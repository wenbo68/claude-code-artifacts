---
name: rename-claude-artifact
description: Rename a Claude Code agent, command, or skill and fix every reference to it across the .claude tree. Use when the user asks to rename, move, or change the name of a .claude agent/command/skill (e.g. "rename the codebase-explorer agent to repo-explorer", "rename the annotate-tree skill"). Runs a deterministic script for the structural rename, then reviews leftover prose mentions by judgment.
argument-hint: "<agent|command|skill> <old-name> <new-name>"
---

# rename-claude-artifact

Rename a Claude Code **agent**, **command**, or **skill** safely. A rename is two kinds of
work and this skill keeps them separate:

- **Load-bearing / structural** (the file move, `name:` frontmatter, `subagent_type="…"`,
  `skills:` lists, `/slash` tokens) — handled deterministically by
  `scripts/rename_claude_artifact.py`. Never hand-edit these; let the script do them so the
  wiring is never left half-renamed.
- **Prose mentions** (headings, "the **old** agent", doc descriptions) — ambiguous and
  context-sensitive. The script does NOT touch these; it *reports* them and you fix them
  with judgment.

## Inputs

`$ARGUMENTS` is `<kind> <old-name> <new-name>`, where kind ∈ {agent, command, skill}.
If any part is missing or ambiguous, ask the user before proceeding.

## Procedure

> **Always invoke with absolute paths.** The shell's working directory is not guaranteed to be
> the repo root between turns, so resolve the root first and use it for both the script path and
> `--claude-dir`. Use `python3` (this machine has no bare `python` on PATH). Run this once and
> reuse `$ROOT` in every command below:
> ```bash
> ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
> RENAME="$ROOT/scripts/rename_claude_artifact.py"
> ```
> If the target `.claude` is not at `$ROOT` (e.g. a nested project), set `--claude-dir` to its
> actual location instead of `$ROOT/.claude`.

1. **Dry run first — always.** Show the user exactly what will change:
   ```bash
   python3 "$RENAME" <kind> <old> <new> --claude-dir "$ROOT/.claude"
   ```
   Relay the MOVE, the EDITS, and the RESIDUAL MENTIONS list to the user.

2. **Apply the rename.** Two modes — pick based on how prose-heavy the references are:
   - **Default** (structural only): the script handles the move + load-bearing refs and *reports*
     every prose mention for you to review in step 3.
     ```bash
     python3 "$RENAME" <kind> <old> <new> --claude-dir "$ROOT/.claude" --apply
     ```
   - **`--prose-too`** (recommended when there are many backtick/heading mentions): also
     auto-edits **high-confidence prose** — backtick-wrapped tokens (`` `old` ``) and markdown
     headings (`# old`). Truly ambiguous bare mentions (e.g. a name inside a sentence or angle
     brackets) still stay residual for judgment.
     ```bash
     python3 "$RENAME" <kind> <old> <new> --claude-dir "$ROOT/.claude" --prose-too --apply
     ```
   Either way the artifact moves (via `git mv` when tracked, else a plain move) and residuals are
   reported, remapped to their post-move paths.

3. **Review residual mentions by judgment.** For each residual the script reported, open the
   file and decide: is this a reference to the renamed artifact (→ update it with `Edit`) or an
   unrelated coincidence (→ leave it)? A name inside a sentence or `<placeholder>` almost always
   should change; a substring inside an unrelated word should not. Do not blind-replace.
   (With `--prose-too`, only the genuinely ambiguous ones remain here.)

4. **Verify zero stray references remain:**
   ```bash
   grep -rn "<old>" "$ROOT/.claude"
   ```
   Expect no meaningful hits. If any remain, they were intentional (genuinely unrelated) — say so.

5. **Report back:** what moved, how many load-bearing edits applied, which residuals you edited
   vs. left, and the final grep result. Mention that the renamed skill/command's `/slash` name
   has changed if applicable.

## Notes

- The script is dry-run by default; `--apply` is required to change anything. It refuses if the
  target name already exists or isn't kebab-case.
- It only edits text files under `.claude` (`.md`, `.json`, `.yaml/.yml`, `.toml`, `.txt`).
  References to the artifact from *outside* `.claude` (e.g. a project `CLAUDE.md` or README that
  names the agent) are not scanned — check those manually if they exist.
