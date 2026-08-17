# Work types

Work **intent** is inferred from the user request or source item and stated in prose near the
top of `spec.md` or `context.md` (example: `Work intent: bugfix`). It is not a
`workflow.work_type` config key, not a CLI `--type`, and not a fifth `feature_profile`.

Combine inferred intent with existing `workflow.feature_profile` (how much of TLC/TDD is
invoked explicitly). Intent decides *what kind of truth* the artifacts must capture. Profile
decides *how much ceremony*. A 5-line authentication change can outrank a 500-line well-known
CRUD in rigor.

Intents (not skills, not a config enum):

```text
feature | bugfix | refactor | investigation | maintenance
```

Mandated content lives **inside** existing headers (`## Requirement {id}`, `## Acceptance
criteria`, `context.md`). Do not add required spec headers such as `## Unchanged behavior` or
`## System Invariants`. Do not create `bugfix.md`.

Skills load this file from `saf-create-spec` onward. See [feature-profiles.md](feature-profiles.md)
for the size/ceremony axis and [evidence-standard.md](evidence-standard.md) for sensors.

## Feature

Current desired behavior, acceptance criteria, optional design. Sensors for specified
behaviors (v1.14.0 / v1.15.0 evidence contract).

## Bugfix

Applies at **any** `feature_profile`, not only `small_fix`. Capture:

```text
current behavior (defect)
expected behavior
unchanged behavior  → regression sensors
root cause
fix boundary
reproduction sensor (fails on current)
```

“Fixed” without a current reproduction sensor is **false success**. “Fixed” without
**unchanged behavior** plus regression sensors is a **silent gap** on preservation.

## Refactor

Name the public/contractual seam and the **unchanged external behavior**. Require
characterization / regression sensors. No silent behavior change.

## Investigation

Questions, evidence, unknowns. Output is a findings package, not a completion claim. Must not
conclude “fixed” or write `Status: pass` / `Status: ready` on the feature.

## Maintenance

Name the blast radius. Require regression sensors for the touched surface. Ceremony follows
uncertainty (a one-line config bump vs a dependency upgrade in auth).
