# Security Policy

RiskAval is a fail-closed authorization engine. If it fails in a way
that lets an unsafe action through, that's a security issue, not just
a bug — please treat it accordingly.

## Reporting a vulnerability

If you find a way to make the policy engine approve an action it
should have blocked, or any other security-relevant flaw:

1. **Do not open a public GitHub issue first.**
2. Email the details privately (see repo owner's GitHub profile for
   contact), including: what you changed, what you expected, what
   actually happened, and a minimal reproduction if possible.
3. You'll get an acknowledgment and a timeline for a fix.
4. Once patched, we'll credit you in the release notes (unless you'd
   rather stay anonymous) and you're welcome to publish your own
   writeup after the fix ships.

## What counts as a security issue here

- Any input that causes `evaluate()` to return `APPROVED` or `LOGGED`
  when it should have returned `BLOCKED`.
- Any way to crash or bypass the engine such that an action proceeds
  without ever being evaluated.
- Injection via YAML config or `proposed_params` that escapes the
  restricted `_safe_eval` sandbox.
- Anonymization bypass — any way to re-identify an account from
  `AnonymizedAuditEntry` or the exported dataset.

## What's out of scope for now

This is an early-stage, single-maintainer project. There's no bug
bounty program and no SLA on response time yet — but every report will
be read and taken seriously.
