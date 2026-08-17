# TLC baseline

Baseline version: 0.7.0

This package adapts a minimum methodology from `tlc-spec-driven`.
See `NOTICE` and `LICENSING.md` for attribution and licensing.

## Minimum flow

Use **Specify → Discuss → Design → Tasks → Execute → Verify**. Clarify ambiguity
before execution, keep requirements traceable to acceptance criteria, derive
sensors from those criteria, and preserve current evidence before completion.

## Internal implementation

`saf-create-spec` owns Specify through Tasks. `saf-implement` and
`saf-implement-multi` implement the Execute intent. `saf-check-task` and
`saf-validate` implement Verify. Direct TLC Execute is not invoked.

## Extensions

The flow may impose stricter safety or review constraints, but must not weaken this
baseline. Atomic, reviewable increments are required; commits remain manual unless
the consumer explicitly changes its policy.

## Invariants

- Do not invent requirements or silently resolve material drift. Specifications are
  **living** control artifacts: on spec drift, stop and reconcile with the human; do not
  silently implement a “better” requirement or rewrite the spec to match the code.
- Load artifacts on demand for the current feature and operation; do not
  load multiple feature specs simultaneously. See [spec-lifecycle.md](spec-lifecycle.md).
- Stop and report `Blocked` when evidence or authority is missing.
- Implementation work records current adequate behavioral evidence at contractual
  seams (see [tdd-baseline.md](tdd-baseline.md)). The RED → GREEN → REFACTOR
  ritual is optional and is not the proof mechanism.
- Do not claim completion without runnable or inspectable evidence.
  Self-report is not completion. A claim of done that is not backed by a current
  executed sensor is illegitimate (see [false-positive classes](evidence-standard.md#false-positive-classes)
  in [evidence-standard.md](evidence-standard.md)).
