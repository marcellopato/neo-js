# Skill authoring standard

Every skill in `skills/` follows the same six-section skeleton. This reference documents that
skeleton so a new skill starts from the standard instead of copying the closest existing
`SKILL.md` and hoping the shape survives. `scripts/check-skills.sh` mechanically enforces the
six section headers and the frontmatter contract fields; this document explains what belongs
inside each one.

Method inspired by the Anthropic `skill-creator` draft → test → evaluate → iterate cycle and by
general "writing for agents" principles (precision, determinism, testability). Cited here as a
method influence only. Nothing below is copied from either source; this file, like the rest of
`shared/`, is written for this project and stays agent-neutral.

## The six required sections

`## When to use`, `## When not to use`, `## Inputs`, `## Workflow`, `## Safety`, `## Output`: in
that order, with no additional top-level sections. Each one has one job:

- **`## When to use`**: the trigger condition, stated as a concrete situation, not a feature
  list. Point to the shared references the workflow depends on (baseline, safety, routing) so a
  reader knows what to load before acting.
  _Minimal example:_ "Use for one unambiguous task that is ready to implement or resume."
- **`## When not to use`**: the boundary against the nearest neighboring skill, stated by name,
  not just "don't do too much." A vague boundary is what let `saf-check-task`/`saf-validate`
  drift apart before M4 tightened it.
  _Minimal example:_ "Do not use to implement fixes, review an entire feature, approve a PR, or
  infer an ambiguous task identity."
- **`## Inputs`**: the concrete inputs the skill needs before it can start, as a short list, not
  prose. Distinguish required from optional inputs.
  _Minimal example:_ "One canonical task reference. `.sdd-agentic-flow/config.yml`, the task's SDD artifacts,
  current diff, and configured validation commands."
- **`## Workflow`**: a numbered sequence, each step an action plus its stop condition. Steps
  read shared references explicitly by path rather than restating their content (see
  [evidence-standard.md](evidence-standard.md) below for the most duplicated example of this).
  _Minimal example:_ "1. Read `.sdd-agentic-flow/config.yml` first. If it is missing, ask the user to run
  `npx sdd-agentic-flow init`; otherwise use its paths, commands, and policy."
- **`## Safety`**: what the skill will never do by default (mutate Git, publish, install, cross
  scope) and which shared safety reference governs it.
  _Minimal example:_ "This is read-only except for disposable test artifacts permitted by
  configuration. Do not change code, specs, Git, trackers, PRs, remote services, or default
  configuration."
- **`## Output`**: the structured return shape (see the `Status`/`Next recommended skill`/
  `Reason` convention below) plus whatever domain-specific fields the skill's consumers need.
  _Minimal example:_ "Return task identity, criterion-to-evidence summary, executed checks, scope
  findings, final classification, and next step."

## Output convention: Status / Next recommended skill / Reason

`saf-route` already uses a structured template for its recommendation. Every skill's
`## Output` section adopts the same closing vocabulary, so a caller (human or agent) can find
the next step without re-reading the whole report:

```text
Status: <this skill's own state vocabulary: e.g. pass / blocked / ready / converged>
Next recommended skill: <skill name, or "none">
Reason: <one line tying the status to the recommendation>
```

This is a content requirement inside the existing `## Output` section, not a seventh section.
It does not change the six-section contract that `scripts/check-skills.sh` already validates.
A skill keeps its own status vocabulary (`saf-check-task` uses `pass`/`needs changes`/`blocked`/
`inconclusive`; `saf-validate` uses `ready`/`not ready`/`blocked`/`inconclusive`; `saf-route`
itself uses a route recommendation instead of a pass/fail state). Only the three labels
(`Status`, `Next recommended skill`, `Reason`) are shared.

Use [canonical vocabulary](canonical-vocabulary.md): Skill is the public capability contract;
Instruction is durable guidance; Prompt is a concrete request. Do not call a Skill a Tool,
Hook, Agent, or Action.

## Evidence and classification

Any skill whose `## Output` includes a pass/fail/ready-style classification must ground it in
[evidence-standard.md](evidence-standard.md): a conclusion is only as good as the verifiable
evidence behind it, and evidence from a prior run is context, not proof of the current state. A
skill may keep domain-specific vocabulary for how it applies that principle (see
evidence-standard.md for the six skills that already do), but the vocabulary must never
contradict the shared principle.

## v4 capability discoverability

Every skill must make discoverable (within the six-section shape, no new frontmatter fields):

- purpose and completion semantics
- required context ([task-context-package.md](task-context-package.md))
- mutation/authorization boundary
- local outcome semantics and next admissible action ([bounded-execution.md](bounded-execution.md))

Skills that execute bounded work add goal and completion criteria; skills eligible for repeated
autonomous work additionally expose iteration/escalation semantics and stop conditions per
[system-invariants.md](system-invariants.md).
