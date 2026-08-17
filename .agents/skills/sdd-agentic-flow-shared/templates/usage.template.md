# Skills usage (local stub)

Regenerable toolkit state written by `sdd-agentic-flow init`. This is not a project spec.
Edit the canonical guide on GitHub if you need to change the workflow; re-running `init`
refreshes this file without touching `.sdd-agentic-flow/config.yml`.

## Main chain

Plan → Prompt → Implement → Check → PR → Review → Fix → Validate

When the next step is unclear, invoke the `saf-route` skill. It recommends one skill from
that chain. It does not run the workflow for you.

## Canonical guide

This consumer project does not ship the package `docs/` tree (default `install --scope user`
is zero footprint). Read the full guide here:

- English: `https://github.com/gmartins-dev/sdd-agentic-flow/blob/main/docs/sdd-skills-usage-guide.md`
- Português: `https://github.com/gmartins-dev/sdd-agentic-flow/blob/main/docs/sdd-skills-usage-guide.pt-BR.md`

Validate the installed setup with:

```bash
npx sdd-agentic-flow doctor
```

If `doctor` reports missing skills, install the pack selected in your installation intent.
