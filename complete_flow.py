"""
complete_flow.py -- Demuestra el flujo end-to-end de RiskAval:

  1. Motor de decision (MNQ) propone una accion
  2. PolicyEngine evalua contra politicas -> devuelve AuditEntry
     (APPROVED/LOGGED/BLOCKED)
  3. Si AuditEntry.decision != BLOCKED, se ejecutaria contra el broker
     (fuera del alcance de este demo)
  4. Se guarda el entry (aqui: se imprime -- en produccion: Postgres)
  5. Si el trader dio data_sharing_consent=true, se anonimiza
  6. El entry anonimizado se agrega al dataset agregado (vendible)

RECONSTRUIDO a partir de fragmentos recuperados de la sesion original
(chat "MNQ", 2026-07-09). Los 4 casos de prueba abajo reproducen
exactamente los 4 escenarios confirmados entonces: aprobado en
condiciones normales, bloqueado por tamano de posicion, bloqueado por
ventana horaria, bloqueado por limite de perdida diaria.
"""
import os
from datetime import datetime, timezone

from policy_engine import PolicyEngine
from audit_schema import ActionType, MarketContext, RiskState
from anonymizer import Anonymizer
from aggregated_dataset import AggregatedDataset, AggregatedDatasetMetadata

CONFIG_PATH = "policy_config_example.yaml"
# La salt NUNCA debe quedar fija en el codigo -- controla que tan
# reversible es el pseudonimo del pool_id. En este demo se usa un
# valor de ejemplo SOLO si la variable de entorno no esta seteada;
# en produccion, PSEUDONYM_SALT es obligatoria.
PSEUDONYM_SALT = os.environ.get("PSEUDONYM_SALT", "demo-salt-cambiar-en-produccion")

engine = PolicyEngine(CONFIG_PATH)
anonymizer = Anonymizer(pseudonym_salt=PSEUDONYM_SALT)
dataset = AggregatedDataset(
    metadata=AggregatedDatasetMetadata(
        dataset_id="mnq-risk-dataset-prod",
        created_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )
)


def process_trading_action(
    action_type, proposed_params, market_context, risk_state,
    agent_id, account_id, config,
):
    """Procesa UNA accion de trading a traves de toda la cadena."""
    audit_entry = engine.evaluate(
        action_type=action_type,
        proposed_params=proposed_params,
        market_context=market_context,
        risk_state=risk_state,
        agent_id=agent_id,
        account_id=account_id,
    )

    print(f"[{audit_entry.decision.value.upper():8s}] {action_type.value:16s} -- {audit_entry.reason}")

    if config.get("data_sharing_consent", False):
        anon_entry = anonymizer.anonymize(audit_entry)
        dataset.add_entry(anon_entry)

    return audit_entry


if __name__ == "__main__":
    config = {"data_sharing_consent": True}

    casos = [
        # Caso 1: condiciones normales -> approved
        dict(
            action_type=ActionType.OPEN_POSITION,
            proposed_params={"direction": "long", "contracts": 1},
            market_context=MarketContext(
                timestamp=datetime(2026, 7, 29, 10, 0), instrument="MNQ",
                price=23500.0, atr=35.0,
            ),
            risk_state=RiskState(
                daily_pnl=150.0, weekly_pnl=400.0,
                open_contracts=0, account_equity=50000.0,
            ),
        ),
        # Caso 2: tamano excede el maximo -> blocked
        dict(
            action_type=ActionType.OPEN_POSITION,
            proposed_params={"direction": "long", "contracts": 5},
            market_context=MarketContext(
                timestamp=datetime(2026, 7, 29, 10, 5), instrument="MNQ",
                price=23505.0, atr=35.0,
            ),
            risk_state=RiskState(
                daily_pnl=0.0, weekly_pnl=0.0,
                open_contracts=0, account_equity=50000.0,
            ),
        ),
        # Caso 3: fuera de ventana horaria -> blocked. La ventana real
        # del motor es casi 24h (00:00-23:50), asi que se prueba a las
        # 23:55, el unico tramo que la deja fuera.
        dict(
            action_type=ActionType.OPEN_POSITION,
            proposed_params={"direction": "long", "contracts": 1},
            market_context=MarketContext(
                timestamp=datetime(2026, 7, 29, 23, 55), instrument="MNQ",
                price=23490.0, atr=35.0,
            ),
            risk_state=RiskState(
                daily_pnl=0.0, weekly_pnl=0.0,
                open_contracts=0, account_equity=50000.0,
            ),
        ),
        # Caso 4: limite de perdida diaria alcanzado ($800, real del
        # motor) -> blocked
        dict(
            action_type=ActionType.OPEN_POSITION,
            proposed_params={"direction": "short", "contracts": 1},
            market_context=MarketContext(
                timestamp=datetime(2026, 7, 29, 11, 0), instrument="MNQ",
                price=23480.0, atr=35.0,
            ),
            risk_state=RiskState(
                daily_pnl=-850.0, weekly_pnl=-900.0,
                open_contracts=0, account_equity=48000.0,
            ),
        ),
        # Caso 5 (auditoria): exposicion combinada -- 1 contrato ya
        # abierto + 2 nuevos = 3, excede max_contracts=2. La orden
        # nueva sola (2) NO excede el maximo por si sola -- este caso
        # verifica especificamente el fix de exposicion combinada.
        dict(
            action_type=ActionType.OPEN_POSITION,
            proposed_params={"direction": "long", "contracts": 2},
            market_context=MarketContext(
                timestamp=datetime(2026, 7, 29, 10, 30), instrument="MNQ",
                price=23510.0, atr=35.0,
            ),
            risk_state=RiskState(
                daily_pnl=0.0, weekly_pnl=0.0,
                open_contracts=1, account_equity=50000.0,
            ),
        ),
        # Caso 6 (auditoria): increase_size con open_contracts=1 (bajo
        # el cap de 2) pero pide +5 mas -- combinado (1+5=6) excede
        # el limite. La regla anterior ("open_contracts >= max") NO
        # detectaba esto porque 1 >= 2 es False.
        dict(
            action_type=ActionType.INCREASE_SIZE,
            proposed_params={"contracts": 5},
            market_context=MarketContext(
                timestamp=datetime(2026, 7, 29, 10, 40), instrument="MNQ",
                price=23515.0, atr=35.0,
            ),
            risk_state=RiskState(
                daily_pnl=0.0, weekly_pnl=0.0,
                open_contracts=1, account_equity=50000.0,
            ),
        ),
    ]

    for caso in casos:
        process_trading_action(
            **caso, agent_id="mnq-v7.1", account_id="mnq-live-001", config=config,
        )

    print(f"\nDataset agregado: {dataset.metadata.entry_count} entradas, "
          f"{dataset.metadata.unique_pools} pool(s) unico(s)")
    dataset.to_jsonl("dataset_ejemplo.jsonl")
    dataset.to_csv("dataset_ejemplo.csv")
    print("Exportado a dataset_ejemplo.jsonl y dataset_ejemplo.csv")