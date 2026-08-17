---
name: saf-implement-multi
description: Implement multiple SDD tasks using dependency-aware waves, isolated Git worktrees, and concurrent workers when safe and authorized. Use for multi-task implementation; use saf-implement for exactly one task.
metadata:
  version: 4.1.0
  pack: multi-worktree
extends: saf-create-prompts
requires: [config, spec-package]
consumes: [domain-glossary, project-context]
produces: [execution-plan, multi-task-evidence]
baseline: [tlc-spec-driven, tdd]
compatible_with: [execution, full, multi-worktree]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'execution-plan.md and multi-task evidence are present, the task dependency graph is acyclic, and every next-wave dependency and isolation boundary is satisfied'
  blocking_conditions: [circular_task_dependencies, unscoped_worktrees]
  evidence_required: [execution-plan.md]
---

# Implement multiple SDD tasks

## When to use

Use when a feature has multiple explicitly selected tasks that must be planned and implemented as dependency-aware waves. Use `saf-implement` for exactly one task.
Read the [TLC baseline](../sdd-agentic-flow-shared/references/tlc-baseline.md),
[TDD baseline](../sdd-agentic-flow-shared/references/tdd-baseline.md),
[engineering principles](../sdd-agentic-flow-shared/references/engineering-principles.md),
[handoff standard](../sdd-agentic-flow-shared/references/handoff-standard.md),
[task slicing](../sdd-agentic-flow-shared/references/task-slicing.md), and
[workflow safety rules](../sdd-agentic-flow-shared/references/workflow-safety.md) before acting.

## When not to use

Do not use for one task, vague feature requests, specification creation, PR work, or when dependencies, task identities, or authorization cannot be resolved.

## Inputs

- One feature identifier and optional explicit task subset.
- `.sdd-agentic-flow/config.yml`, feature SDD artifacts, and repository state.
- User-approved concurrency/worktree constraints when implementation orchestration is requested.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first; if it is missing, ask the user to run `/saf-setup` or `npx sdd-agentic-flow init`.
2. Read `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md` when they exist. Resolve one feature, enumerate tasks, and build a candidate dependency-wave grouping from SDD evidence. Mark ambiguous or externally blocked tasks instead of guessing. The documented chain is: tasks → dependencies → **DAG** (must be **acyclic**) → **waves** (independent tasks in a wave) → parallel worktrees only with explicit user authorization. See `../sdd-agentic-flow-shared/references/worktree-orchestration.md`. Do not add a runtime scheduler.
3. Before recommending that any two tasks run in parallel, analyze whether they are genuinely independent: check for files either task writes that the other also touches, shared contracts or types, shared runtime or test state, and any ordering the tasks' own evidence implies even if not stated as a formal dependency. Only place tasks in the same parallel wave when this analysis confirms real independence; when it does not, keep them sequential regardless of what the candidate grouping in step 2 suggested. This is the analysis the worktree-isolation rule in `## Safety` depends on — decide eligibility here, do not restate the rule itself.
4. Write `execution-plan.md` with waves, ownership, paths, sensors, and integration boundary. In `plan`/`guided` mode stop before Git mutations. In `apply`/`full`, require explicit authorization before creating worktrees or changing code.
5. Plan each ready task as an independently verifiable vertical slice with a contractual seam (field label: `Public seam`), targeted sensor command, and evidence owner. Justify horizontal work explicitly. Expected RED is a diagnostic sensor hint (`n/a — not used as proof` is valid); do not instruct faking RED.
6. Execute every ready wave through `saf-implement`, once per task. Concurrent work requires isolated owned worktrees; otherwise execute the wave sequentially. Run `saf-check-task` for each completed task before allowing dependent work to proceed. After each wave barrier: collect task evidence, evaluate completion criteria and semantic progress, identify stalled work (`stalled-progress` reason — not a second durable state), evaluate shared changes, re-check affected stale evidence, resolve decision gates, and unlock only legitimate dependent work. Record per-task ledger fields: ID, bounded goal/criteria reference, wave, owner, dependencies, path/worktree boundary, execution state (`planned`, `ready`, `running`, `implemented-isolated`, `checked`, `integration-required`, `integrated`, `blocked`, `failed`, `skipped`, `no-change`), check-report reference/status, freshness, integration requirement, blocker/gate, last meaningful progress, next admissible action. A worktree result is never `integrated` until separately authorized integration. Stop at blockers. Do not treat orchestration completion as feature validation or merge readiness.
7. Collect `multi-task-evidence` summarizing the ledger. Stop at blockers.

## Safety

Never share a mutable worktree between concurrent tasks. Never create branches or worktrees without explicit authorization. Never commit, merge, cherry-pick, push, delete a worktree, or discard uncommitted changes implicitly. Preserve existing changes and stop on unknown mutable-worktree state.

## Output

Return feature identity, dependency waves, per-task status, blockers, execution-plan and multi-task-evidence paths, integration state, and next safe action.

## Autonomy

Supports `manual`, `supervised`, and `autonomous` autonomy levels (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`). In `autonomous` mode, advancing to delegated `saf-implement` runs requires execution-plan.md present, an acyclic dependency graph, and a declared worktree/scope boundary per task; a circular dependency or unscoped worktree blocks the advance. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
