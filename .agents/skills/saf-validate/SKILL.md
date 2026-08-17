---
name: saf-validate
description: Independently validate an accumulated SDD feature implementation against its specification and configured gates. Use for feature readiness after task work; not for implementing fixes or reviewing one task PR.
metadata:
  version: 4.1.0
  pack: core
extends: saf-check-task
requires: [config, spec-package, task-evidence]
consumes: [domain-glossary, project-context]
produces: [validation-report]
baseline: [tlc-spec-driven, tdd]
compatible_with: [core, full, github, local-files]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'validation-report present with status PASS (PASS invalid on a false-positive catalog hit) and every specification requirement satisfied'
  blocking_conditions: [requirements_unmet, gates_failed]
  evidence_required: [validation-report]
---

# Validate an SDD feature

## When to use

Use when the user asks whether one implemented feature is ready against its SDD. Read [the TLC baseline](../sdd-agentic-flow-shared/references/tlc-baseline.md), [the TDD baseline](../sdd-agentic-flow-shared/references/tdd-baseline.md), [change-impact validation](../sdd-agentic-flow-shared/references/change-impact-validation.md), [task slicing](../sdd-agentic-flow-shared/references/task-slicing.md), [feature profiles](../sdd-agentic-flow-shared/references/feature-profiles.md), [spec lifecycle](../sdd-agentic-flow-shared/references/spec-lifecycle.md), and [safety rules](../sdd-agentic-flow-shared/references/workflow-safety.md).

## When not to use

Do not use to implement code, repair findings, validate only one task, create a PR, or infer a feature identity from ambiguous branch names. For a single task before handoff/PR, use `saf-check-task` instead — this skill assumes several already-checked tasks have accumulated.

## Inputs

- One feature identifier.
- `.sdd-agentic-flow/config.yml`, feature context/spec/design/tasks artifacts, accumulated implementation, and configured gates.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first. If it is missing, ask the user to run `/saf-setup` or `npx sdd-agentic-flow init`; otherwise resolve exactly one feature and its configured validation paths and commands.
2. Follow this **fresh-eyes** order at feature scope (state-checking, not narrative-judging): re-read spec + repo contracts → re-derive expected per AC (ignore implementer narrative) → run current sensor commands (environment state) → requirement coverage matrix (`requirement → sensor → current result`) → apply false-positive catalog → Status (existing enum only). Read `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md` when they exist. Read `workflow.feature_profile` from `.sdd-agentic-flow/config.yml` and apply feature-profile guidance to calibrate expected rigor.
3. Re-read the spec **and** normative repo contracts. Derive feature-scoped validation obligations from requirements, accumulated diff, affected seams, architecture, work intent, feature profile, and risk, following `change-impact-validation.md`. Select the smallest adequate sensor set; record each omitted higher-level sensor and its requirement-based reason. Confirm task-level TDD evidence for code changes: behavior, contractual seams, current passing-sensor commands, explained deviations, untested risks, and requirement-to-evidence traceability. Treat stale results as context, not current proof. Record explicit evidence gaps. Distinguish verification limits from implementation failures. For each required behavior, name one wrong implementation that the current sensors would still pass (**non-shallow litmus**). If you cannot, record **Shallow sensor** or an evidence gap — not `Status: ready`.
4. Confirm task slices have independent checks or recorded horizontal-slice justifications and dependencies. An unmapped AC cannot silently PASS. Include **unchanged** ACs in the coverage matrix; do not skip unchanged-behavior sensors on bugfix. If the spec is still **ambiguous**, do not PASS / `Status: ready` an implementation of one interpretation. On spec drift, write `not ready` with a reconciliation note — do not rewrite the spec to match the code.
5. Run only configured, safe, applicable validation gates, applying `../sdd-agentic-flow-shared/references/evidence-standard.md`. Record actual **current** commands and results (command, exit status, observed result, requirement mapping); evidence from prior runs is context, not proof. Emit the v4 validation-report contract: evidence index table (`| Requirement anchor | Sensor | Result | Freshness |`) distinguishing selected obligations, intentionally omitted sensors, unsatisfied completion criteria, and human-judgment boundaries. A passing sensor is evidence, not a correctness verdict. Self-report is not evidence. This skill must not inherit author narrative.
6. Decide `ready`, `not ready`, `blocked`, or `inconclusive`. A feature is ready only when all mandatory criteria have current adequate evidence and required gates pass. Never silent PASS. Never write `Status: ready` on a false-positive catalog hit.
7. Produce a sanitized local report in `.sdd-agentic-flow/reports` when configuration permits; never create `validation.md` under `.specs`. Never move or delete `.specs/features/<slug>/`. After a PASS report, **may recommend** the human set `Lifecycle: implemented`; must not write that line itself.

## Safety

Remain read-only except for permitted local report or disposable test artifacts. Do not change code, specs, Git history, PR metadata, trackers, remote services, or default configuration. Preserve existing work and redact secrets, PII, and absolute paths. Self-report is not evidence. This skill must not inherit author narrative.

## Output

Return feature identity, validation scope (impact, obligations, selected and omitted sensors), decision, requirement/task evidence counts, required gate results, ranked gaps, report location if written, and next step. When the decision is `not ready`, `blocked`, or `inconclusive` and resolution is likely to span a session or agent boundary, write or update `handoff.md` per `../sdd-agentic-flow-shared/references/handoff-standard.md`.

## Autonomy

Supports `manual`, `supervised`, and `autonomous` autonomy levels (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`). In `autonomous` mode, treating the feature as ready for `saf-create-pr` requires a validation-report with status PASS and every specification requirement satisfied (PASS invalid on a false-positive catalog hit); an unmet requirement or failed gate blocks that advance. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
