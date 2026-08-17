# System invariants

SAF distinguishes mechanically checkable, contractually checkable, and human-judgment boundaries.
These invariants apply across skills, artifacts, and CLI surfaces.

| ID | Invariant | Check class |
| --- | --- | --- |
| TRACE-001 | Every consequential transition is reconstructable from durable artifacts and current evidence. | contractual |
| AUTH-001 | Agent-authored content cannot satisfy a human authorization gate. | mechanical |
| POLICY-001 | Effective constraints are visible before planning dependent actions. | contractual |
| EVIDENCE-001 | Self-report never substitutes for current adequate evidence. | mechanical |
| EVIDENCE-002 | Material dependency changes require evidence freshness re-evaluation. | contractual |
| STATE-001 | Each durable state domain has one canonical writer. | contractual |
| STATE-002 | Summaries, handoffs and views are projections, never authority. | contractual |
| AMBIGUITY-001 | Consequential ambiguity is surfaced, not guessed. | human-judgment |
| GOAL-001 | Every implementation-ready task has a bounded intended outcome, explicit constraints and evidence-backed completion criteria. | contractual |
| ITERATION-001 | Autonomous continuation requires bounded scope, valid completion criteria, meaningful progress and clear stop/escalation with no crossed human gate. | contractual |
| VERIFY-001 | Consequential verification re-derives its oracle from canonical artifacts; prefer fresh/independent context when permitted. | contractual |
| JUDGMENT-001 | Measurable passing criteria do not resolve consequential product, architecture or complexity judgment absent from the specification. | human-judgment |
| PROGRESS-001 | Attempts, tool activity and status churn are not progress; continued iteration requires material improvement in state, evidence, diagnosis or uncertainty. | contractual |
| MULTI-001 | A task has at most one active owner in one multi-task execution. | mechanical |
| MULTI-002 | Safe independent work may continue around a blocked lane without bypassing its gate. | contractual |

See also [bounded-execution.md](bounded-execution.md), [evidence-standard.md](evidence-standard.md), and [decision-gates.md](decision-gates.md).
