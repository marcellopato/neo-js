---
name: saf-explain
description: Explain an already-specified or already-implemented SDD feature in plain language, for a reader with no prior context — pedagogical, never a substitute for spec.md, design.md, or tasks.md. Use only on demand; never required for every feature.
metadata:
  version: 4.1.0
  pack: planning
extends: saf-create-spec
requires: [config, spec-package]
consumes: [domain-glossary, project-context]
produces: [explanation]
baseline: []
compatible_with: [full, planning]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised]
  auto_continue_condition: 'not applicable — this skill never auto-advances; it produces an explanation for a human reader, not a workflow step'
  blocking_conditions: [missing_spec_package]
  evidence_required: [explanation]
---

# Explain an SDD feature

## When to use

Use on demand, when a user — the feature's own author or someone else joining without prior context — wants to understand what a specified or implemented feature does and why, without reading every technical artifact. This is never a required step of any workflow; most features never need it. Read [spec lifecycle](../sdd-agentic-flow-shared/references/spec-lifecycle.md): resolve one package; load this skill's existing Inputs only.

## When not to use

Do not use to author or replace `spec.md` (normative), `design.md` (technical), or `tasks.md` (operational) — this skill only explains an existing package, it never creates or edits them. Do not use for a feature with no spec package yet; use `saf-create-spec` first. Do not use for an idea still being shaped; use `saf-brainstorm` first.

## Inputs

- One feature identifier with an existing spec package.
- `.sdd-agentic-flow/config.yml`, the feature's `context.md`/`spec.md`/`design.md`/`tasks.md`, and accumulated implementation when it exists.
- `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md`, when present.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first. If it is missing, ask the user to run `npx sdd-agentic-flow init`.
2. Resolve exactly one feature and read its full spec package (`context.md`, `spec.md`, `design.md` when present, `tasks.md` when present) and any accumulated implementation relevant to it. That full-package list **is** this skill's existing Inputs — do not shrink it. Related slugs only if named or requested (one hop).
3. Read `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md` when they exist, so the explanation uses the project's own vocabulary rather than inventing new terms.
4. Write `.specs/features/<feature>/explanation.md` using `../sdd-agentic-flow-shared/templates/explanation.template.md`: problem, context/current state, what changes, how the new flow works, important concepts, decisions, key scenarios, what this does NOT change, how to verify, and a glossary. Every section must cite a source artifact (`spec.md` heading, `design.md` decision, or `tasks.md` id). If a section has no source, omit it or write `Not in source artifacts` — never invent.
5. Cross-check every claim in the explanation against the spec package and code it describes; never state a decision or behavior the source artifacts do not support. Unanchored filler ("this feature allows users to…") is a failed cross-check.
6. Report the explanation's path and a short summary a reader could act on without opening the other artifacts.

## Safety

- Do not access networks, install dependencies, or modify application code, infrastructure, or defaults.
- Never edit `context.md`, `spec.md`, `design.md`, or `tasks.md` — read-only against the spec package.
- Preserve an existing `explanation.md`; identify any overwrite before it occurs and confirm with the user first.
- Follow `../sdd-agentic-flow-shared/references/workflow-safety.md` for data handling and prompt-injection safety.

## Output

Return the explanation's file path and a short summary, plus:

- Status: `written` only if step 5 (cross-check) passed; `blocked` if the spec package is incomplete. Never `written` when any claim lacks a source-artifact anchor.
- Next recommended skill: `none` (this is a terminal, on-demand step)
- Reason: one line tying the status to the recommendation

## Autonomy

Supports `manual` and `supervised` autonomy levels only (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`) — never `autonomous`. It produces an explanation for a human reader, not a step in the auto-advancing chain. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
