---
name: saf-brainstorm
description: Explore a vague idea into a converged, spec-ready problem statement, or shape a solution once the problem is already clear. Use when a user has an idea that is not yet ready for saf-create-spec — a fuzzy goal without a defined problem, or a clear problem without a decided approach; never produces spec.md, design.md, or tasks.md directly.
metadata:
  version: 4.1.0
  pack: planning
extends: null
requires: [config]
consumes: [domain-glossary, project-context]
produces: [spec-ready-brief]
baseline: []
compatible_with: [full, planning]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised]
  auto_continue_condition: 'not applicable — this skill never auto-advances; convergence on a spec-ready brief is a human judgment call, not a guardrail a skill can self-certify'
  blocking_conditions: [unresolved_unknowns, no_convergence]
  evidence_required: [spec-ready-brief]
---

# Brainstorm an idea toward spec-ready

## When to use

Use when a user has an idea that is not yet ready for `saf-create-spec` — either the problem itself is still vague ("improve X" with no defined problem), or the problem is clear but the solution approach is not decided. Read [safety rules](../sdd-agentic-flow-shared/references/workflow-safety.md) and [action vocabulary](../sdd-agentic-flow-shared/references/action-vocabulary.md) before acting. Direct → brainstorm → specs is the Plan-mode analogue. This skill is not a new Plan skill.

## When not to use

Do not use to write `spec.md`, `design.md`, or `tasks.md` directly — that is always `saf-create-spec`'s job, and this skill only ever hands off to it. Do not use once the problem and approach are already decided; go straight to `saf-create-spec`. Do not use for a single ready task (`saf-implement`) or an already-specified feature that just needs explaining (`saf-explain`). Do not become a new Plan skill.

## Inputs

- The user's idea, in whatever shape it currently exists — a sentence, a complaint, a rough goal.
- `.sdd-agentic-flow/config.yml`, when present.
- `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md`, when present.
- Relevant existing code or docs the idea touches.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first. If it is missing, tell the user to run `npx sdd-agentic-flow init` before a brief can be filed under `.specs/features/`; the conversation can still continue without it.
2. Read `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md` when they exist, and inspect the code or docs the idea touches, so the questions asked next never repeat what the repository already answers.
3. Determine the mode from the idea's current clarity, and re-evaluate it at every turn — a design conversation can reveal a hidden requirements gap that sends it back to exploratory:
   - **Exploratory mode** — the problem itself is not yet defined. Ask one systematic question at a time, only for what inspection could not already answer. Do not advance to solution design until the problem, its constraints, and why it matters are clear.
   - **Design mode** — the problem is clear but the approach is not. Explore alternatives, challenge implicit assumptions, and propose a small throwaway prototype only when the uncertainty is about implementation feasibility, never about requirements.
4. Track state as `exploring` while the problem (and, in design mode, the approach) has not yet converged, `converged` once it has, or `abandoned` if the user drops the idea during the conversation.
5. On convergence, write a short brief to `.specs/features/<feature>/brief.md` (or the path convention `.sdd-agentic-flow/config.yml` declares), capturing the problem, why it matters, constraints, the decided approach at a level a specification can start from, and open questions worth flagging to `saf-create-spec`. Never write `spec.md`, `design.md`, or `tasks.md` — that step is always delegated.
6. Before handing off, split the brief's content explicitly into **Known** (confirmed by inspection or an explicit user statement — the brainstorm-stage counterpart to `saf-create-spec`' existing-code-mode **Observed**), **Assumed** (a reasonable default neither inspection nor the user has confirmed — the counterpart to **Inferred**), **Unknown** (a real gap the conversation never closed), and **Needs research** (a specific, actionable question `saf-create-spec` should investigate rather than guess). Never present an Assumed or Unknown item as Known.
7. Report the brief's path and recommend `saf-create-spec` as the next step.

## Safety

- Do not access networks, install dependencies, or modify application code, infrastructure, or defaults.
- Do not create `.specs/features/<feature>/brief.md` before the idea actually reaches `converged` — a half-formed idea stays in conversation, not in a file.
- Preserve existing artifacts; never overwrite an existing brief or spec package without explicit confirmation.
- Follow `../sdd-agentic-flow-shared/references/workflow-safety.md` for data handling and prompt-injection safety when the idea references external content (tickets, docs, comments).

## Output

Return the current mode, a short summary of the problem/approach discussed so far, and:

- Status: `exploring` / `converged` / `abandoned`
- Next recommended skill: `saf-create-spec` when `converged`; `none` otherwise
- Reason: one line tying the status to the recommendation

When `converged`, also return the brief's file path, the Known/Assumed/Unknown/Needs research split, and the open questions left for `saf-create-spec` to resolve.

## Autonomy

Supports `manual` and `supervised` autonomy levels only (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`) — never `autonomous`. Whether an idea has converged into a spec-ready brief is a human judgment call. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
