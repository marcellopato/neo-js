# Bounded execution

Host-neutral semantic contract. Not a task artifact, frontmatter schema, retry engine or host adapter.

## Fields

```text
Goal                 bounded intended outcome
Completion criteria  observable state that demonstrates it
Iteration policy     iteration-safe | bounded-with-gate | human-judgment
Stop/escalation      satisfied | missing evidence | no semantic progress | decision gate | unsafe scope
```

`deterministic`, `observable` and `measured` criteria can support bounded autonomous iteration.
`human-judgment` criteria let an agent prepare evidence and options but retain human completion authority.

## Evidence vocabulary

For Sensor, Evidence, Oracle, Adequacy, Verification, Freshness and Decision, apply
[evidence-standard.md](evidence-standard.md). No second vocabulary is introduced here.

Do not prescribe an arbitrary universal retry count or persist generic per-attempt history outside
the multi-task ledger.

## Host boundary

A SAF skill never autonomously starts another host turn. It reports whether another bounded attempt
is admissible, blocked or requires human judgment; the host or human decides whether to run it.

See [task-context-package.md](task-context-package.md) and [system-invariants.md](system-invariants.md).
