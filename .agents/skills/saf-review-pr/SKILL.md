---
name: saf-review-pr
description: Review one task-scoped pull request against its SDD, diff, and configured checks. Use for an evidence-based PR review; not for fixing findings or mutating PR metadata.
metadata:
  version: 4.1.0
  pack: pr
extends: saf-create-pr
requires: [config, pr-reference]
consumes: []
produces: [review-findings]
baseline: [tlc-spec-driven]
compatible_with: [full, github, pr]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'review-findings present, every finding evidence-backed, and no unresolved blocking finding'
  blocking_conditions: [blocking_findings_unresolved]
  evidence_required: [review-findings]
---

# Review an SDD pull request

## When to use

Use when the user asks to review a PR associated with one SDD task. Read [the TLC baseline](../sdd-agentic-flow-shared/references/tlc-baseline.md), [engineering principles](../sdd-agentic-flow-shared/references/engineering-principles.md), and [safety rules](../sdd-agentic-flow-shared/references/workflow-safety.md).

## When not to use

Do not use to implement fixes, validate a whole feature, create a PR, or review a PR whose task scope cannot be resolved.

## Inputs

- PR URL/number or local branch plus one task reference.
- `.sdd-agentic-flow/config.yml`, task SDD artifacts, diff, and available check evidence.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first; if it is missing, ask the user to run `/saf-setup` or `npx sdd-agentic-flow init`, then resolve the task, base, and head context.
2. Make two independent judgments: (1) spec/correctness against the SDD package, (2) engineering fit against `../sdd-agentic-flow-shared/references/engineering-principles.md` and repo conventions. Pretty code must not hide a spec miss. A spec-correct but over-engineered change is a quality finding, not an automatic block. Review acceptance criteria, changed behavior, tests, scope boundaries, and configured quality/security expectations.
3. Verify findings with code or reproducible evidence, applying `../sdd-agentic-flow-shared/references/evidence-standard.md`. Separate blocking defects from non-blocking observations; do not invent CI results; do not invent done.
4. Produce a Markdown-first findings ledger with severity, file/line, evidence, required remediation, and re-review focus.

## Safety

Operate read-only. Do not submit reviews, comments, approvals, labels, assignments, status changes, code edits, Git mutations, or network mutations by default.

## Output

Return `approved`, `changes requested`, `blocked`, or `inconclusive`, plus the scoped findings ledger, check evidence, and next step.

## Autonomy

Supports `manual`, `supervised`, and `autonomous` autonomy levels (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`). Autonomy only governs whether the workflow *advances* after this skill completes (to `saf-fix-pr` on accepted findings, or to `saf-validate` when ready) — this skill still never corrects a finding automatically, in any autonomy level. Advancing in `autonomous` mode requires review-findings present, every finding evidence-backed, and no unresolved blocking finding. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
