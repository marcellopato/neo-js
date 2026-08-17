---
name: saf-create-prompts
description: Generate self-contained, paste-ready implementation prompts from a validated repository-local SDD specification package. Use when a user asks to split specifications into agent prompts or handoff prompts; read .sdd-agentic-flow/config.yml first and do not implement the work.
metadata:
  version: 4.1.0
  pack: planning
extends: saf-create-spec
requires: [config, spec-package]
consumes: [domain-glossary, project-context]
produces: [task-prompts]
baseline: [tlc-spec-driven, tdd]
compatible_with: [full, planning]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'prompts.md present with a paste-ready prompt for every task in tasks.md; no ambiguous task boundary'
  blocking_conditions: [missing_spec_package, ambiguous_task_boundaries]
  evidence_required: [prompts.md]
---

# Create SDD Implementation Prompts

## When to use

Use after an SDD specification package is ready and the user needs bounded implementation prompts for one or more tasks. Read [spec lifecycle](../sdd-agentic-flow-shared/references/spec-lifecycle.md): resolve one package; load this skill's existing Inputs only.

## When not to use

Do not use to create a specification from scratch, execute implementation, make repository changes outside prompt artifacts, or guess missing requirements. Use `saf-create-spec` first when the specification is incomplete.

## Inputs

- `.sdd-agentic-flow/config.yml`.
- A validated specification package and its acceptance criteria.
- Optional task ordering, ownership boundaries, and target agent constraints.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first to locate the specification package and configured prompt output location. If it is missing, ask the user to run `/saf-setup` or `npx sdd-agentic-flow init`. Resolve **one** package; load this skill's existing Inputs/Workflow list only. Related slugs only if named or requested (one hop). Do not glob sibling `spec.md`.
2. Read `../sdd-agentic-flow-shared/references/tlc-baseline.md` to preserve lifecycle gates and validation expectations.
3. Read `../sdd-agentic-flow-shared/references/tdd-baseline.md`, `../sdd-agentic-flow-shared/references/task-slicing.md`, `../sdd-agentic-flow-shared/references/workflow-safety.md`, and `../sdd-agentic-flow-shared/references/engineering-principles.md` before producing prompts.
4. Read `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md` when they exist.
5. Generate one prompt per Task, trace each to a bounded set of requirements and acceptance criteria, and save prompts to the configured location or `.sdd-agentic-flow/prompts`.
6. Prefer independently verifiable vertical slices. Record explicit dependencies, public seams, and any justified horizontal slice or expand-contract strategy.
7. For code tasks, require behavior, contractual seam (field label: `Public seam`), test strategy, Expected RED command (diagnostic; `n/a — not used as proof` is valid; do not fabricate), Expected GREEN command (passing-sensor command(s)), refactor scope, and TDD limitations. Copy **Requirement anchors** from `tasks.md` into each task prompt; never conflate anchors with task-order Dependencies.
8. Write self-contained prompts with scope, repository evidence to inspect, allowed files, explicit non-goals, implementation steps, and proportionate validation commands. Copy spec-derived expected outcomes into each prompt. When work intent is **bugfix**, also copy **unchanged behavior** and the regression / reproduction sensors from the spec. Do not invite the implementer to derive expected from the implementation. Require the implementer to search existing patterns, prefer modifying existing files, and keep the complexity budget. Do not dump `engineering-principles.md` into every prompt.
9. Verify every prompt references local paths, contains no private context or secrets, and collectively covers the requested criteria without overlapping ownership.

## Safety

- Generate text artifacts only; do not execute prompts, install dependencies, use the network, or change repository/global defaults.
- Do not include secrets, personal data, private conversation context, or unsupported claims.
- Keep instructions repository-local and flag any step requiring elevated access, external coordination, or destructive action for the user.
- Follow `../sdd-agentic-flow-shared/references/workflow-safety.md` for safety boundaries.
- Do not invite the implementer to derive expected outcomes from the code.

## Output

Return the prompt artifact paths plus a compact mapping of prompt to requirements, owned files, dependencies, and validation expected from the implementer.

## Autonomy

Supports `manual`, `supervised`, and `autonomous` autonomy levels (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`). In `autonomous` mode, advancing to `saf-implement` or `saf-implement-multi` requires prompts.md present with a paste-ready prompt for every task and no ambiguous task boundary; missing evidence blocks the advance and returns control to the human. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
