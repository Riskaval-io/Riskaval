# Getting Started

RiskAval's policy engine is fail-closed authorization for any autonomous
agent, not just trading bots. This example shows a generic agent that
sends emails and deletes files — no trading concepts required.

## Install

```bash
pip install git+https://github.com/Riskaval-io/Riskaval.git@v0.1.0
```

## Write your policy config

`policy_config_example.yaml` is calibrated for a trading motor. Copy it
and write your own — here's a minimal one for a generic agent:

```yaml
account_id: "my-agent"

rules:
  max_emails_per_hour: 5
  max_daily_loss: -100      # required field name, reuse for any dollar cap
  max_weekly_loss: -500
  max_contracts: 999         # required field name, ignore if not applicable

block:
  - action: send_email
    condition: "params.get('recipient_count', 0) > rules.max_emails_per_hour"
    reason: "Too many recipients in a single send"

  - action: delete_file
    condition: "params.get('path', '').startswith('/prod')"
    reason: "Refuses to delete anything under /prod"

log:
  - action: send_email
    condition: "true"
    reason: "Every email logged for audit"
```

## Wire it into your agent

```python
from datetime import datetime, timezone
from policy_engine import PolicyEngine
from audit_schema import MarketContext, RiskState

engine = PolicyEngine("my_policy_config.yaml")

def before_agent_action(action_name: str, params: dict, agent_id: str):
    """Call this before your agent actually performs an action."""
    audit_entry = engine.evaluate(
        action_type=action_name,          # any string, e.g. "send_email"
        proposed_params=params,           # e.g. {"recipient_count": 12}
        market_context=MarketContext(
            timestamp=datetime.now(timezone.utc),
            instrument="n/a", price=0,      # unused outside trading, required fields
        ),
        risk_state=RiskState(
            daily_pnl=0, weekly_pnl=0,       # reuse as any dollar-denominated counter
            open_contracts=0, account_equity=1000,
        ),
        agent_id=agent_id, account_id="my-agent",
    )

    if audit_entry.decision.value == "blocked":
        print(f"BLOCKED: {audit_entry.reason}")
        return False  # do not perform the action

    return True  # safe to proceed (approved or logged)


# Example usage
if before_agent_action("send_email", {"recipient_count": 12}, agent_id="mailer-1"):
    send_the_email()
```

## Sharing anonymized data (optional, for pilot participants)

If you're piloting RiskAval and want to contribute anonymized data to
help calibrate the risk model:

```python
from anonymizer import Anonymizer
from aggregated_dataset import AggregatedDataset, AggregatedDatasetMetadata
import os
from datetime import datetime, timezone

anonymizer = Anonymizer(pseudonym_salt=os.environ["PSEUDONYM_SALT"])
dataset = AggregatedDataset(AggregatedDatasetMetadata(
    dataset_id="my-agent-pilot",
    created_at=datetime.now(timezone.utc),
    last_updated=datetime.now(timezone.utc),
))

# After each evaluate() call:
dataset.add_entry(anonymizer.anonymize(audit_entry))

# Export weekly and send to the RiskAval team:
dataset.to_jsonl("weekly_export.jsonl")
```

No account IDs, agent IDs, or exact parameters leave your machine —
only bucketed context (time of day, volatility/magnitude bucket) and
the decision outcome.

## Notes on field names

The dataclasses (`MarketContext`, `RiskState`) were designed around a
trading motor, so some field names (`instrument`, `price`, `atr`,
`open_contracts`) don't map 1:1 to non-trading domains. For now, reuse
them loosely (see example above) — a domain-neutral schema is on the
roadmap once there's real pilot usage to calibrate it against.
