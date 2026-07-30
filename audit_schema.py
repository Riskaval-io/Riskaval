"""
audit_schema.py -- Modelos de datos del motor de politicas de RiskAval.

Cada accion propuesta por un motor de trading (o, en general, por un
agente autonomo) se representa como UN AuditEntry: contexto de mercado
+ estado de riesgo + decision tomada + motivo. Es el objeto que fluye
entre policy_engine.py, anonymizer.py y aggregated_dataset.py.

RECONSTRUIDO a partir de fragmentos recuperados de la sesion original
(chat "MNQ", 2026-07-09) -- estos dataclasses coinciden con el diseño
verificado en esa sesion.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    OPEN_POSITION = "open_position"
    MODIFY_STOP = "modify_stop"
    MODIFY_TARGET = "modify_target"
    CLOSE_POSITION = "close_position"
    INCREASE_SIZE = "increase_size"
    CANCEL_ORDER = "cancel_order"
    QUERY_ACCOUNT_STATUS = "query_account_status"


class Decision(str, Enum):
    APPROVED = "approved"
    LOGGED = "logged"
    BLOCKED = "blocked"


@dataclass
class MarketContext:
    timestamp: datetime
    instrument: str
    price: float
    atr: Optional[float] = None
    delta_signal: Optional[str] = None
    session: Optional[str] = None
    minutes_to_next_news_event: Optional[int] = None


@dataclass
class RiskState:
    daily_pnl: float
    weekly_pnl: float
    open_contracts: int
    account_equity: float
    position_size_requested: Optional[int] = None


@dataclass
class AuditEntry:
    entry_id: str
    agent_id: str
    account_id: str
    action_type: ActionType
    proposed_params: dict
    market_context: MarketContext
    risk_state: RiskState
    decision: Decision
    rule_triggered: Optional[str] = None
    reason: Optional[str] = None
    outcome_pnl: Optional[float] = None
    outcome_recorded_at: Optional[datetime] = None