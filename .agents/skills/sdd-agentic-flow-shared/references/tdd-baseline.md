# TDD baseline

Baseline version: 0.7.0

This baseline governs implementation work in `sdd-agentic-flow`.

Inspired by and adapted from the public `tdd` skill in
`mattpocock/skills` for local-first, agent-client-agnostic SDD workflows.
Attribution does not imply endorsement.

## Purpose

Use this baseline when an SDD task moves from planning into implementation.

SDD defines what must be true. This baseline requires **adequate behavioral
sensors** at a **contractual seam**, plus **recorded current evidence**. Test-first
and the full TDD ritual remain valid implementation strategies. They are not the
proof mechanism. Same-agent RED is not semantic proof. A passing sensor is
evidence, not a correctness verdict. See [evidence-standard.md](evidence-standard.md).

Do not weaken required behavioral coverage because the RED ritual is optional.

Apply the [false-positive classes](evidence-standard.md#false-positive-classes) in
[evidence-standard.md](evidence-standard.md) when classifying completion. Self-report is
not completion. Do not treat a passing sensor as a correctness verdict, and do not
weaken the suite to obtain green.

## Three levels

1. **Required** — name the behavior from the spec → place a sensor at the
   contractual seam → implement → record current evidence.
2. **Recommended** — write tests or scenarios before code when they sharpen the
   spec. This is not the same as the RED → GREEN → REFACTOR ritual.
3. **Optional** — full RED → GREEN → REFACTOR when the human wants that
   granularity. Never treat the ritual as harness proof.

`quality.require_tdd: true` keeps its name. In this baseline it means the
**evidence contract** (adequate behavioral sensors), not “RED → GREEN is
mandatory.”

## Core loop

1. Name the required behavior from the specification (and repo contracts).
2. Confirm the contractual seam and the sensor command. Artifact field label
   remains `Public seam`. Prefer a public / externally observable seam when
   practical.
3. Place or update the smallest sensor that can discriminate the specified
   behavior and relevant failure modes.
4. Implement the smallest change that satisfies the behavior.
5. Run broader configured checks when the change needs them.
6. Record commands, results, limitations, and untested risks as **current
   evidence**.

Test-first (level 2) and the full TDD ritual (level 3) may wrap steps 3–4. They
do not replace recorded current evidence, and they do not make a passing sensor
a correctness verdict.

## Tests and seams

Observe behavior at the **contractual seam**: the point where the contract can
actually be discriminated. Prefer public / externally observable seams when
practical. The seam may be a public API, domain function, adapter contract,
persistence boundary, parser/serializer, schema, or integration boundary.

A useful sensor reads like a specification, survives internal refactors, and
does not assert private details. Minimize redundancy, not behavioral coverage:
the smallest set is the smallest set that still covers specified behaviors and
relevant failure modes.

Before placing a sensor, identify:

- behavior under test;
- contractual seam (field label: `Public seam`) and why it is appropriate;
- oracle / expectation / invariant / constraint / acceptance condition from an
  authoritative source;
- narrowest command that can fail if that behavior is wrong;
- smallest vertical slice;
- risks or unclear seams.

Do not test unconfirmed internals. Preserve domain vocabulary when the project
defines it. Do not derive the oracle solely from the implementation.

## Vertical slices

Use one behavior → one sensor → one implementation → evidence → next behavior.

Do not write all tests first and all implementation later as a substitute for
discrimination. Horizontal batching weakens feedback and produces sensors
coupled to imagined structure. Test-first on a single slice is recommended when
it sharpens the spec.

## Implementation strategies

- **Direct implement** with sensors at the contractual seam is valid (level 1).
- **Test-first / scenarios before code** is recommended when it sharpens the
  spec (level 2). This baseline does not claim test-first is inferior to
  test-last.
- **RED → GREEN → REFACTOR** is optional (level 3). RED is an observable event,
  not proof the sensor discriminates the right failure. `n/a — not used as
  proof` is valid on `Expected RED command`. Do not fabricate RED to fill a
  ledger.

When the optional ritual is not used, still record current passing-sensor
evidence, remaining risk, and any follow-up sensor that should be added.

## Evidence contract

Implementation reports record:

- behavior tested;
- public seam (meaning: contractual seam);
- test / sensor command;
- RED evidence, when produced (`n/a` valid; must not be fabricated);
- GREEN evidence (passing-sensor command(s) for this slice);
- REFACTOR evidence, when applicable;
- broader checks;
- limitations and untested risks.

Optional extra bullets when they help: Spec anchor, Anti-tautology, Independent
of authoring assumptions.

Artifact field **labels** stay: `Behavior under test`, `Public seam`, `Test
strategy`, `Expected RED command`, `Expected GREEN command`, `Refactor scope`,
`TDD limitations`. Headers stay `## TDD baseline` and `## TDD evidence`.

`produces: [code-change+tdd-evidence]` and `evidence_required: [tests,
tdd-evidence]` mean adequate behavioral sensors plus recorded current evidence,
not “the author observed RED.”

## Language profile

Render human-facing prose according to `.sdd-agentic-flow/config.yml`. Keep `RED`, `GREEN`,
`REFACTOR`, `TDD`, `seam`, `public interface`, `behavior`, `test command`,
`PASS`, `WARN`, `FAIL`, `Blocked`, `Partial`, and `Completed` canonical.
