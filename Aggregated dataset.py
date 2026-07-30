"""
aggregated_dataset.py -- Acumula AnonymizedAuditEntry de multiples
traders/agentes y exporta a CSV o JSON Lines. Este es el dataset
vendible/compartible del punto #4 del plan de RiskAval.

RECONSTRUIDO a partir de fragmentos recuperados de la sesion original
(chat "MNQ", 2026-07-09). Incluye el fix ya encontrado entonces:
to_csv/to_jsonl deben funcionar tanto si un campo es un Enum como si
ya es un string plano (esto ultimo pasa despues de recargar un CSV
previamente exportado, donde los Enums se leen como texto).
"""
import csv
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from anonymizer import AnonymizedAuditEntry


@dataclass
class AggregatedDatasetMetadata:
    """Metadatos del dataset -- para auditoria, trazabilidad, y control
    de versiones."""
    dataset_id: str
    created_at: datetime
    last_updated: datetime
    entry_count: int = 0
    unique_pools: int = 0
    data_version: str = "1.0"
    anonymization_salt_hash: Optional[str] = None


class AggregatedDataset:
    def __init__(self, metadata: AggregatedDatasetMetadata):
        self.metadata = metadata
        self.entries: list[AnonymizedAuditEntry] = []
        self._pools_seen: set[str] = set()

    # -----------------------------------------------------------
    def add_entry(self, entry: AnonymizedAuditEntry) -> None:
        self.entries.append(entry)
        self._pools_seen.add(entry.pool_id)
        self.metadata.entry_count = len(self.entries)
        self.metadata.unique_pools = len(self._pools_seen)
        self.metadata.last_updated = datetime.now(timezone.utc)

    # -----------------------------------------------------------
    @staticmethod
    def _val(field):
        """Devuelve el valor string de un campo que puede ser Enum o
        ya un string plano (ej. tras recargar desde CSV) -- este es
        el fix del bug real encontrado en la sesion original."""
        if field is None:
            return ""
        return field.value if hasattr(field, "value") else field

    # -----------------------------------------------------------
    @staticmethod
    def _write_atomic(path: str, write_fn) -> None:
        """
        Escribe a un archivo temporal en el mismo directorio y luego
        hace os.replace (atomico en POSIX) -- si el proceso muere a
        mitad de la escritura, el archivo original queda intacto en
        vez de quedar corrupto a medias. El dataset es el activo
        vendible; no puede arriesgarse a corromperse por un crash.
        """
        directorio = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=directorio, prefix=".tmp_", suffix=".part")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                write_fn(f)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    # -----------------------------------------------------------
    def to_csv(self, path: str) -> None:
        def _escribir(f):
            writer = csv.writer(f)
            writer.writerow([
                "entry_id", "pool_id", "session_bucket", "volatility_bucket",
                "hour_of_day", "action_type", "decision", "risk_reason_bucket",
                "outcome_pnl_bucket",
            ])
            for e in self.entries:
                writer.writerow([
                    e.entry_id,
                    e.pool_id,
                    self._val(e.session_bucket),
                    self._val(e.volatility_bucket),
                    e.hour_of_day,
                    self._val(e.action_type),
                    self._val(e.decision),
                    self._val(e.risk_reason_bucket),
                    self._val(e.outcome_pnl_bucket),
                ])
        self._write_atomic(path, _escribir)

    # -----------------------------------------------------------
    def to_jsonl(self, path: str) -> None:
        def _escribir(f):
            for e in self.entries:
                row = {
                    "entry_id": e.entry_id,
                    "pool_id": e.pool_id,
                    "session_bucket": self._val(e.session_bucket),
                    "volatility_bucket": self._val(e.volatility_bucket),
                    "hour_of_day": e.hour_of_day,
                    "action_type": self._val(e.action_type),
                    "decision": self._val(e.decision),
                    "risk_reason_bucket": self._val(e.risk_reason_bucket) or None,
                    "outcome_pnl_bucket": self._val(e.outcome_pnl_bucket) or None,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._write_atomic(path, _escribir)
