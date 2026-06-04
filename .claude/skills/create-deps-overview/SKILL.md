---
name: create-deps-overview
description: This skill writes DEPENDENCY-OVERVIEW.md to explain the third-party dependencies of a codebase. It owns and reconciles DEPENDENCY-OVERVIEW.md. Use when onboarding to an unfamiliar codebase or as a sub-step of /create-overview.
user-invocable: true
argument-hint: "[path-to-repo-or-manifest]"
---

# create-deps-overview

You explain the project's third-party dependencies in **one file — `DEPENDENCY-OVERVIEW.md`** at the
repo root. **You never modify the dependency manifest** (`pyproject.toml` / `package.json` / …); you
only read it. This is deliberate: JSON manifests can't hold comments at all, and package managers
(`pnpm add`, `uv add`, …) re-serialize manifests and would wipe any in-file annotation — so keeping all
annotation in a sidecar is format-agnostic and tooling-proof.

The file has **two sections**:
1. **Dependencies** — every dependency, in the **same order as the manifest**, each
   with a one-line annotation of what it is and how it's used here.
2. **Taxonomy** — the same dependencies grouped into categories.

You **write** `DEPENDENCY-OVERVIEW.md` and **own its reconciliation** — re-running updates it
idempotently rather than duplicating. This holds standalone (`/create-deps-overview`) or as a sub-step
of `/create-overview`; the calling agent does not reconcile for you. A caller may pass a
**force/refresh** intent to skip any prompt.

## What to read (authoritative source, not raw imports)

Parse the **manifest**, which enumerates external deps with versions — don't enumerate deps by grepping
`import`/`require` (internal imports are noise). Read whichever are present (`Glob`):
- Python: `pyproject.toml` (`[project.dependencies]`, `[project.optional-dependencies]`), `requirements*.txt`
- Node: `package.json` (`dependencies`, `devDependencies`)
- Go: `go.mod` · Rust: `Cargo.toml` · Ruby: `Gemfile` · Java: `pom.xml`/`build.gradle`

To learn *how* a dep is used, a couple of targeted `Grep`s for the import name across the source tree
is fine. **Preserve the manifest's declared order** in section 1 — do not sort it.

## Procedure

1. Resolve the target (argument path — repo dir or specific manifest — else current working dir).
2. **Reconcile first — you own `DEPENDENCY-OVERVIEW.md`.** If it exists, don't blindly overwrite: read
   it, compare against the current manifest (new/removed deps, version changes, header date), preserve
   any hand-written notes (e.g. a `> Notes:` line). If force/refresh → update-in-place silently; else
   report and ask (update-in-place (default) / overwrite / skip). If it doesn't exist, generate fresh.
3. Read each manifest; collect dependency names + version constraints **in declared order**. Keep
   runtime vs dev/optional groups distinct if the manifest separates them.
4. For each dependency, compose **one specific line**: what the library is **and** how it's used in
   *this* project where inferable (e.g. "builds the StateGraph that orchestrates the agent nodes"). If
   usage is unclear, give the library's general purpose.
5. Assign each dependency a category for the taxonomy (don't reorder section 1 — categorize in section 2).

## Output — write `DEPENDENCY-OVERVIEW.md` at the repo root

````markdown
# Dependency Overview

- Date: <YYYY/MM/DD>
- Sources: `pyproject.toml`, `source2`, …

## List

- `langchain-core`: `>=0.3.81`
    - base message/runnable abstractions the graph is built on
- `backtrader`: `>=1.9.78.123`
    - backtesting engine for strategy evaluation
- …

<If several manifests / dependency groups exist, give each its own ordered block under a
`### <manifest> — <group>` subheading, each preserving that file's declared order.>

## Taxonomy

- <Category>: <one-line description of what this category covers in the project>
   - `langgraph`
   - `langgraph-checkpoint-sqlite`
   - `langchain-core`
- <Category>: <one-line description of what this category covers in the project>
   - `langchain-anthropic`
   - `langchain-openai`
   - `langchain-google-genai`
````

Rules:
- **Section 1 preserves manifest order exactly** (the numbered rows mirror the manifest top-to-bottom).
- **Every dependency appears in both sections** — section 1 (annotated, in order) and section 2 (grouped).
- Order taxonomy categories by how central they are (core framework first).
- Idempotent: a re-run rewrites the two sections; it doesn't append duplicates. Preserve hand edits.

## When invoked as a sub-step of /create-overview

The `codebase-explorer` agent runs these instructions itself and forwards any force/refresh intent. You
own `DEPENDENCY-OVERVIEW.md` and its reconciliation; you never touch the manifest.