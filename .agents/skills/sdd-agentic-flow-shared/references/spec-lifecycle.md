# Spec lifecycle

This file is **not a skill**, **not a baseline**, **not a CLI**, and **not a registry**. It is a shared methodology contract for *which spec package to
resolve* and *which artifacts to load* for the active operation. Existing SDD
skills still decide which workflow step to run. Do not invoke this file as a
fifteenth skill or as a substitute for `saf-route`.

Skills load this file at install time as
`../sdd-agentic-flow-shared/references/spec-lifecycle.md`.

Pointers (do not restate): [tlc-baseline.md](tlc-baseline.md) (living specs),
[evidence-standard.md](evidence-standard.md),
[artifact-contracts.md](artifact-contracts.md),
[feature-profiles.md](feature-profiles.md),
[handoff-standard.md](handoff-standard.md).

## Purpose

Feature-oriented SDD packages persist broadly. Agent context must stay
task-scoped. The working directory layout does not change.

Existence is not relevance. Resolve broadly; load narrowly.

## Layout (unchanged)

Canonical path remains:

```text
.specs/features/<slug>/
  context.md
  spec.md
  design.md      # optional per feature-profiles
  tasks.md       # optional per profile / existing-code mode
```

Optional extras already in the toolkit (`brief.md`, `explanation.md`,
`handoff.md`) stay in that folder. Do **not** require `.specs/active/` or
`.specs/archive/`. Do **not** create `validation.md` under `.specs`.

## Package resolution

When a skill needs a spec package, resolve in this order:

1. Explicit slug/path from the user or invoking workflow.
2. Task identity already present in the current task prompt/artifact.
3. Unambiguous identity in lightweight `context.md` metadata.
4. Otherwise stop and ask.

Outcomes:

```text
0 plausible packages  → ask (when the workflow requires a package)
1 unique package      → select it
2+ plausible          → HUMAN GATE; never guess
```

Directory listing is not loading bodies. Allowed for routing: directory names
under `specs.root`, and a skim of `context.md`. Not allowed by default for
discovery: **do not glob** every `spec.md` / `design.md` / `tasks.md`.

## Load rule

After resolution, load **only** the artifacts the **active skill’s
Inputs/Workflow already names**. Missing optional files are valid
(feature-profiles already skip `design.md`). Do **not** invent a second
per-skill file matrix here — that would drift from `SKILL.md`.

Related packages: load at most **one hop** when `Extends:` / `Supersedes:` is
named or the user asks. Do not recurse (`A→B` may load B; do not auto-load C
because B extends C).

`saf-route` may **list** slugs to disambiguate; listing ≠ loading bodies. It
remains a **skill** router, not a spec registry.

## Same slug vs new slug

```text
Same change / same contract being refined  → same slug  → living evolution
Materially new change                     → new slug   → flow-forward history
```

Same slug when: clarifying requirements, correcting the current spec, refining
design, adjusting tasks, or incorporating implementation discoveries **within
the same intended change**. Confirm overwrite (already in `saf-create-spec`
Safety).

New slug when: intended behavior or scope changes materially; acceptance
criteria represent a new change; the previous package was already implemented
and a new change is requested; a later attempt after an abandoned package
(unless the human explicitly elects to resume it).

Never `spec-v2/` as a naming scheme.

## Lifecycle metadata

Optional prose near the top of `context.md` or `spec.md`, same pattern as
`Work intent:`:

```text
draft | active | implemented | superseded | abandoned
```

Use **`implemented`**, not `completed`. `implemented` does **not** mean
validation PASS, correctness, human approval, or release.

Lifecycle is **descriptive, not authoritative**. It does not control routing,
context loading, validation, implementation permissions, archival,
correctness, or release readiness. Do not write `if Lifecycle == implemented:
skip`.

Do not introduce required YAML frontmatter or a required `## Lifecycle` H2.

## Relations

Optional canonical lines, preferably in `context.md`:

```text
Extends: <slug>
Supersedes: <slug>
```

Not free-form “this builds on the previous effort…”. No larger vocabulary
(`Depends-on`, `Related-to`, …) in this contract.

## Artifact authority

```text
context.md     → scope, provenance, constraints, cheap discovery
spec.md        → intended behavior / requirements / acceptance
design.md      → implementation approach
tasks.md       → execution breakdown
code + tests   → observed implementation behavior (evidence, not oracle)
Lifecycle:     → never overrides the above
```

Preserve spec/AC → task requirements → repo contracts → observed behavior as
evidence. See [evidence-standard.md](evidence-standard.md).

## Git vs filesystem

Folders answer “what were the artifacts of this change?” Git answers “how did
those files evolve?” Git history is for targeted investigation (`evidence wins
over a stale snapshot`), **not** default `git log --all -- .specs` context.

This toolkit repository gitignores `.specs/` for local dogfooding only.
Consumers should version `.specs/features/`.

## Validation does not archive

`saf-validate` may write a sanitized report under
`.sdd-agentic-flow/reports`. After PASS it **may recommend** the human set
`Lifecycle: implemented`. It never rewrites lifecycle metadata, never
moves/deletes the package, never creates `validation.md` under `.specs`.
PASS is still not a correctness verdict.

## Validated feature knowledge reconciliation

When a validated feature changes durable project truth (architecture, glossary, operational
docs, or relationships between packages), reconcile the appropriate existing project knowledge.
Do not add a global system-spec database, delta-spec engine, archive tree, or mandatory ADR folder.

## Living specs (pointer)

On drift, stop and reconcile with the human. See
[tlc-baseline.md](tlc-baseline.md). This file does not re-open that rule.

## TLC alignment

Inherit on-demand load and never-multiple-feature-specs. Do **not** copy TLC
`STATE.md`, `LESSONS.md`, Verifier runtime, or `validation.md` under `.specs`.
Per-feature pause already uses [handoff-standard.md](handoff-standard.md).

## Local vocabulary per skill

| Skill | Use |
| --- | --- |
| `saf-create-spec` | New vs same slug; optional Lifecycle + `Extends:` / `Supersedes:`; **do not glob** sibling `spec.md` except collision / explicit relation |
| `saf-create-prompts` / `saf-implement` / `saf-check-task` / `saf-explain` | Resolve one package; load that skill’s existing Inputs only |
| `saf-validate` | That feature only; recommend `implemented`; never archive; never `validation.md` under `.specs` |
| `saf-route` | List slugs + skim `context.md`; 0/1/>1 gate; do not load every `spec.md` |
