# Explanation — {{feature_slug}}

Pedagogical, not normative: read `spec.md` for what must be true, `design.md` for how it is
structured, and `tasks.md` for what to do in order. This document explains why and how, for a
reader with no prior context.

Cite a source artifact for every section (`spec.md` heading, `design.md` decision, or
`tasks.md` id). If the source has nothing for a section, omit that section or write
`Not in source artifacts`. Never invent. Never fill a section with unanchored prose
("this feature allows users to…").

## Problem

Cite the `spec.md` heading that states the problem. Empty → omit or `Not in source artifacts`.

{{problem}}

## Context / current state

Cite `spec.md` / `context.md` (and code only when the spec package already points at it).
Empty → omit or `Not in source artifacts`.

{{current_state}}

## What changes

Cite the `spec.md` heading or acceptance criterion. Empty → omit or `Not in source artifacts`.

{{what_changes}}

## How the new flow works

Cite `design.md` (flow/decision) or `spec.md` behavior. Empty → omit or `Not in source artifacts`.

{{how_it_works}}

## Important concepts

Cite `spec.md`, `design.md`, or `.sdd-agentic-flow/context/domain-glossary.md`. Empty → omit
or `Not in source artifacts`.

{{concepts}}

## Decisions

Cite a `design.md` decision. Empty → omit or `Not in source artifacts`.

{{decisions}}

## Key scenarios

Cite `spec.md` scenarios or `tasks.md` ids. Empty → omit or `Not in source artifacts`.

{{scenarios}}

## What this does NOT change

Cite the `spec.md` out-of-scope heading. Empty → omit or `Not in source artifacts`.

{{out_of_scope}}

## How to verify

Cite `spec.md` acceptance criteria or `tasks.md` verification. Empty → omit or
`Not in source artifacts`.

{{how_to_verify}}

## Glossary

Cite `.sdd-agentic-flow/context/domain-glossary.md` or terms defined in `spec.md`. Empty →
omit or `Not in source artifacts`.

{{glossary}}
