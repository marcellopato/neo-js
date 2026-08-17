# Task slicing

Prefer vertical slices. Each task should describe one observable behavior, acceptance criteria, a public seam when code is involved, and an independent check.

- State dependencies explicitly.
- Use horizontal-only slices only with a recorded justification.
- For broad contract changes, use an expand-contract strategy where applicable.
- Mark non-code work as `non-code`; public seams and test commands may be `N/A` with a reason.
- Keep tasks bounded enough to implement, check, and report independently.
