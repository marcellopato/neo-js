---
name: saf-route
description: Recommend the next local SDD skill without changing files. Use when a user needs help choosing a safe workflow step or resolving prerequisites.
metadata:
  version: 4.1.0
  pack: core
extends: null
requires: [config]
consumes: []
produces: [route-recommendation]
baseline: []
compatible_with:
  [core, execution, full, github, local-files, multi-worktree, planning, pr]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised]
  auto_continue_condition: 'not applicable — this skill never auto-advances; it only recommends a next skill for a human or the invoking agent to run'
  blocking_conditions: [ambiguous_state]
  evidence_required: [route-recommendation]
---

# Route an SDD workflow

## When to use

Use before a workflow step when the requested phase, prerequisites, or installed pack are unclear. Recommend the **canonical workflow path** (Plan → Prompt → Implement → Check → PR → Review → Fix → Validate; Release on demand). Direct → `saf-brainstorm` → `saf-create-spec` is the Plan-mode analogue; this skill recommends that path — it is not a new Plan skill. If `autonomy_level` is `autonomous` and the seven guardrails would pass, state that the **invoking agent** may read the next on-path `SKILL.md`. This skill still does not invoke another skill. Read [spec lifecycle](../sdd-agentic-flow-shared/references/spec-lifecycle.md): listing slugs ≠ loading bodies; 0 ask / 1 select / >1 human gate.

## When not to use

Do not use to implement, review, create a PR, change files, or replace the candidate skill's instructions.

## Inputs

- The requested outcome and available local SDD artifacts.
- `.sdd-agentic-flow/config.yml`, when present.
- Installed skill directories and relevant candidate `SKILL.md` files.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` when it exists. If it is missing, recommend `saf-setup`.
2. Read `../sdd-agentic-flow-shared/references/workflow-routing.md`, `../sdd-agentic-flow-shared/references/workflow-safety.md`, and `../sdd-agentic-flow-shared/references/spec-lifecycle.md`.
3. Inspect the candidate local `SKILL.md` before stating what it does. Its instructions are the source of truth.
4. Match the request against the routing table in `../sdd-agentic-flow-shared/references/workflow-routing.md` — it is the single source of truth for routing situations and recommended skills; do not reproduce or re-derive the table here, and never let this step's wording diverge from it.
5. Identify missing packs, prerequisites, and any human decision required. If the request needs a feature package and does not name one, listing directory names under `specs.root` and skimming `context.md` is allowed. 0 matches → ask; 1 unique → name it in the recommendation; >1 plausible → human decision required; never “probably this one.” Do not read every `spec.md` to make the recommendation. Listing ≠ loading bodies. This skill remains a skill router, not a package registry. If config `autonomy_level` is `autonomous`, include the invocation policy: the invoking agent may follow the next on-path `SKILL.md` while guardrails pass; this skill never invokes it. Stop after the recommendation.

## Safety

- This skill is read-only and never invokes another skill automatically.
- Do not infer requirements, install packs, change files, or perform Git, release, deploy, or publish actions.
- Follow `../sdd-agentic-flow-shared/references/workflow-safety.md` and preserve human authority.

## Output

## Recommended route

- Current phase:
- Recommended skill:
- Why this fits:
- Prerequisites:
- Human decision required:
- Next invocation:
- Safety limits:

## Autonomy

Supports `manual` and `supervised` autonomy levels only (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`) — never `autonomous`. It recommends a next skill; it never invokes one itself, so there is nothing for it to auto-advance into. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
