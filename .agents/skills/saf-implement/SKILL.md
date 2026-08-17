---
name: saf-implement
description: Implement exactly one validated SDD task as the smallest tested, merge-ready increment. Use for a single task reference or explicit task implementation request; not for planning a feature or coordinating several tasks.
metadata:
  version: 4.1.0
  pack: core
extends: saf-create-prompts
requires: [config, task-identity]
consumes: [domain-glossary, project-context]
produces: [code-change+tdd-evidence]
baseline: [tlc-spec-driven, tdd]
compatible_with: [core, execution, full, github, local-files]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'tests pass, the configured linter is clean, and modified files stay within the declared task scope'
  blocking_conditions: [tests_fail, linter_errors, scope_exceeded]
  evidence_required: [tests, tdd-evidence]
---

# Implement one SDD task

## When to use

Use for one unambiguous task that is ready to implement or resume. Read [the TLC baseline](../sdd-agentic-flow-shared/references/tlc-baseline.md), [the TDD baseline](../sdd-agentic-flow-shared/references/tdd-baseline.md), [task slicing](../sdd-agentic-flow-shared/references/task-slicing.md), [feature profiles](../sdd-agentic-flow-shared/references/feature-profiles.md), [engineering principles](../sdd-agentic-flow-shared/references/engineering-principles.md), [spec lifecycle](../sdd-agentic-flow-shared/references/spec-lifecycle.md), and [safety rules](../sdd-agentic-flow-shared/references/workflow-safety.md) before acting.

## When not to use

Do not use for specification authoring, several tasks, a feature-wide validation, PR review, or a task whose identity, scope, or dependencies are ambiguous.

## Inputs

- A single canonical task reference or explicit feature and task identifiers.
- Repository SDD artifacts, relevant code, and `.sdd-agentic-flow/config.yml`.
- Optional task prompt or prior handoff, treated as supporting evidence only.

## Workflow

1. Read `.sdd-agentic-flow/config.yml` first. If it is missing, ask the user to run `/saf-setup` or `npx sdd-agentic-flow init`; otherwise use its paths, commands, and policy.
2. Read `.sdd-agentic-flow/context/project-context.md` and `.sdd-agentic-flow/context/domain-glossary.md` when they exist. Read `workflow.feature_profile` from `.sdd-agentic-flow/config.yml` and apply feature-profile guidance for evidence rigor. Resolve exactly one package, then exactly one task from the configured SDD source. Load the [Task Context Package](../sdd-agentic-flow-shared/references/task-context-package.md) minimum context. Resolve bounded goal, completion criteria, constraints and applicable [decision gates](../sdd-agentic-flow-shared/references/decision-gates.md) before mutation per [bounded-execution.md](../sdd-agentic-flow-shared/references/bounded-execution.md). Load this skill's existing Inputs/Workflow list only; related slugs only if named or requested (one hop). Confirm its acceptance criteria, requirement anchors, dependencies, allowed scope, and current implementation state.
3. Inspect callers and existing patterns before editing. Stop if the work requires a spec change, sibling task, unsafe environment, or unresolved conflict. Specifications are **living** control artifacts: if you find spec drift, stop and reconcile the spec with the human. Do not silently implement a “better” requirement. Do not silently rewrite the spec to match the code.
4. Apply `../sdd-agentic-flow-shared/references/engineering-principles.md` before editing. Search existing patterns, prefer modifying an existing file, and keep the complexity budget. Do not add a competing architecture, new dependency, or new convention without confirmation (decision path step 5).
5. Identify the required behavior from the spec, the contractual seam (field label: `Public seam`; prefer public/observable when practical), the sensor, and the oracle/acceptance condition from spec, repo contracts, or configured gates — never solely from the implementation. Stop when the seam is unclear. Stay inside the fix boundary; do not expand into **unchanged behavior**. For bugfix or refactor intent, record regression sensors. Do not complete an **investigation** as a fix (`Status: pass` on findings is forbidden).
6. Use one vertical slice at a time: name the behavior, place a sensor at the contractual seam, implement the smallest change, and record executed **current** evidence. Test-first is recommended when it sharpens the spec. Full RED → GREEN → REFACTOR is optional and is never harness proof. Do not fabricate RED. Do not weaken required behavioral coverage because the ritual is optional. Do not complete on self-assessment. Do not achieve green by suite weakening (deleting, skipping, or narrowing tests that encoded the AC). The oracle stays the spec-derived expected outcomes.
7. Apply `../sdd-agentic-flow-shared/references/evidence-standard.md`. Record commands, results, limitations, and untested risks. A passing sensor is evidence, not a correctness verdict. Do not claim done because the conversation feels finished.
8. Report TDD evidence, changed files, checks, remaining risks, and the next SDD step. Do not commit, push, open a PR, or update external trackers unless the user separately asks.

## Safety

Preserve unrelated and pre-existing changes. Keep credentials, personal data, and local paths out of output. Do not mutate production, remote services, tracker state, Git history, or repository configuration by default. Do not complete on self-assessment. Do not perform suite weakening to obtain green.

## Output

Return the resolved task, outcome (`implemented`, `partial`, `blocked`, or `no changes required`), concise evidence, validation results, and recommended next step. Terminal output is an **implementation candidate ready for verification**, never its own final verification verdict. You may report another bounded attempt as admissible only while evidence shows semantic progress and iteration policy permits; the host decides whether that attempt runs. When work pauses before a terminal outcome — session end, an agent swap, or a blocker only a human can resolve — write or update `handoff.md` per `../sdd-agentic-flow-shared/references/handoff-standard.md`.

## Autonomy

Supports `manual`, `supervised`, and `autonomous` autonomy levels (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`). In `autonomous` mode, advancing to `saf-check-task` requires tests passing, the configured linter clean, and modified files staying within the declared task scope; a failure or a scope violation blocks the advance and returns control to the human. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
