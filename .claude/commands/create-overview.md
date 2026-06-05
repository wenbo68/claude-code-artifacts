---
name: create-overview
description: Generate (or refresh) a codebase overview — an annotated directory map (FILESYSTEM-OVERVIEW.md) and an annotated, categorized dependency list (DEPENDENCY-OVERVIEW.md). The dependency manifest itself is never modified.
argument-hint: "[path-to-repo] [--prune | --exclude a,b | --exclude-file]  (default: current repo root, exclude nothing)"
---

# /create-overview

Generate an onboarding overview of a codebase: an annotated directory map, and a dependency overview
that lists every dependency in manifest order with a per-dep annotation plus a category taxonomy. The
dependency manifest itself is left untouched.

## What to do

Invoke the **codebase-explorer** agent, a thin orchestrator over two writer skills that each own and
reconcile their own files:

```
Agent(
  subagent_type="codebase-explorer",
  description="Generate codebase overview",
  prompt="Generate the codebase overview for the repo at <TARGET>. <EXCL_NOTE> <FORCE_NOTE>"
)
```

- `<TARGET>` = the path in `$ARGUMENTS` if provided, otherwise the current repo root.
- `<EXCL_NOTE>` = forward any `--prune` or `--exclude name1,name2` flags from `$ARGUMENTS` to the
  filesystem skill verbatim. They control which folders the directory map leaves out (default: leave
  out nothing); they don't affect the dependency overview.
- `<FORCE_NOTE>` = if the user clearly asked to force/refresh/overwrite, add
  "The user wants an update-in-place refresh — do not ask, just regenerate and preserve hand edits."
  Otherwise leave empty so the agent asks before clobbering an existing file.

This command is a thin entry point. The agent does the heavy file-reading in its own isolated context
(via its preloaded `create-filesystem-overview` and `create-deps-overview` skills), so your main context
stays clean. Each skill writes **and reconciles** its own artifacts: `create-filesystem-overview` writes
`FILESYSTEM-OVERVIEW.md`; `create-deps-overview` writes `DEPENDENCY-OVERVIEW.md` (and never modifies the
dependency manifest). The agent only sequences them and forwards the force/refresh intent.
Relay the agent's final summary to the user.

> Tip: to refresh just one part without the full run, invoke a skill directly —
> `/create-deps-overview` (e.g. on `pyproject.toml`) rewrites `DEPENDENCY-OVERVIEW.md`;
> `/create-filesystem-overview` regenerates just the directory map.
