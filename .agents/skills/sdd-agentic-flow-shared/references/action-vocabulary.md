# Action vocabulary

Skill bodies describe behavior with a small set of vendor-neutral verbs instead of naming a
specific coding agent or product. This keeps every skill usable by any agent that can read
Markdown and follow instructions, and lets `scripts/check-skills.sh` mechanically guard against
vendor names creeping into skill bodies (see [compatibility promise](../../docs/compatibility-promise.md)).

An **Action** is one bounded operation, not a synonym for a Skill, Tool, or Hook. See the
[canonical vocabulary](canonical-vocabulary.md) for the broader harness taxonomy.

Each verb below is defined by three facets: **Intent** (why a skill would use it), **Authority**
(what it is and is not allowed to change), and **Output** (what it leaves behind for the next
step).

- **Read**
  - Intent: gather existing information (a file, config value, or prior artifact) before
    acting on it.
  - Authority: read-only; never creates, edits, or deletes anything.
  - Output: loaded content available to inform the next step (for example, reading
    `.sdd-agentic-flow/config.yml` before using its artifact paths).
- **Write**
  - Intent: record a decision or result as a durable artifact.
  - Authority: create or update exactly the file(s) the current step is scoped to; never touch
    unrelated files.
  - Output: a new or updated file on disk (for example, `spec.md` with requirements and
    acceptance criteria).
- **Delegate**
  - Intent: hand a bounded sub-task to another skill or a human without doing the work directly.
  - Authority: names the receiving skill or human decision-maker; never performs the delegated
    work itself.
  - Output: a clear handoff (for example, delegating the PR write-up to `saf-create-pr` once
    evidence is captured).
- **Inspect**
  - Intent: examine code, tests, or evidence to understand current behavior.
  - Authority: read-only; never changes the inspected material.
  - Output: findings that inform a later Write, Verify, or Review step (for example, inspecting
    changed files for scope drift before classifying a task).
- **Verify**
  - Intent: check that a specific claim or artifact meets a defined gate.
  - Authority: read-only against the target, though it may run an approved local command to
    obtain evidence.
  - Output: a pass/fail determination backed by evidence (for example, confirming a RED command
    actually failed before recording it).
- **Review**
  - Intent: assess a completed artifact for correctness, safety, or quality.
  - Authority: read-only against the artifact; raises findings rather than fixing them directly.
  - Output: findings compared against defined acceptance criteria (for example, reviewing a
    diff against a task's acceptance criteria).
- **Ask Human**
  - Intent: pause for an explicit authorization or a missing decision only a human can make.
  - Authority: cannot proceed past the pause point without an explicit human answer.
  - Output: a recorded decision or authorization that unblocks the next step (for example,
    asking before creating `.sdd-agentic-flow/context/domain-glossary.md`).
- **Summarize**
  - Intent: condense findings, evidence, or a decision into a short report.
  - Authority: read-only against the source material; adds no new claims beyond what was
    gathered.
  - Output: a short report or handoff note (for example, summarizing unresolved decisions
    before handing off the spec package).
