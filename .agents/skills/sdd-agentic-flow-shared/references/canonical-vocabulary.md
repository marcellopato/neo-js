# Canonical vocabulary

Use one term for one concept. These terms describe the harness, not a host
runtime implementation.

| Layer | Terms | Meaning |
| --- | --- | --- |
| Intent | Specification, Requirement, Task | The behavior and bounded work to achieve it |
| Capability | Skill, Instruction, Prompt | A public capability contract, durable guidance, and a concrete request |
| Execution | Host, Agent, Worker, Tool, Hook, Action | The runtime, reasoning actor, delegated unit, executable capability, runtime callback, and bounded operation |
| Control | Policy, Guardrail, Gate, Decision Gate, Stage, State, Status, Transition | Rules and conditions governing workflow movement |
| Verification | Sensor, Evidence, Finding, Verdict | Observation, result, derived issue, and aggregated decision |

`Worker` is host-neutral; a host may implement it with a subagent, a fresh
session, or serial work. `Tool` and `Hook` are runtime mechanics, not skills.
`Action` is one bounded operation and is not a synonym for a skill. `Stage` is
a macro workflow phase; `Status` is one value within state. Governance names
the control layer collectively, not another runtime object.
