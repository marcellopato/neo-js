---
name: saf-create-spec
description: Create or update a repository-local, evidence-based SDD specification package, either from a requested outcome or from existing, undocumented code. Use when a user asks to turn a feature request into requirements, acceptance criteria, design decisions, or implementation-ready specifications, or asks to document/formalize behavior that already exists in the codebase with no source item to start from; read .sdd-agentic-flow/config.yml before producing artifacts.
metadata:
  version: 4.1.0
  pack: core
extends: null
requires: [config, source-item]
consumes: [domain-glossary, project-context]
produces: [spec-package]
baseline: [tlc-spec-driven]
compatible_with: [core, full, github, local-files, planning]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'spec.md and design.md present with no unresolved Unknown finding blocking an acceptance criterion'
  blocking_conditions: [missing_spec, inconsistent_design, unspecified_requirements]
  evidence_required: [spec.md, design.md]
---

# Create SDD Specifications

## When to use

Use when a feature, change, bug fix, or technical initiative needs an implementation-ready SDD specification package — whether it starts from a requested outcome (**source-item mode**) or from code that already exists in the repository with no prior spec and no requested outcome to start from (**existing-code mode**). Read [spec lifecycle](../sdd-agentic-flow-shared/references/spec-lifecycle.md) for new vs same slug, optional `Lifecycle:` / `Extends:` / `Supersedes:`, and the do-not-glob rule.

## When not to use

Do not use for direct implementation, a casual explanation, or an unscoped brainstorming request. Do not proceed without repository-local configuration; use `saf-setup` first.

## Inputs

- **Source-item mode:** the requested outcome and known constraints.
- **Existing-code mode:** an explicit **scope** — the specific module, feature, package, directory, or bounded area to reverse-engineer, named by the user. Never proceed against an unstated or whole-repository scope — ask the user to name a bounded area first.
- `.sdd-agentic-flow/config.yml`.
- Relevant repository evidence: code, tests, existing decisions, and prior SDD artifacts (within the stated scope, in existing-code mode).

## Workflow

1. Determine the mode. If the user provides a requested outcome, ticket, or feature request, use **source-item mode**. If the user asks to document or formalize behavior that already exists in the code with no prior spec and no requested outcome, use **existing-code mode** and confirm the user has named an explicit scope — a specific module, feature, or bounded area, not the whole repository — before continuing; ask for one if it is missing or too broad.
2. Read `.sdd-agentic-flow/config.yml` and use its artifact paths, naming rules, and configured scope. If it is missing, ask the user to run `/saf-setup` or `npx sdd-agentic-flow init`.
3. Read `../sdd-agentic-flow-shared/references/tlc-baseline.md` to apply the common lifecycle and required decision points. Read `workflow.feature_profile` from `.sdd-agentic-flow/config.yml` and apply `../sdd-agentic-flow-shared/references/feature-profiles.md` guidance to scope the package's depth. Read `../sdd-agentic-flow-shared/references/work-types.md`. Infer **work intent** (`feature` / `bugfix` / `refactor` / `investigation` / `maintenance`) from the request or source item and state it in prose near the top of `spec.md` or `context.md` (example: `Work intent: bugfix`). Work intent is not a config key, not a CLI `--type`, and not a fifth `feature_profile`. Apply the matching content contract from `work-types.md` inside existing headers — do not add `## Unchanged behavior` or `## System Invariants`, and do not create `bugfix.md`.
4. Read `../sdd-agentic-flow-shared/references/task-slicing.md`, `../sdd-agentic-flow-shared/references/artifact-contracts.md`, `../sdd-agentic-flow-shared/references/workflow-safety.md`, and `../sdd-agentic-flow-shared/references/spec-lifecycle.md` before handling inputs or writing artifacts. New slug → new folder. Same slug → identify overwrite and wait for an explicit update request (already in Safety). If the work extends or supersedes another package, record canonical `Extends:` / `Supersedes:` in `context.md`. Optional `Lifecycle: draft` or `active` in `context.md` (not a new H2). Do not glob sibling `spec.md` files except to detect slug collision or an explicit relation. Read `../sdd-agentic-flow-shared/references/engineering-principles.md` so `design.md` follows existing architecture. If the existing architecture is flawed, record the tension; do not silently specify a competing architecture.
5. Read `.sdd-agentic-flow/context/project-context.md` when it exists; treat it as read-only discovered output. In source-item mode, also read `.sdd-agentic-flow/context/domain-glossary.md` when it exists; propose or create it only with explicit authorization and a source or uncertainty note for every term.
6. Inspect the evidence, applying `../sdd-agentic-flow-shared/references/evidence-standard.md`:
   - **Source-item mode:** inspect only evidence needed to state the current behavior, desired behavior, constraints, risks, and acceptance criteria. Mark unknowns as open questions rather than inventing facts.
   - **Existing-code mode:** inspect the named code, its tests, and its call sites within the confirmed scope. Classify every finding as **Observed** (directly shown by code or a passing test), **Inferred** (a reasonable reading of the code that no test directly confirms), or **Unknown** (a gap neither the code nor its tests answer). Never present an Inferred or Unknown finding as Observed.
7. Create the artifacts:
   - **Source-item mode:** create exactly `context.md`, `spec.md`, `design.md`, and `tasks.md`; never create `validation.md`. Keep requirements traceable to evidence, give each acceptance criterion an **observable expected outcome** (status, code, persisted state, or invariant), and slice code tasks vertically where practical. Optional invariant sentences live **inside** existing requirement/AC text (`INV-…` allowed). Do not add a required `## Invariants` header. When work intent is **bugfix** (any `feature_profile`, not only `small_fix`), include current broken behavior, a **reproduction sensor** that fails on current code, expected fixed behavior, **unchanged behavior** with regression sensors, root cause, and fix boundary — still inside existing headers.
   - **Existing-code mode:** create exactly `context.md`, `spec.md`, and `design.md`, labeling every requirement and decision Observed, Inferred, or Unknown; only create `tasks.md` if the user confirms follow-up work is needed. Never create `validation.md`.
8. **Spec analysis** (requirement analysis): after drafting requirements and **before** treating the spec as ready, inspect the set for ambiguity (divergent implementations), contradiction (collectively impossible), unstated assumptions, missing edge cases / failure modes, unverifiable acceptance criteria, and impacted modules / call sites (from the same inspection already used for evidence — not a mandatory `git grep` ritual). This extends, and does not replace, Observed/Inferred/Unknown (existing-code) and Known/Assumed/Unknown (brainstorm). Skip this pass **only** when `feature_profile` is `small_fix` **and** the work is well-understood; record the skip in the spec or output so it is not silent. Do not present a skip as if analysis ran. No 15th skill; no Analyze CLI.
9. **SPEC-Q completion gate** (v4): before treating the package implementation-ready, verify SPEC-Q1–SPEC-Q11 — critical requirements observable; no unresolved consequential ambiguity; observable acceptance criteria; explicit scope/review boundary; explicit task dependencies; identifiable contractual seams/sensors; reconciled applicable invariants; no material spec/design/tasks contradiction; intentional optional-artifact omissions; task completion criteria evidence-backed or deterministically derivable; known consequential human-judgment boundaries explicit. Structural facts (headers, REQ-* IDs, resolvable dependencies, acyclic task graph, requirement anchors) may be checked deterministically; semantic sufficiency remains an explicit skill/human decision.
10. Check internal links, paths, and consistency with existing artifacts. In source-item mode, summarize unresolved decisions. In existing-code mode, summarize Observed behavior, Inferred behavior, Unknown/open questions, and any gaps between observed behavior and observed tests, so the user can confirm or correct each Inferred and Unknown item before it is relied on.

## Safety

- Do not use private conversation context as specification evidence or copy secrets into artifacts.
- Do not access networks, install dependencies, or modify application code, infrastructure, or defaults.
- Preserve existing artifacts unless the user explicitly requests an update; identify any overwrite before it occurs.
- In existing-code mode, never present Inferred or Unknown findings as Observed, confirmed requirements; label every finding Observed, Inferred, or Unknown.
- Apply `../sdd-agentic-flow-shared/references/workflow-safety.md` for data handling and confirmation requirements.

## Output

Return the created or updated artifact paths, evidence consulted, and: in source-item mode, a concise scope and acceptance-criteria summary plus open questions or decisions required before implementation; in existing-code mode, a concise summary of findings labeled Observed, Inferred, or Unknown, so the reader can distinguish confirmed behavior from inference and unresolved gaps at a glance.

## Autonomy

Supports `manual`, `supervised`, and `autonomous` autonomy levels (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`). In `autonomous` mode, advancing to `saf-create-prompts` or `saf-implement` requires spec.md and design.md present with no unresolved Unknown finding blocking an acceptance criterion; an inconsistent design or missing evidence blocks the advance and returns control to the human. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
