# RiskAval

Fail-closed risk infrastructure for autonomous systems.

Most governance platforms tell you what happened after the fact. RiskAval is built to stop the bad action before it happens at all.

It's not another monitoring or logging layer sitting on the side. Every action goes through the policy engine first. If it satisfies the rules, it proceeds. If it violates a policy, or the engine can't evaluate it with confidence, execution stops right there. No confidence, no green light.

## Why I built this

I built RiskAval out of what I learned running an automated trading system on real capital.

In quantitative trading, you don't get to manage risk after the trade executes. Every decision has to be evaluated before capital is on the line, because a single bad call produces a real loss immediately, not a lesson for next time. That reality is what makes preventive controls worth more than a dashboard that explains the damage afterward.

The same logic applies once software starts acting on its own. Once a system can execute transactions, call external services, touch infrastructure, or make operational decisions without a human approving each step, it needs something evaluating the risk of that action before it happens, not a log entry after.

RiskAval takes risk management ideas that already work in trading and applies them to autonomous execution.

Trust scoring for AI agents isn't a new idea. There's an IETF draft for it, and at least one live product doing agent credit scores. What's missing isn't the concept. It's calibration that comes from actually managing risk with real capital, not a heuristic someone wrote based on what sounded reasonable.

What it actually does:

- Authority that adapts to track record. An agent's autonomy is based on how it's actually performed, not a fixed permission you set once and forget.
- Circuit breakers on execution. When predefined risk limits get hit, operations halt automatically instead of just triggering an alert.
- Fail-closed by default. If an action can't be validated with confidence, it's denied. Silence is not the same as approval.
- Behavioral signature logging. Every execution gets fingerprinted so drift in behavior over time is something you can actually measure.

## Where this stands right now

**Working:**
- Policy engine, YAML-configured, three decision tiers (approve / log / block)
- Behavioral signature logging
- Automated diagnostic reporting

**In progress:**
- Wiring the policy engine into a live execution environment

**Planned:**
- A public, cross-system behavioral observatory
- A pip-installable SDK

Note: multi-hop agent delegation (Agent A authorizing Agent B) is an open problem industry-wide right now. This doesn't solve that yet, and neither does anything else.

Right now the priority is getting the execution layer solid and predictable before I build anything else on top of it. I'm still tuning where the block threshold should sit, and I'll probably get that wrong once or twice before it's right.

## Architecture

```
Client Request
      │
      ▼
Policy Engine
      │
      ▼
Risk Evaluation
      │
      ▼
Decision Layer
      │
   ┌──┼──────────┐
   ▼  ▼          ▼
Approve  Log        Block
→Execute →Execute  →Reject
         & Record
      │
      ▼
Behavioral Logger
      │
      ▼
Diagnostics & Reporting
```

## License

MIT
