---
name: create-filesystem-overview
description: This skill writes FILESYSTEM-OVERVIEW.md to explain the structure of a codebase. It owns and reconciles FILESYSTEM-OVERVIEW.md. Use this skill when onboarding to an unfamiliar codebase or as a sub-step of the `/create-overview` command.
user-invocable: true
argument-hint: "[path-to-repo] [--prune | --exclude name1,name2,… | --exclude-files]"
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

### Ordering (strict — enforced by the script, not by hand)

Within **every** directory, list entries in this order:
1. **Files first, then folders.**
2. **Within each group, dotted entries cluster first** (alphabetical among themselves), **then the rest**
   (alphabetical). All comparisons are **case-insensitive** — case is never a tiebreaker, so `README.md`
   and `pyproject.toml` interleave purely by letter regardless of capitalization.

So a directory renders as: dotfiles → other files → dot-folders → other folders.

`scripts/build_filesystem_overview.py` produces this ordering (and the box-art, exclusions, and
"hidden folders are leaves" rule) deterministically — **do not** assemble or re-sort the tree by hand.
A bare `sort`/`ls` is locale-dependent and will inconsistently put capitalized names before lowercase
ones; the script sorts on `name.lower()` so the output is identical every run.

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

The split: a **script** owns the deterministic mechanics (walk, exclusions, ordering, box-art, the
date/summary scaffold, the blank `— ` annotation slots); **you** own the judgment (reconciliation,
the per-entry annotations, the summary paragraph).

1. Resolve the target repo (argument path, else current working directory) and the exclusion flags
   (none by default; `--prune`; `--exclude a,b`; `--exclude-files`).
2. **Reconcile first — you own this file.** If `<repo>/FILESYSTEM-OVERVIEW.md` exists, don't blindly
   overwrite: read it, then run the script with `--stdout` to generate the fresh skeleton, diff the
   two to detect staleness (new/removed entries; header date), and **preserve any hand-written notes**
   by carrying their annotations over onto the new skeleton. If force/refresh → update-in-place
   silently; else report and ask (update-in-place (default) / overwrite / skip). If it doesn't exist,
   skip to step 3 for a fresh generate.
3. **Generate the skeleton with the script** (writes `<repo>/FILESYSTEM-OVERVIEW.md` with blank `— `
   slots; use `python3`, this machine has no bare `python`). Pass the resolved exclusion flags:
   ```bash
   SKILL_DIR="<this skill's dir>"   # resolve the absolute path first
   python3 "$SKILL_DIR/scripts/build_filesystem_overview.py" <repo>            # default: exclude nothing
   python3 "$SKILL_DIR/scripts/build_filesystem_overview.py" <repo> --prune    # noise preset
   python3 "$SKILL_DIR/scripts/build_filesystem_overview.py" <repo> --exclude __pycache__,node_modules
   python3 "$SKILL_DIR/scripts/build_filesystem_overview.py" <repo> --exclude-files
   # add --stdout to print instead of writing (used for the reconcile diff in step 2)
   ```
   The script already lists all hidden root entries, keeps hidden folders as leaves, applies the
   exclusions, and emits the strict case-insensitive ordering — so the structure is fixed; you only
   fill in text.
4. **Fill in the annotations** in the generated file (`Edit` each `— ` slot). Cheap signals first:
   name, any `README`/`__init__` docstring, the names of files inside (`Glob`), a single representative
   file read only if still unclear. Per-folder granularity — don't read everything; one line per entry,
   describing what it's *for*. For hidden folders a one-line "what it's for" is enough.
5. **Fill in the summary** — replace the `<FILL IN: …>` slot with a one-paragraph "what this project
   is", drawn from `README`/`CLAUDE.md` if present.

## Output — `FILESYSTEM-OVERVIEW.md` at the repo root

The script emits exactly this shape (date filled, structure ordered, every entry ending in a blank
`— ` slot, plus a `<FILL IN: …>` summary slot). You fill the slots in place — do not retype the tree.

`````markdown
# Filesystem Overview

- Date: <YYYY/MM/DD>
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