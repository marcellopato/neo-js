# Feature validation — {{feature_slug}}

Status: {{status}}

## Validation scope

<!-- Record impact, obligations, selected sensors, and omitted sensors with reasons. -->
{{validation_scope}}

## Evidence

<!--
Distinguish current vs historical vs not-run.
A passing sensor is evidence, not a correctness verdict.
Record requirement → sensor → current result in the table below AND detailed evidence prose.
-->

| Requirement anchor | Sensor | Result | Freshness |
| --- | --- | --- | --- |
| {{requirement_anchor}} | {{sensor}} | {{result}} | {{freshness}} |

{{evidence}}

## TDD evidence

- Behavior tested: {{behavior_tested}}
- Seam: {{public_seam}}
- RED: {{red_evidence}}
- GREEN: {{green_evidence}}
- REFACTOR: {{refactor_evidence}}
- Broader checks: {{broader_checks}}
- Limitations: {{tdd_limitations}}
