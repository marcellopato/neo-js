# Evidence standard

Six skills restated this principle in slightly different sentences. That drift created real
maintenance cost. This file is the single generic statement; each consuming skill keeps only the
domain-specific vocabulary listed below and references this file for the shared rule.

This file is also the canonical **operational contract** for sensors, evidence, verification,
and decision (v1.14.0). Do not collapse those four terms. v1.15.0 adds the false-positive
catalog, requirement coverage mapping, and evidence strength ladder on top of that contract
without changing the four terms or the Status enum.

## The principle

- A claim of completion, correctness, or readiness is valid only when it is backed by evidence
  gathered during the current check: a real command, its real output, its real exit code.
- Evidence from a prior run is context, not proof. State can change between runs. A check that
  reuses a stale result without re-running it is not a check.
- Never invent a command result, a CI status, or a test outcome. If a check was not run, say so
  and say why, rather than presenting an assumed or expected result as observed.
- When evidence is missing, incomplete, or contradictory, the classification reflects that gap
  (`blocked`, `inconclusive`, `needs changes`). Missing evidence is never silently upgraded to a
  pass.
- A passing sensor result is **evidence**, not a correctness verdict. The human decision uses
  the existing Status values. Evidence establishes confidence about specified properties. It
  does not establish complete correctness unless the specification and verification boundary
  justify that conclusion.

## Vocabulary

| Term | Meaning | Example |
| --- | --- | --- |
| **Sensor** | The verification mechanism | test, typecheck, lint, schema validator, recorded command |
| **Evidence** | The observable result the sensor produced | `pnpm test` / exit 0 / 37 passed |
| **Verification** | Interpreting evidence against a requirement | R-12 → sensor S-03 → current PASS → adequate |
| **Decision** | Human conclusion using existing Status values | `ready` / `not ready` / `blocked` / `inconclusive` |

A passing sensor is not a decision. A decision without current adequate evidence is invalid.

## Sensor

An executable or mechanically observable check about a required property. Examples (not a
mandatory catalog): behavior tests, integration/contract checks, typecheck, lint, schema/API
checks, recorded command + exit status.

**Selection:** smallest applicable set that can **discriminate** the specified behaviors and
relevant failure modes.

**Minimize redundancy, not behavioral coverage.** “Smallest” does not mean fewest tests
mechanically; it means the smallest set that provides adequate coverage of the specified
behaviors and relevant failure modes.

Derive sensors from spec, repo contracts, configured gates, feature profile, then task. Mark
others inapplicable. Do not invent sensors to fill a checklist. Do not drop required behaviors
to look “minimal.”

```text
spec → required behavior → contractual seam → sensor
```

## Sensor taxonomy

Methodology only — **which class of sensor is appropriate**, not six engines this package
ships. Execution remains repository-provided (pytest, vitest, fast-check, pact, typecheck,
lint, …). Property-based testing is a **class of evidence**, not a product claim; weak
properties can still pass. Differential / mutation is a later, costlier class; it is not
implemented here.

```text
Evidence sensors
├── Example-based     (specific scenarios)
├── Property-based    (invariants over input spaces)  — class, not engine
├── Contract-based    (API / schema / types)
├── Static            (typecheck / lint / analysis)
├── Integration       (real component boundaries)
└── Differential / mutation   — later, costlier; not implemented
```

Do not add a required `## System Invariants` spec header. Optional `INV-…` sentences inside
existing requirement/AC text remain allowed (v1.15.0).

## Contractual seam

Observe the behavior at the point where the **contract can actually be discriminated**. Prefer
public / externally observable seams when practical. The seam may be a public API, domain
function, adapter contract, persistence boundary, parser/serializer, schema, or integration
boundary — whichever is the contractual surface for that requirement.

Artifact field **label** remains `Public seam` (and check-report `Seam`). Fill it with the
contractual seam, not “always the HTTP/API edge.”

## Oracle

Not every sensor has a literal expected value. The **oracle, expectation, invariant,
constraint, or acceptance condition** must be derived from an authoritative source.

Oracle kinds (examples, not a catalog): expected values; invariants; properties; constraints;
schemas; typechecking; lint rules; contract validation; metamorphic relations;
differential/reference implementations; exit status; presence/absence of a forbidden condition.

```text
Bad:  oracle = implementation(input); actual = implementation(input)
Good: oracle = spec/acceptance/invariant/repo contract; actual = implementation(input)
```

## Adequacy

A sensor is adequate only when all that apply hold:

1. Traceable to a required behavior/property.
2. Observes an appropriate **contractual seam**.
3. Oracle / expectation / invariant / constraint / acceptance condition comes from an
   authoritative source.
4. Does not derive that oracle solely from the implementation.
5. Executed against the **current** implementation state (see Freshness).
6. Result is observable and recordable (**evidence**).
7. **Can fail** if that behavior is wrong.

`test exists` is not enough. `test passed` is not enough if tautological or disconnected from
the spec.

## Anti-tautology / epistemic independence

Verification **must not** derive its oracle, expectation, invariant, or acceptance condition
solely from the implementation (includes fixtures/snapshots/validators derived from the same
code).

Independence does not require a second implementation or a second agent. It requires that the
verification oracle or acceptance condition be independently grounded in authoritative
requirements rather than inferred solely from the implementation under test.

Implementation may **produce** tests. `saf-check-task` / `saf-validate` **ground the oracle in
spec / repo contracts / configured gates** — they do not rewrite the suite as a second
implementation. Full TLC Verifier remains out of scope.

## Authority order

Authoritative requirements → derived execution instructions → observed implementation:

1. Validated specification / acceptance criteria
2. Normative repository contracts and configured gates
3. Task requirements derived from the specification
4. Implementation behavior (observed; never sole oracle)

If a task says X and a normative repo contract requires Y, the task is wrong or incomplete.
Surface that as a spec/task gap; do not let the task override the contract.

## Evidence strength ladder

The authority order above is **which source wins**. This ladder is **how strong a piece of
evidence is**. Lower rungs must not outrank higher ones. A passing typecheck is evidence about
types, not about a business acceptance criterion. GREEN is evidence only of the property that
sensor actually observes.

1. Validated specification / acceptance criteria / stated invariants
2. Normative repository contracts and configured gates
3. Human-authored or pre-existing behavioral tests that encode those ACs
4. Spec-derived executable sensors (current run)
5. Mechanical gates (typecheck, lint, build) for the properties they actually observe
6. Agent-authored tests after independent spec-grounding
7. Agent-authored tests without independent grounding
8. Agent narrative / self-report (**never sufficient**)

Self-report is not evidence. Confident closing language, chat “done”, or an LLM restatement of
the author’s write-up cannot override spec, contracts, or a current executed sensor.

## Freshness

Prior runs are context, not proof. Reports distinguish current vs historical vs not-run **in
Evidence / Limitations prose**. **No new Status enum** (v1.9.0 freeze:
`pass`/`needs changes`/`blocked`/`inconclusive` and
`ready`/`not ready`/`blocked`/`inconclusive`).

Evidence is current only when the implementation state **and** the relevant
specification/configuration inputs have not changed since the evidence was produced.

| Implementation | Spec / relevant config | Prior result |
| --- | --- | --- |
| changed | unchanged | stale |
| unchanged | changed | stale |
| unchanged | unchanged | may remain current |

## Sensor composition

Sensors are complementary. Multiple passing sensors may increase confidence when they exercise
**materially different** properties or boundaries. Duplicated sensors do not automatically
provide independent evidence.

Use [change-impact validation](change-impact-validation.md) to derive the minimum adequate
sensor set from requirements, diff, seams, repository contracts, and risk. Record omitted
higher-level sensors and why they are unnecessary.

## Gaps

No adequate sensor for a required behavior → record an evidence gap; identify the requirement;
state the limitation; map to existing Status. **Never** silent PASS. **Never** invent an
irrelevant sensor. Gap is **not** automatically `blocked`.

## Requirement coverage

Every required behavior maps to:

```text
requirement → sensor → current result
```

Record the mapping inside existing `## Evidence`. No new artifact. An uncovered requirement is
an evidence gap. A green suite with an unmapped acceptance criterion is **not** fully verified
(`silent gap` and/or `green-but-wrong`) and must not silently PASS.

## RED / PASS

RED is an observable event, not proof the test discriminates the right failure.
`n/a — not used as proof` is valid. Do not fake RED to fill a ledger.

A passing sensor result is evidence, not a correctness verdict. This includes test GREEN,
typecheck, lint, build, schema validation, command exit status, integration checks. The human
decision uses existing Status values.

Mutation testing may be named as a later, costlier sensor class. It is not implemented in this
package.

## False-positive classes

Named classes of **illegitimate completion**. A hit **forbids** `Status: pass` and
`Status: ready` and forbids treating the work as complete. Self-report is not evidence
(`self-report is not evidence`). `Status:` is a decision label, not evidence. No new
Status enum (v1.9.0 freeze stands).

These names are stable tokens for skills and `check-skills.sh`. Point at existing
[Anti-tautology / epistemic independence](#anti-tautology--epistemic-independence) rather than
rewriting it: that section already covers **Tautological oracle** and the independence rule
behind **Error propagation**.

1. **Tautological oracle** — expected derived from the implementation.
2. **Error propagation** — tests/assertions written from the same misread as the code.
3. **Green-but-wrong** — sensors pass; a spec AC is unmet or unasserted.
4. **Shallow sensor** — would still pass if the required behavior were inverted (mock-called,
   HTTP 200 only, “function exists”).
5. **Stale evidence** — prior run presented as current (named class of the
   [Freshness](#freshness) rule).
6. **Silent gap** — missing/inadequate sensor treated as PASS or quiet N/A.
7. **False success / self-assessment** — “done/functional” from conversation or confident
   closing language, not from a current executed sensor.
8. **Inherited author narrative** — check/validation trusts the implementer’s evidence section
   (or an LLM restatement of it) without re-deriving expected and re-running sensors.
9. **Suite weakening** — green achieved by deleting, skipping, or narrowing tests that encoded
   the AC.
10. **Completion theater** — `tasks.md` / loop-state / chat marked complete while check-report
    is missing, non-pass, or lists blocking gaps.

Minimum current-evidence record for PASS: command, exit status, observed result, requirement
mapping. Skepticism without a command result is still self-report.

## Local vocabulary per skill

Each skill below applies the principle above with wording specific to its own domain. The local
wording is the operative text inside that skill's `SKILL.md`. This file is the shared rule it
implements, not a replacement for it.

- **`saf-create-spec`**: classifies every finding as **Observed** (directly shown by code or a
  passing test), **Inferred** (a reasonable reading no test directly confirms), or **Unknown** (a
  gap neither code nor tests answer), and never presents an Inferred or Unknown finding as
  Observed.
- **`saf-implement`**: preserves behavioral sensors at contractual seams; records executed
  **current** evidence; grounds the oracle in spec / repo contracts / configured gates, not a
  tautological `expected`. Test-first is allowed. Same-agent RED is not proof. Missing RED is
  not a failure by itself.
- **`saf-check-task`**: identifies requirements; selects the smallest sensor set that still
  covers specified behaviors and relevant failure modes; grounds the oracle in authority; flags
  tautology; records commands/results as **evidence**; records missing/inadequate sensors as
  gaps; distinguishes current vs historical vs not-run. Missing RED is not an automatic fail.
  PASS is evidence, not a verdict. Never turn missing evidence into a pass.
- **`saf-validate`**: re-reads spec **and** repo contracts; evaluates accumulated evidence;
  runs required **current** gates; rejects stale results as current proof; traces
  requirement-to-evidence; records explicit gaps; distinguishes verification limits from
  implementation failures. Evidence from prior runs is context, not proof.
- **`saf-review-pr`**: "do not invent CI results": verifies every finding with code or
  reproducible evidence before separating blocking defects from non-blocking observations.
- **`saf-fix-pr`**: keeps a findings ledger that classifies preferences, missing evidence, and
  spec drift without altering their classification just to close them out.

A skill's local vocabulary may add nuance for its domain; it must never contradict the generic
principle above.

## `Status:` field and the guardrail 1 mapping

`shared/templates/check-report.template.md` and `shared/templates/validation-report.template.md`
carry a top-line `Status: {{status}}` field, filled with the producing skill's own local
vocabulary (`saf-check-task`: `pass`/`needs changes`/`blocked`/`inconclusive`; `saf-validate`:
`ready`/`not ready`/`blocked`/`inconclusive`). This does not introduce a new, universal status
enum; `skill-authoring-standard.md`'s existing per-skill vocabulary rule is unchanged.

[Guardrail 1](autonomy-guardrails.md) ("the skill reports `PASS`/`DONE`, not `IN_PROGRESS`,
`UNKNOWN`, or `FAIL`") reads this field, not the surrounding prose, and maps each skill's own
positive value to a pass: `pass` (`saf-check-task`) and `ready` (`saf-validate`) count as
`PASS`; every other local value (`needs changes`, `not ready`, `blocked`, `inconclusive`) counts
as not-`PASS` and blocks an `autonomous` advance the same way a literal `FAIL` would. A skill
must never write `Status: pass`/`Status: ready` while a required check in `## Evidence` recorded
a failure. A skill must never write `Status: pass`/`Status: ready` on a
[False-positive classes](#false-positive-classes) hit. The same "missing evidence is never
silently upgraded to a pass" rule above applies to this field specifically.

This same field is also what [handoff-standard.md](handoff-standard.md) keys off to decide
whether a skill needs to write `handoff.md`: a terminal `Status:` (`pass`/`ready`) with no open
blocker means the produced artifact is sufficient continuity on its own; any non-terminal
`Status:` (`needs changes`, `not ready`, `blocked`, `inconclusive`) paired with work that is
pausing before completion is a signal to write or update `handoff.md`. One field, two consumers
(guardrail 1 and the handoff decision) — not a second completion taxonomy.
