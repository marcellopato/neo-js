# Decision Gates

Use a Decision Gate only for ambiguity that materially affects architecture, scope, data, external
contracts, security, irreversible mutation, human authority, or subjective product/architecture
judgment not resolved by the specification. Local choices may follow established repository
conventions.

## Required fields

```text
Decision required
Why human judgment is required
Known bounded options (when known)
Affected scope
Blocked transition or task
Safe independent work (when any)
```

Decision gates block autonomous completion authority. They do not authorize the agent to choose
among consequential options without human input.

See [system-invariants.md](system-invariants.md) (AMBIGUITY-001, JUDGMENT-001) and
[bounded-execution.md](bounded-execution.md).
