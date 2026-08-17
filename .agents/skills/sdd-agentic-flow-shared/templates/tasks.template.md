# Tasks — {{feature_slug}}

## {{task_id}}

Acceptance criteria: {{acceptance_criteria}}

Review boundary: {{review_boundary}}

Slice type: {{vertical | horizontal | non-code}}

Independently verifiable: {{yes | no}}

Public seam: {{public_seam_or_na}}

Requirement anchors: {{requirement_anchors}}

Dependencies: {{dependencies_or_none}}

Horizontal-slice justification: {{justification_or_na}}

Expand-contract strategy: {{strategy_or_na}}

## TDD baseline

- Behavior under test: {{behavior_under_test}}
- Public seam: {{public_seam}}
- Test strategy: {{test_strategy}}
<!--
Historical/diagnostic field only.
RED is not required and must not be fabricated.
Use n/a when RED is not meaningful or was not used as evidence.
-->
- Expected RED command: {{red_command}}
- Expected GREEN command: {{green_command}}
- Refactor scope: {{refactor_scope}}
- TDD limitations: {{tdd_limitations}}
<!--
Expected outcomes come from the spec (observable expected outcome per AC), not from the code.
When the work is a defect, include a reproduction sensor that fails on current code.
-->
