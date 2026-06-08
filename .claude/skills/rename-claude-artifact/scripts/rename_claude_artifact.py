#!/usr/bin/env python3
"""Rename a Claude Code agent, command, or skill and fix its load-bearing references.

This script owns the *deterministic* half of a rename:
  - moves the file (agent/command) or directory (skill), preserving git history when possible
  - rewrites the artifact's own ``name:`` frontmatter
  - rewrites high-confidence references across the .claude tree:
        agents   -> ``subagent_type="old"`` and ``subagent_type='old'``
        commands -> ``/old`` slash tokens
        skills   -> ``/old`` slash tokens and ``skills:`` frontmatter entries
                    (both comma-list and YAML-list forms)

It deliberately does NOT touch prose mentions (e.g. "the **old** agent", headings,
doc descriptions). Those are ambiguous and context-sensitive, so instead it *reports*
every residual occurrence of the old name for a human (or Claude) to review by judgment.

Dry-run by default. Pass --apply to actually move files and write edits.

Usage:
    python scripts/rename_claude_artifact.py <agent|command|skill> <old> <new> [--claude-dir DIR] [--apply]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("agent", "command", "skill")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Text files we are willing to scan/edit. Avoid binaries and lockfiles.
SCAN_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".txt"}


def boundary(name: str) -> re.Pattern:
    """Match `name` only when not part of a larger identifier (hyphens count as word chars)."""
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")


@dataclass
class Plan:
    moves: list[tuple[Path, Path]] = field(default_factory=list)
    edits: list[tuple[Path, int, str, str]] = field(default_factory=list)  # path, lineno, before, after
    residuals: list[tuple[Path, int, str]] = field(default_factory=list)  # path, lineno, line
    errors: list[str] = field(default_factory=list)


def locate(kind: str, name: str, claude: Path) -> Path | None:
    if kind == "agent":
        p = claude / "agents" / f"{name}.md"
        return p if p.exists() else None
    if kind == "command":
        hits = list((claude / "commands").rglob(f"{name}.md"))
        return hits[0] if hits else None
    if kind == "skill":
        p = claude / "skills" / name / "SKILL.md"
        return p.parent if p.exists() else None
    return None


def target_path(kind: str, src: Path, new: str) -> Path:
    if kind == "skill":  # src is the directory
        return src.with_name(new)
    return src.with_name(f"{new}.md")


def replace_slash(old: str, new: str, text: str) -> tuple[str, int]:
    """Replace `/old` slash tokens, not `/old/` path segments or `foo-old`."""
    pat = re.compile(rf"(?<![\w/-])/{re.escape(old)}(?![\w/-])")
    return pat.subn(f"/{new}", text)


def replace_skills_frontmatter(old: str, new: str, text: str) -> tuple[str, int]:
    """Update `skills:` frontmatter entries (comma list and YAML list)."""
    count = 0
    lines = text.splitlines(keepends=True)
    in_skills_block = False
    bword = boundary(old)
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        # inline comma form: `skills: a, old, b`
        m = re.match(r"^(\s*skills\s*:\s*)(.+)$", stripped)
        if m and not m.group(2).strip().startswith("#"):
            new_val, n = bword.subn(new, m.group(2))
            if n:
                lines[i] = m.group(1) + new_val + ("\n" if line.endswith("\n") else "")
                count += n
            in_skills_block = m.group(2).strip() == ""  # `skills:` then YAML list below
            continue
        # YAML list item under a `skills:` block: `  - old`
        if in_skills_block:
            if re.match(r"^\s*-\s+", stripped):
                new_line, n = bword.subn(new, stripped)
                if n:
                    lines[i] = new_line + ("\n" if line.endswith("\n") else "")
                    count += n
                continue
            if stripped.strip() and not stripped.startswith(" "):
                in_skills_block = False
    return "".join(lines), count


def scan_and_edit(kind: str, old: str, new: str, claude: Path, own_file: Path,
                  plan: Plan, prose_too: bool = False) -> dict[Path, str]:
    """Compute edits across the tree. Returns {path: new_content} for files that change."""
    new_contents: dict[Path, str] = {}
    bword = boundary(old)
    sub_pat = re.compile(rf'(subagent_type\s*=\s*["\']){re.escape(old)}(["\'])')
    # `[ \t]*$` (not `\s*$`): under re.MULTILINE, `\s` matches newlines, so `\s*$` would
    # gobble trailing blank lines and merge them away. Match only horizontal whitespace.
    name_pat = re.compile(rf"(?m)^([ \t]*name[ \t]*:[ \t]*){re.escape(old)}[ \t]*$")
    # --prose-too: only high-confidence prose forms — backtick-wrapped tokens (`old`)
    # and markdown headings (`# old`). Bare mentions stay residual for human judgment.
    btick_pat = re.compile(rf"`{re.escape(old)}`")
    heading_pat = re.compile(rf"(?m)^(#+[ \t]+){re.escape(old)}[ \t]*$")

    for path in sorted(claude.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        text = original

        if kind == "agent":
            text, _ = sub_pat.subn(rf"\g<1>{new}\g<2>", text)
        if kind in ("command", "skill"):
            text, _ = replace_slash(old, new, text)
        if kind == "skill":
            text, _ = replace_skills_frontmatter(old, new, text)
        if path == own_file:  # the artifact's own `name:` frontmatter is load-bearing
            text, _ = name_pat.subn(rf"\g<1>{new}", text)
        if prose_too:
            text, _ = btick_pat.subn(f"`{new}`", text)
            text, _ = heading_pat.subn(rf"\g<1>{new}", text)

        if text != original:
            new_contents[path] = text
            # record per-line edits for the plan
            for ln, (a, b) in enumerate(zip(original.splitlines(), text.splitlines()), start=1):
                if a != b:
                    plan.edits.append((path, ln, a.strip(), b.strip()))

        # residuals: any remaining bare occurrence of `old` in the (post-edit) text
        post = new_contents.get(path, original)
        for ln, line in enumerate(post.splitlines(), start=1):
            if bword.search(line):
                plan.residuals.append((path, ln, line.strip()))

    return new_contents


def git_move(src: Path, dst: Path, repo: Path) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(repo), "mv", str(src), str(dst)],
                           capture_output=True, text=True)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--claude-dir", default=".claude", help="path to the .claude directory (default: .claude)")
    ap.add_argument("--apply", action="store_true", help="actually move files and write edits (default: dry-run)")
    ap.add_argument("--prose-too", action="store_true",
                    help="also auto-edit high-confidence prose: backtick-wrapped tokens (`old`) and "
                         "markdown headings (# old). Truly ambiguous bare mentions still stay residual.")
    args = ap.parse_args()

    claude = Path(args.claude_dir).resolve()
    if not claude.is_dir():
        print(f"error: {claude} is not a directory", file=sys.stderr)
        return 2
    if not NAME_RE.match(args.new):
        print(f"error: new name '{args.new}' must be kebab-case ([a-z0-9-])", file=sys.stderr)
        return 2

    plan = Plan()
    src = locate(args.kind, args.old, claude)
    if src is None:
        print(f"error: no {args.kind} named '{args.old}' under {claude}", file=sys.stderr)
        return 2
    dst = target_path(args.kind, src, args.new)
    if dst.exists():
        print(f"error: target already exists: {dst}", file=sys.stderr)
        return 2
    plan.moves.append((src, dst))

    # The artifact's own markdown file (whose `name:` frontmatter we must rewrite).
    own_file = (src / "SKILL.md") if args.kind == "skill" else src

    # Compute reference edits across the tree (relative to the OLD on-disk layout).
    new_contents = scan_and_edit(args.kind, args.old, args.new, claude, own_file, plan, args.prose_too)

    # Print the plan.
    rel = lambda p: p.relative_to(claude.parent) if claude.parent in p.parents else p
    print(f"\n{'APPLYING' if args.apply else 'DRY RUN'}: rename {args.kind} '{args.old}' -> '{args.new}'\n")
    print("MOVE:")
    for s, d in plan.moves:
        print(f"  {rel(s)}  ->  {rel(d)}")
    edits_label = "EDITS (load-bearing + high-confidence prose)" if args.prose_too else "LOAD-BEARING EDITS"
    print(f"\n{edits_label} ({len(plan.edits)}):")
    for p, ln, a, b in plan.edits:
        print(f"  {rel(p)}:{ln}")
        print(f"    - {a}")
        print(f"    + {b}")
    if not plan.edits:
        print("  (none)")

    if not args.apply:
        print(f"\nRESIDUAL MENTIONS to review by judgment ({len(plan.residuals)}):")
        for p, ln, line in plan.residuals:
            print(f"  {rel(p)}:{ln}: {line}")
        if not plan.residuals:
            print("  (none)")
        print("\nRe-run with --apply to execute the move and load-bearing edits.")
        print("Residual mentions above are NOT auto-edited — review them after applying.")
        return 0

    # --- APPLY ---
    # 1) write reference edits first (paths still point at old layout)
    for path, text in new_contents.items():
        path.write_text(text, encoding="utf-8")
    # 2) move the artifact (its own name: was already rewritten in step 1)
    moved = git_move(src, dst, claude.parent)
    if not moved:
        src.rename(dst)

    # 3) verify: count remaining bare occurrences of old name
    remaining = 0
    bword = boundary(args.old)
    for path in claude.rglob("*"):
        if path.is_file() and path.suffix in SCAN_SUFFIXES:
            try:
                remaining += len(bword.findall(path.read_text(encoding="utf-8")))
            except (UnicodeDecodeError, OSError):
                pass

    # Residuals were located against the pre-move layout; remap any under `src` to `dst`.
    def remap(p: Path) -> Path:
        if p == src:
            return dst
        try:
            return dst / p.relative_to(src)
        except ValueError:
            return p

    print(f"\nDONE. Moved artifact and applied {len(plan.edits)} load-bearing edit(s).")
    print(f"Remaining bare occurrences of '{args.old}': {remaining} (review these — they are prose, not wiring).")
    if remaining:
        for p, ln, line in plan.residuals:
            print(f"  {rel(remap(p))}:{ln}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
