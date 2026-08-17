# Task Context Package

A logical package — not a mandatory file — specifying minimum sufficient context for a task worker.

## Contents

```text
task identity and bounded goal / intended outcome
acceptance criteria / requirement anchors
scope and review boundary; constraints/invariants that must remain true
dependencies and relevant dependency evidence
relevant design seam and applicable invariants
validation obligations, required/candidate sensors and completion criteria
applicable iteration constraints and stop/escalation when autonomous continuation is under consideration
known blockers / human gates
host constraints when relevant
```

## Consumer classification

Every consumer classifies each item as:

- **MUST READ** — required before acting
- **READ WHEN RELEVANT** — load on demand
- **DO NOT PRELOAD** — unrelated feature packages, PR history, prior conversation

Unrelated feature packages, PR history and prior conversation are not default context.

See [bounded-execution.md](bounded-execution.md) and [system-invariants.md](system-invariants.md).
