# Autonomy guardrails

`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml` is a **new axis orthogonal to** `workflow.execution_mode`
(`plan`/`guided`/`apply`/`review`/`full`, see [execution modes](../../docs/execution-modes.md)).
`execution_mode` answers "what is a skill authorized to do"; `autonomy_level` answers "does a
skill need a human between it and the next one." Neither replaces the other, and neither changes
behavior unless a project explicitly opts in. The default is `manual`, the same fully-supervised
behavior every skill already had before this file existed.

## The three levels

- **`manual`** (default): every skill returns control completely. Nothing advances
  automatically, even when a skill reports success. Transition policy: `stop`.
- **`supervised`**: a skill executes, reports its evidence, and offers an explicit
  "continue to `<next skill>`?" recommendation; the human decides. Transition policy: `confirm`.
- **`autonomous`**: a skill executes and advances to the next skill on its own, but only when
  every guardrail below passes. Any guardrail failure blocks the advance and hands control back
  to the human, the same as `manual` would. Transition policy: `continue`, gated.

## `execution_mode` × `autonomy_level` compatibility

| execution_mode | `manual` | `supervised` | `autonomous` |
| --- | --- | --- | --- |
| `plan` | valid (default) | valid, uncommon | **invalid** |
| `guided` | valid | valid (default) | **invalid** |
| `apply` | valid | valid | valid (default) |
| `review` | valid (default) | valid | valid, uncommon |
| `full` | valid | valid | valid (default) |

`plan` and `guided` never combine with `autonomous`. A plan-only workflow has nothing to
auto-advance into, and step-by-step confirmation is the entire point of `guided`. Pairing it with
unattended advance contradicts `guided`. `doctor --autonomy` flags either combination as `FAIL`.

## The 7 guardrails

Every one of the seven is deterministic and auditable; a single failure blocks the advance. An
agent operating in `autonomy_level: autonomous` re-checks all seven before treating a skill's
completion as license to invoke the next skill.

1. **Completion status** — the skill reports `PASS`/`DONE`, not `IN_PROGRESS`, `UNKNOWN`, or
   `FAIL`.
2. **Evidence validation** — every artifact the skill's `autonomy_profile.evidence_required` lists
   actually exists and is non-empty.
3. **Verification gates** — the skill's own required checks (tests, linter, spec consistency, no
   blocking findings) all pass; a skill never reports `PASS` while a required check failed.
4. **Scope boundary** — the work stayed inside the task's declared scope (files touched, lines
   changed); it did not silently expand into unrelated files or new features.
5. **Skill transition validity** — the proposed next skill is on the workflow's authorized path
   (see the main SDD flow diagram in `README.md`); a guardrail failure here blocks skipping or
   reversing a step, e.g. advancing straight from `saf-create-spec` to `saf-review-pr`.
6. **Resource sufficiency** — the configured budget (`workflow.autonomy_budget` in
   `.sdd-agentic-flow/config.yml`: `max_iterations`, `max_tokens`, `max_runtime_hours`) is not exhausted, and
   `pause_on_warning` triggers a stop, not just a warning, once remaining budget drops below 20%.
7. **Human override gate** — no `pause: true` or `stop: true` is recorded in
   `.sdd-agentic-flow/autonomy/loop-state.md`. This is the one guardrail that is not evaluated automatically by
   construction — it exists specifically so a human can halt an in-flight autonomous run by
   editing state, without needing to kill a process.

If any guardrail fails, the agent stops, records the failing guardrail and its reason in
`.sdd-agentic-flow/autonomy/loop-state.md`, and waits for a human to resolve it. The human fixes the underlying
cause and re-runs the skill, or runs `sdd-agentic-flow autonomous-resume`.

## `autonomy_profile` frontmatter

Each skill declares, in its `SKILL.md` frontmatter, which levels it supports and what a `PASS`
means for it:

```yaml
autonomy_profile:
  supported_levels: [manual, supervised, autonomous]
  auto_continue_condition: 'spec.md, design.md, and tasks.md present; no unresolved requirements'
  blocking_conditions: [missing_spec, inconsistent_design, unspecified_requirements]
  evidence_required: [spec.md, design.md, tasks.md]
```

- `supported_levels` — which of the three levels this skill can run under. A skill whose output is
  always a recommendation or explanation for a human to act on (never itself a link in the
  auto-advancing chain) omits `autonomous`.
- `auto_continue_condition` — one-line, human-readable statement of what "safe to advance
  automatically" means for this skill. Informational; the actual gate is guardrails 1–3 above.
- `blocking_conditions` — the specific failure modes that stop this skill from reporting `PASS`.
- `evidence_required` — the artifact(s) guardrail 2 checks for.

`scripts/check-skills.sh` validates that every installed skill declares `autonomy_profile` and
that `supported_levels` is a subset of `{manual, supervised, autonomous}`.

## `.sdd-agentic-flow/autonomy/loop-state.md`

The execution-state file an agent maintains while running a workflow under `supervised` or
`autonomous`. It is the "memory of the loop": an agent (or a human) can read it to resume from the
last completed skill without replaying earlier ones, and `sdd-agentic-flow context autonomy-state`
/ `sdd-agentic-flow autonomous-resume` both read and update it. Minimal shape:

```markdown
# Loop State

Execution mode: full
Autonomy level: autonomous

## Current State

- Skill: saf-check-task (completed)
- Status: PASS
- Next: saf-validate
- Guardrails: PASS
- Human override: pause=false, stop=false

## Blocker History

None.
```

An agent appends a new "Current State" block after each skill completes; it never rewrites
history, only adds to it. A human halts an autonomous run by setting `pause: true` or
`stop: true` under Human override — guardrail 7 picks that up on the next check.

The `Skill:` value is not itself the SDD flow phase — `docs/sdd-methodology.md`'s
`Phase | Typical skill` table is the existing mapping (`saf-brainstorm` through `saf-validate`) for
reading which phase (Plan/Prompt/Implement/Check/PR/Review/Fix/Validate) a given entry
corresponds to. No new field is needed to make `loop-state.md` phase-inspectable; the data already
exists, this is just where to read it.

## Scope: what autonomy governs, and what it does not

`autonomy_level` governs **skill-to-skill transitions only**. It does not grant a skill any
authority `execution_mode` does not already grant — `autonomous` never implies "skip
`no_commit_by_default`" or "ignore an explicit scope boundary." A skill running in
`autonomy_level: manual` may still call any tool, including an available MCP integration, exactly
as it always could; autonomy only changes whether the agent asks before invoking the *next skill*.
There is no orchestration engine in this CLI that executes skills on a loop — `autonomy_level` is a
contract the skills and the invoking agent honor, validated statically by `doctor --autonomy`, not
a runtime this package hosts.
