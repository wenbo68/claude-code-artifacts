#!/usr/bin/env python3
"""Build the FILESYSTEM-OVERVIEW.md skeleton deterministically.

Owns the *mechanical* half of the create-filesystem-overview skill: walking the
tree, applying exclusions, the "hidden folders are leaves" rule, the strict
ordering, and drawing the box-art skeleton with blank `— ` annotation slots plus
the date/summary scaffold. The model fills in the annotations afterward.

Ordering within every directory (all comparisons case-insensitive, so case is
NEVER a tiebreaker):
  1. files first, then folders
  2. within each group: dotted entries cluster first, then the rest
  => dotfiles -> other files -> dot-folders -> other folders

Run with --stdout to print (for reconciliation/merge); default writes the file.
"""

import argparse
import fnmatch
import os
import sys
from datetime import date

PRUNE_PRESET = [
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store",
    "node_modules", "dist", "build", "*.egg-info",
]

ANNOT = "— "  # blank annotation slot the model fills in


def is_hidden(name):
    return name.startswith(".")


def is_excluded(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def sort_key(entry):
    # (is_dir, not dotted, lowercased name)
    #  files(False=0) before folders(True=1); within a group dotted(False=0)
    #  first; then case-insensitive alphabetical. name.lower() means case is
    #  never a tiebreaker -- the whole point of this script.
    name, is_dir = entry
    return (is_dir, not is_hidden(name), name.lower())


def list_dir(path, exclude, only_dirs):
    try:
        names = os.listdir(path)
    except OSError:
        return []
    entries = []
    for name in names:
        if is_excluded(name, exclude):
            continue
        full = os.path.join(path, name)
        is_dir = os.path.isdir(full) and not os.path.islink(full)
        if only_dirs and not is_dir:
            continue
        entries.append((name, is_dir))
    entries.sort(key=sort_key)
    return entries


def walk(path, prefix, lines, exclude, exclude_files, depth):
    # exclude_files: at depth>0 (non-root), list folders only.
    only_dirs = exclude_files and depth > 0
    entries = list_dir(path, exclude, only_dirs)
    for i, (name, is_dir) in enumerate(entries):
        last = i == len(entries) - 1
        connector = "└── " if last else "├── "
        display = name + ("/" if is_dir else "")
        lines.append((prefix + connector + display, True))  # annotatable
        # Hidden folders are leaves -- listed, never recursed.
        if is_dir and not is_hidden(name):
            ext = "    " if last else "│   "
            walk(os.path.join(path, name), prefix + ext, lines,
                 exclude, exclude_files, depth + 1)


def render_tree(repo, exclude, exclude_files):
    root_label = os.path.basename(os.path.abspath(repo)) or repo
    lines = [(root_label + "/", False)]  # root line: no annotation slot
    walk(repo, "", lines, exclude, exclude_files, 0)

    width = max((len(text) for text, annot in lines if annot), default=0)
    out = []
    for text, annot in lines:
        if annot:
            out.append(f"{text.ljust(width)}  {ANNOT}")
        else:
            out.append(text)
    return "\n".join(out)


def render_doc(repo, exclude, exclude_files):
    tree = render_tree(repo, exclude, exclude_files)
    today = date.today().strftime("%Y/%m/%d")
    return (
        "# Filesystem Overview\n\n"
        f"- Date: {today}\n"
        "- Summary: <FILL IN: one-paragraph what-this-project-is, "
        "drawn from README/CLAUDE.md if present>\n\n"
        "## Structure\n\n"
        "```\n"
        f"{tree}\n"
        "```\n"
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("repo", nargs="?", default=".", help="repo root (default: cwd)")
    p.add_argument("--exclude", default="", help="comma-separated names/globs to omit entirely")
    p.add_argument("--prune", action="store_true", help="apply the noise preset")
    p.add_argument("--exclude-files", action="store_true",
                   help="show files only at root; folders-only below root")
    p.add_argument("--stdout", action="store_true",
                   help="print to stdout instead of writing FILESYSTEM-OVERVIEW.md")
    args = p.parse_args(argv)

    if not os.path.isdir(args.repo):
        p.error(f"not a directory: {args.repo}")

    exclude = []
    if args.prune:
        exclude += PRUNE_PRESET
    if args.exclude:
        exclude += [s.strip() for s in args.exclude.split(",") if s.strip()]

    doc = render_doc(args.repo, exclude, args.exclude_files)

    if args.stdout:
        sys.stdout.write(doc)
    else:
        dest = os.path.join(args.repo, "FILESYSTEM-OVERVIEW.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(doc)
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
