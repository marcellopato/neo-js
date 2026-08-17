---
name: saf-setup
description: Initialize the public SDD Agentic Flow structure in a repository. Use when a user asks to set up, bootstrap, or configure this SDD workflow; create only the requested repository-local planning files and start from .sdd-agentic-flow/config.yml.
metadata:
  version: 4.1.0
  pack: core
extends: null
requires: [config]
consumes: []
produces: [project-config, project-context]
baseline: [tlc-spec-driven]
compatible_with: [core, full, github, local-files, planning]
depends_on: []
conflicts: []
requires_cli: null
autonomy_profile:
  supported_levels: [manual, supervised]
  auto_continue_condition: 'not applicable — this skill never auto-advances; project bootstrap is a one-time, human-confirmed step'
  blocking_conditions: [config_write_failed]
  evidence_required: [.sdd-agentic-flow/config.yml, .sdd-agentic-flow/context/project-context.md]
---

# Set up SDD Agentic Flow

## When to use

Use for a repository that needs the SDD Agentic Flow initialized or repaired.

## When not to use

Do not use to implement a feature, generate a specification for an already configured flow, change global defaults, install tools, or access external services.

## Inputs

- Repository root and the user's requested scope.
- Existing `.sdd-agentic-flow/config.yml`, if present.
- Optional project name, artifact location, and workflow preferences.
- An optional domain glossary request with explicit authorization.

## Workflow

1. Inspect the repository and read `.sdd-agentic-flow/config.yml` first when it exists.
2. Read the TLC baseline at `../sdd-agentic-flow-shared/references/tlc-baseline.md` before choosing artifact names or stages.
3. Read the safety guidance at `../sdd-agentic-flow-shared/references/workflow-safety.md` before creating files.
4. If configuration is absent, show the smallest proposed `.sdd-agentic-flow/config.yml` and obtain confirmation before writing it. Keep settings repository-local and explicit.
5. Create only the configured directories and starter artifacts needed for the requested setup. Preserve existing content and do not replace a file without explicit approval.
6. Do not create `.sdd-agentic-flow/context/domain-glossary.md` automatically. Propose or create it only when explicitly authorized, using the shared template.
7. Note that `.sdd-agentic-flow/context/project-context.md` is populated automatically by `init`/`discover`; treat it as read-only discovered output and never hand-author it.
8. Validate paths and report the resulting configuration and created files.

## Safety

- Treat `.sdd-agentic-flow/config.yml` as the source of truth; do not infer or mutate user, machine, or global defaults.
- Do not send data over the network, install dependencies, create remote resources, or use private context.
- Keep all writes inside the repository scope supplied by the user.
- Follow `../sdd-agentic-flow-shared/references/workflow-safety.md` for confirmation and redaction rules.

## Output

Return a short setup summary containing:

- the configuration path and effective artifact locations;
- files created or intentionally left unchanged;
- the next local command or skill to use.

## Autonomy

Supports `manual` and `supervised` autonomy levels only (`workflow.autonomy_level` in `.sdd-agentic-flow/config.yml`) — never `autonomous`. Project bootstrap is a one-time, human-confirmed step outside the auto-advancing chain. See `../sdd-agentic-flow-shared/references/autonomy-guardrails.md`.
