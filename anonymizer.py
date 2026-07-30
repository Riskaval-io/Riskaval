"""
anonymizer.py -- Convierte un AuditEntry crudo en un AnonymizedAuditEntry
vendible/compartible: elimina account_id real, agent_id real, y la
senal de entrada exacta. Preserva regimen de mercado (bucketizado) y
resultado -- lo que sirve para analisis de riesgo agregado.

RECONSTRUIDO a partir de fragmentos recuperados de la sesion original
(chat "MNQ", 2026-07-09). El bug real encontrado en esa sesion (la
clasificacion buscaba palabras clave en ingles contra razones en
español, y 5 de 8 categorias caian a "other") ya viene corregido aqui:
_reason_to_bucket clasifica sobre `rule_triggered` (el texto de la
condicion, siempre en formato consistente) en vez de sobre `reason`
(texto libre en español para humanos).
"""
import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from audit_schema import ActionType, AuditEntry, Decision


class SessionBucket(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NY = "ny"
    OVERNIGHT = "overnight"


class VolatilityBucket(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    UNKNOWN = "unknown"


class RiskReasonBucket(str, Enum):
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    WEEKLY_LOSS_LIMIT = "weekly_loss_limit"
    POSITION_SIZE_LIMIT = "position_size_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    TIME_WINDOW = "time_window"
    NEWS_BLACKOUT = "news_blackout"
    MANUAL_APPROVAL_REQUIRED = "manual_approval_required"
    ENGINE_FAILURE = "engine_failure"
    OTHER = "other"


class OutcomePnlBucket(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    UNKNOWN = "unknown"


@dataclass
class AnonymizedAuditEntry:
    """
    Version vendible de un AuditEntry. Contiene todo lo util para
    analisis de riesgo EXCEPTO: account_id real, agent_id real, señal
    de entrada exacta.
    """
    entry_id: str
    # Pool ID es un pseudonimo unico del trader -- una cuenta siempre
    # es el mismo pool_id, pero ese ID nunca revela quien es. Se genera
    # hasheando account_id + una salt secreta.
    pool_id: str

    # Contexto de mercado BUCKETIZADO -- util, pero no exacto (no se
    # puede reproducir el trade tick a tick).
    session_bucket: SessionBucket
    volatility_bucket: VolatilityBucket
    hour_of_day: int  # 0-23, UTC; exactitud: horas, no segundos

    # La accion y su resultado
    action_type: str
    decision: Decision
    risk_reason_bucket: Optional[RiskReasonBucket] = None
    outcome_pnl_bucket: Optional[OutcomePnlBucket] = None


class Anonymizer:
    def __init__(self, pseudonym_salt: str):
        if not pseudonym_salt or not pseudonym_salt.strip():
            raise ValueError(
                "pseudonym_salt no puede estar vacia -- sin ella, pool_id "
                "se vuelve predecible (sha256 de solo account_id, "
                "atacable con tabla de arcoiris si account_id sigue un "
                "patron conocido). Usa una variable de entorno secreta."
            )
        self._salt = pseudonym_salt

    # -----------------------------------------------------------
    def _pool_id(self, account_id: str) -> str:
        h = hashlib.sha256((self._salt + account_id).encode()).hexdigest()
        return f"pool_{h[:16]}"

    def _session_bucket(self, ts: datetime) -> SessionBucket:
        hour = ts.hour
        if 0 <= hour < 7:
            return SessionBucket.ASIA
        if 7 <= hour < 12:
            return SessionBucket.LONDON
        if 12 <= hour < 17:
            return SessionBucket.NY
        return SessionBucket.OVERNIGHT

    def _volatility_bucket(self, atr: Optional[float]) -> VolatilityBucket:
        if atr is None:
            return VolatilityBucket.UNKNOWN
        if atr < 20:
            return VolatilityBucket.LOW
        if atr < 50:
            return VolatilityBucket.MEDIUM
        if atr < 100:
            return VolatilityBucket.HIGH
        return VolatilityBucket.EXTREME

    def _reason_to_bucket(self, entry: AuditEntry) -> Optional[RiskReasonBucket]:
        """
        Clasifica sobre `rule_triggered` (texto de condicion, formato
        consistente), NO sobre `reason` (texto libre en español) --
        ese fue el bug real encontrado: buscar keywords en ingles
        contra razones en español hacia caer 5 de 8 categorias a
        "other". El fallo interno del motor (reason con "bloqueado
        por seguridad") se detecta aparte, sobre reason, porque ese
        caso especifico no tiene rule_triggered.
        """
        if entry.reason and "bloqueado por seguridad" in entry.reason.lower():
            return RiskReasonBucket.ENGINE_FAILURE

        text = (entry.rule_triggered or "").lower()
        if not text:
            return None
        if "max_daily_loss" in text or "daily_pnl" in text:
            return RiskReasonBucket.DAILY_LOSS_LIMIT
        if "max_weekly_loss" in text or "weekly_pnl" in text:
            return RiskReasonBucket.WEEKLY_LOSS_LIMIT
        if "max_contracts" in text and "increase_size" not in text and "open_contracts" not in text:
            return RiskReasonBucket.POSITION_SIZE_LIMIT
        if "exposure" in text or "exposicion" in text:
            return RiskReasonBucket.EXPOSURE_LIMIT
        if "trading_window" in text:
            return RiskReasonBucket.TIME_WINDOW
        if "news" in text or "blackout" in text:
            return RiskReasonBucket.NEWS_BLACKOUT
        if "open_contracts" in text and "max_contracts" in text:
            return RiskReasonBucket.MANUAL_APPROVAL_REQUIRED
        return RiskReasonBucket.OTHER

    def _outcome_bucket(self, pnl: Optional[float]) -> Optional[OutcomePnlBucket]:
        if pnl is None:
            return None
        if pnl > 0:
            return OutcomePnlBucket.WIN
        if pnl < 0:
            return OutcomePnlBucket.LOSS
        return OutcomePnlBucket.BREAKEVEN

    # -----------------------------------------------------------
    def anonymize(self, entry: AuditEntry) -> AnonymizedAuditEntry:
        action_value = (
            entry.action_type.value
            if isinstance(entry.action_type, ActionType)
            else str(entry.action_type)
        )
        return AnonymizedAuditEntry(
            entry_id=entry.entry_id,
            pool_id=self._pool_id(entry.account_id),
            session_bucket=self._session_bucket(entry.market_context.timestamp),
            volatility_bucket=self._volatility_bucket(entry.market_context.atr),
            hour_of_day=entry.market_context.timestamp.hour,
            action_type=action_value,
            decision=entry.decision,
            risk_reason_bucket=self._reason_to_bucket(entry),
            outcome_pnl_bucket=self._outcome_bucket(entry.outcome_pnl),
        )