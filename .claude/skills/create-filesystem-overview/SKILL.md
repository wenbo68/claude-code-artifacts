---
name: create-filesystem-overview
description: This skill writes FILESYSTEM-OVERVIEW.md to explain the structure of a codebase. It owns and reconciles FILESYSTEM-OVERVIEW.md. Use this skill when onboarding to an unfamiliar codebase or as a sub-step of the `/create-overview` command.
user-invocable: true
argument-hint: "[path-to-repo] [--prune | --exclude name1,name2,…]"
---

# create-filesystem-overview

You produce and **own** `FILESYSTEM-OVERVIEW.md` at the repo root — you write the file and reconcile it
when it already exists. Symmetric with `create-deps-overview`: each skill writes its own artifact and
owns that artifact's reconciliation, so both work identically standalone (`/create-filesystem-overview`)
or as a sub-step of `/create-overview`. The calling agent does not write or reconcile this file for you.
A caller may pass a **force/refresh** intent, in which case update-in-place without prompting.

## What the tree must contain

- **Root level — list everything, including hidden:**
  - **All root files**, including hidden ones (`.gitignore`, `.env.example`, `.dockerignore`, …).
  - **All root folders**, including hidden ones (`.git`, `.github`, `.claude`, …).
- **Hidden folders are leaves — do not look inside them.** List each with a one-line purpose only
  (e.g. `.github/ — CI workflows & issue templates`); never recurse into them.
- **Visible folders are expanded fully** — recurse to show all of its files and subfolders.
- **One-line annotation** for every file and folder: what it is *for*, not what it literally contains.

### Ordering (strict)

Within **every** directory, list entries in this order:
1. **Files first, then folders.**
2. **Within each group, dotted entries cluster first** (alphabetical among themselves), **then the rest**
   (alphabetical). All comparisons case-insensitive.

So a directory renders as: dotfiles → other files → dot-folders → other folders.

### Exclusions (customizable — default: leave out NOTHING)

By default the tree omits **nothing**: every file and folder is listed and every non-hidden folder is
recursed (so `__pycache__`, `node_modules`, etc. appear). Override via the argument:

- **`--exclude <names>`** — comma-separated names/globs omitted **entirely** (not listed, not recursed).
  Example: `--exclude __pycache__,node_modules,*.egg-info`
- **`--exclude-files`** — include all files in the root directory but exclude all files in other directories; i.e., only show folders, not files, except at the root level
- **`--prune`** — apply the ready-made noise preset; equivalent to
  `--exclude __pycache__,.pytest_cache,.mypy_cache,.ruff_cache,.DS_Store,node_modules,dist,build,*.egg-info`

If no flag is given, exclude nothing.

**Independent rule (always on): hidden folders are leaves.** Any folder whose name starts with `.`
(`.git`, `.claude`) is listed but never recursed, regardless of the exclusion setting — recursing
`.git` is never useful. (Hidden *files* are always listed.) This is separate from `--exclude`.

## Procedure

1. Resolve the target repo (argument path, else current working directory) and the exclusion setting
   (none by default; `--prune` → the preset list; `--exclude a,b` → that list).
2. **Reconcile first — you own this file.** If `<repo>/FILESYSTEM-OVERVIEW.md` exists, don't blindly
   overwrite: read it, detect staleness (new/removed folders vs the map; header date), preserve any
   hand-written notes. If force/refresh → update-in-place silently; else report and ask
   (update-in-place (default) / overwrite / skip). If it doesn't exist, generate fresh.
3. List **all** root entries including hidden ones, then drop any that match the exclusion list:
   ```bash
   ls -A1p <repo> | sort        # -A includes dotfiles (not . / ..); -p marks dirs with a trailing /
   ```
4. Build the recursable skeleton — always prune hidden folders; additionally prune excluded names:
   ```bash
   # Default (exclude nothing): only hidden folders are pruned
   find <repo> -mindepth 1 \( -path '*/.*' \) -prune -o -type d -print | sort

   # With exclusions, add each name to the prune group, e.g. for --prune:
   find <repo> -mindepth 1 \( -path '*/.*' \
        -o -name __pycache__ -o -name node_modules -o -name dist -o -name build -o -name '*.egg-info' \
        -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -o -type d -print | sort
   ```
5. Annotate each entry. Cheap signals first: name, any `README`/`__init__` docstring, the names of
   files inside (`Glob`), a single representative file read only if still unclear. Per-folder
   granularity — don't read everything. For hidden folders a one-line "what it's for" is enough.
6. Draft a one-paragraph "what this project is" from `README`/`CLAUDE.md` if present.

## Output — write `FILESYSTEM-OVERVIEW.md`s at the repo root

`````markdown
# Filesystem Overview

- Date: <YYYY-MM-DD>
- Summary: <one-paragraph what-this-project-is, drawn from README/CLAUDE.md if present>

## Structure

```
repo-root/
├── .dockerignore          — <purpose>          (dotfiles cluster first, alphabetical)
├── .env.example           — <purpose>
├── README.md              — <purpose>          (then other files, alphabetical)
├── pyproject.toml         — <purpose>
├── .claude/               — <purpose>          (then dot-folders: leaves, not expanded)
├── .git/                  — <purpose>
├── src/                   — <purpose>          (then other folders: expanded)
│   ├── components/        — <purpose>
│   └── hooks/             — <purpose>
└── tests/                 — <purpose>
```
`````