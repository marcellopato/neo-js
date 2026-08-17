# Handoff standard

`shared/templates/handoff.template.md` exists, but no skill was required to populate it.
This file states when and how a skill writes one, so continuity across a session boundary
or an agent swap does not depend on the invoking agent remembering to ask for it.

## When a skill writes `handoff.md`

A skill writes or updates `.specs/features/<feature>/handoff.md` (or the path convention
`.sdd-agentic-flow/config.yml` declares) only when work on a feature or task is paused before it reaches a
terminal state (`pass`/`ready`, per [evidence-standard.md](evidence-standard.md)'s `Status:`
field) and is likely to resume in a different session, with a different agent, or after a human
decision:

- **Session end with open work**: the invoking session is ending (context exhausted, user
  stopping) while a task or feature is not yet at a terminal `Status:`.
- **Agent handoff**: work is continuing under a different coding agent than the one that
  produced the current state.
- **Blocker requiring a human decision**: a skill stops because of a `blocked` classification,
  an unresolved `Unknown`/`Assumed` item, or a failed guardrail (see
  [autonomy-guardrails.md](autonomy-guardrails.md)) that only a human can resolve.

Do not write `handoff.md` when a skill completes with a terminal `Status:` and no open blocker.
The produced artifact (`check-report`, `validation-report`, `pr-package`) is sufficient
continuity on its own. A redundant `handoff.md` would only drift out of sync with it.

## Named feedback loop (not auto-run)

The portable cycle is implement → check (`saf-check-task`) → needs-changes back to implement
(bounded; human-gated) → validation → **human gate**. PR path remains `saf-create-pr` →
`saf-review-pr` → `saf-fix-pr`. A suggested bound (for example three check→implement cycles
then escalate) is **guidance**, not a CLI flag. This package does not auto-run that loop.
`handoff.md` is for pausing inside it, not for executing it.

## Relationship to `.sdd-agentic-flow/autonomy/loop-state.md`

`handoff.md` and `loop-state.md` serve different scopes and must not duplicate the same facts:

- `loop-state.md` (see [autonomy-guardrails.md](autonomy-guardrails.md)) is the mechanical,
  append-only execution-state ledger for one workflow run under `supervised`/`autonomous`. It records
  which skill ran, its `Status`, the proposed next skill, and guardrail results.
- `handoff.md` is the human-readable continuity note for one feature or task. It covers why the work
  matters, what is actually done, what remains open, and what a reader (human or the next
  agent) should do next.

When both exist for the same paused work, `handoff.md`'s `## Current state` and `## Blockers`
sections reference the relevant `loop-state.md` entry by skill name and timestamp instead of
restating its content. For example: "Last recorded state: `saf-implement` (completed),
guardrail 3 failed. See `.sdd-agentic-flow/autonomy/loop-state.md`." A skill running under `autonomy_level:
manual` (no `loop-state.md` in use) omits that reference and describes the state directly.

## What belongs in each `handoff.template.md` section

Non-terminal handoffs are compact projections of:

```text
goal, current unit/state, verified work by artifact reference,
unsatisfied completion criteria and last meaningful progress (non-terminal work only),
decision gates, blockers, freshness concerns, relevant paths, next typed action
```

Never duplicate full logs or evidence tables in handoff; reference check/validation reports by path.

- **Goal**: the feature or task's goal, one line, not a restatement of `spec.md` in full.
  Link to it instead.
- **Current state**: the concrete state right now: what has run, what its `Status:` was, and
  the `loop-state.md` reference above when one exists.
- **Completed work**: what is done and verified, referencing existing artifacts by path
  (`check-report`, `validation-report`) rather than duplicating their evidence.
- **Open decisions**: unresolved `Assumed`/`Unknown` items a human still needs to settle, using
  whichever classification the producing skill already applies (e.g. `saf-brainstorm`'s
  Known/Assumed/Unknown/Needs research split, or `saf-create-spec`' existing-code-mode
  Observed/Inferred/Unknown).
- **Blockers**: the specific failure or guardrail that stopped the work, in the same
  vocabulary the stopping skill already uses (evidence-standard.md's `blocked`/`inconclusive`
  or a named guardrail failure); never invent a new blocker taxonomy here.
- **Relevant artifacts**: paths only; never copy artifact content into `handoff.md`.
- **Suggested next step**: the specific skill or human action to resume with, matching
  `skill-authoring-standard.md`'s `Next recommended skill` convention.

## Who reads and writes it

Same posture as every other shared reference: the skill and the invoking agent honor this
contract. The CLI does not generate or enforce it. `sdd-agentic-flow` ships no command
that creates, updates, or reads `handoff.md`. It is plain Markdown a skill writes like any
other artifact.
