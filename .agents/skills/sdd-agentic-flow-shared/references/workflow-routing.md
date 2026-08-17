# Workflow routing

Use this reference to recommend a local SDD next step. It is guidance, not automatic invocation: read the candidate `SKILL.md` before acting.

| Situation                             | Recommended skill                  |
| --- | --- |
| No `.sdd-agentic-flow/config.yml`                  | `saf-setup`           |
| Idea not yet defined (vague goal, or a clear problem with no decided approach) | `saf-brainstorm` |
| Ambiguous or unstructured request     | `saf-create-spec`                 |
| Existing undocumented code needing specs | `saf-create-spec` (existing-code mode) |
| Specified feature needing a pedagogical explanation | `saf-explain`     |
| Ready spec without task prompts       | `saf-create-prompts`               |
| One ready task                        | `saf-implement`               |
| Multiple dependent tasks              | `saf-implement-multi`              |
| Completed task                        | `saf-check-task`                   |
| Completed change needing a PR package | `saf-create-pr`                    |
| Change ready for review               | `saf-review-pr`                    |
| Accepted review findings              | `saf-fix-pr`, then `saf-review-pr` |
| Integrated feature                    | `saf-validate`                   |

Routing recommends; it does not install packs, change files, invoke skills, or bypass human decisions.
