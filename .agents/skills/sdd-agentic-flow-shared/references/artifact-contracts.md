# Artifact contracts

Every SDD artifact this package's skills produce has an implicit structure, mirrored by
`shared/templates/*.template.md`. This file documents that structure explicitly so skills and
`doctor` can confirm an artifact's required sections are present without inventing a new schema
format. This is a presence check, not full-schema validation. It does not verify section
*content*, only that the required headers exist.

- `spec.md`: required `# Specification — {feature_slug}`, one `## Requirement REQ-{id}` per
  requirement (stable `REQ-*` identifiers), `## Acceptance criteria`. Produced by
  `saf-create-spec`.
- `design.md`: required when the artifact exists (optional for `small_fix`; see
  `feature-profiles.md`): `# Design — {feature_slug}`, `## Decision`, `## Path ownership`.
  Produced by `saf-create-spec`.
- `tasks.md`: required `# Tasks — {feature_slug}`, one `## {task_id}` per task (each with
  Acceptance criteria, Review boundary, Slice type, Independently verifiable, Public seam,
  **Requirement anchors** (REQ-* fulfilled by the task), Dependencies (task-order only —
  never requirement fulfillment), Horizontal-slice justification, and Expand-contract strategy),
  plus nested `## TDD baseline` for code tasks. Produced by `saf-create-spec`.
- task-prompt: required `# Task prompt — {task_id}`, `## Task slice` including **Requirement
  anchors**, `## TDD baseline`. Produced by `saf-create-prompts`.
- check-report: required `# Task check — {task_id}`, top-line `Status:`, **`Feature:
  {feature_slug}`**, `## Validation scope`, evidence table:

  ```text
  | Requirement anchor | Sensor | Result | Freshness |
  ```

  Freshness is `current`, `historical`, `stale`, or `not-run`. Also `## Evidence` (detailed
  current evidence record per evidence-standard.md) and `## TDD evidence`. Produced by
  `saf-check-task`.
- validation-report: required `# Feature validation — {feature_slug}`, top-line `Status:`,
  `## Validation scope`, evidence table with anchor/sensor/result/freshness, `## Evidence`,
  `## TDD evidence`. Produced by `saf-validate`.
- pr-package: required `# {feature_slug} — {task_id}`, `## Scope`, `## Evidence`. Produced by
  `saf-create-pr`.

## Requirement identity (v4)

`REQ-*` identity is semantic, not presentation order:

- IDs are unique within a feature and are never reused for unrelated semantics.
- Rewording that preserves one requirement's identity preserves its ID.
- Requirement anchors in tasks/prompts reference fulfillment; task-order `Dependencies` never
  substitute for requirement fulfillment.

## Traceability matrix

| Contract | Canonical producer | Consumers |
| --- | --- | --- |
| `REQ-*` identity | `saf-create-spec` | prompts, implement, check, validate, graph |
| Requirement anchors | `saf-create-spec` / `saf-create-prompts` | implement, multi, check, graph |
| Evidence index row + freshness | check/validation reports | multi, graph, handoff |
| `Feature:` task-check identity | `saf-check-task` | multi, validate, graph |

See [system-invariants.md](system-invariants.md), [bounded-execution.md](bounded-execution.md),
[task-context-package.md](task-context-package.md), and [decision-gates.md](decision-gates.md).

## Legacy optional convention (pre-v4)

Pre-v4 artifacts may omit `Feature:` and evidence tables; they remain human-readable history but
cannot satisfy v4 graph coverage.
