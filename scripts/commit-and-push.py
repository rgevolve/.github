#!/usr/bin/env python3
"""Cross-repo commit and push helper for the rgevolve workspace.

Workspace WPs touch many repos at once. Entering each one, staging,
committing, and pushing to both ``origin`` and ``upstream`` by hand
gets tedious fast. This script fans one commit message out across
the 11 sibling repos, pushes to both remotes, and skips repos with
no changes.

**Manual-invocation tool.** Per workspace convention §4 the *agent*
never runs mutating git commands. You run this script after you've
reviewed the per-repo diffs (the agent typically reports them in the
WP closeout summary). Default is dry-run; ``--execute`` actually
commits and pushes.

The script derives the workspace root from its own location: it must
live at ``<workspace>/.github/scripts/commit-and-push.py``. The 11
expected sibling dirs are listed in ``REPOS`` below.

Typical invocations from anywhere::

    # Show what would happen (default):
    python .github/scripts/commit-and-push.py -m "WP3: foo"

    # Actually do it:
    python .github/scripts/commit-and-push.py -m "WP3: foo" --execute

    # Include untracked files (e.g. new .github/scripts/ on first commit):
    python .github/scripts/commit-and-push.py -m "..." --add-all --execute

    # Commit but don't push:
    python .github/scripts/commit-and-push.py -m "..." --no-push --execute

    # Push only (skip commit step entirely):
    python .github/scripts/commit-and-push.py --push-only --execute

    # Limit to a subset:
    python .github/scripts/commit-and-push.py -m "..." \\
        --only rgevolve-core,rgevolve --execute

Safety: the script refuses to commit on any branch other than
``main`` or ``master`` (so an in-progress feature branch isn't
accidentally bulldozed). Override with ``--allow-any-branch``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# Order matters only for readability of the output; nothing depends on it.
REPOS: List[str] = [
    ".github",
    "rgevolve-core",
    "rgevolve.smeft.warsaw",
    "rgevolve.smeft.warsaw_up",
    "rgevolve.wet.flavio",
    "rgevolve.wet.jms",
    "rgevolve.wet_3.flavio",
    "rgevolve.wet_3.jms",
    "rgevolve.wet_4.flavio",
    "rgevolve.wet_4.jms",
    "rgevolve",
]

REMOTES: Tuple[str, ...] = ("origin", "upstream")
ALLOWED_BRANCHES: Tuple[str, ...] = ("main", "master")

SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_ROOT = SCRIPT_PATH.parent.parent.parent  # .github/scripts/<file>


# ---------------------------------------------------------------------
# Thin git wrappers
# ---------------------------------------------------------------------

def _git(repo: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=capture,
        text=True,
    )


def _git_out(repo: Path, *args: str) -> str:
    r = _git(repo, *args, capture=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {r.stderr.strip()}")
    return r.stdout


def has_changes(repo: Path) -> bool:
    return bool(_git_out(repo, "status", "--porcelain").strip())


def current_branch(repo: Path) -> str:
    return _git_out(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()


def has_remote(repo: Path, name: str) -> bool:
    return name in _git_out(repo, "remote").split()


def status_short(repo: Path) -> str:
    return _git_out(repo, "status", "--short")


# ---------------------------------------------------------------------
# Per-repo actions
# ---------------------------------------------------------------------

def commit_one(
    repo: Path,
    message: str,
    add_all: bool,
    dry_run: bool,
    allow_any_branch: bool,
) -> Tuple[bool, str]:
    """Returns (did_commit_or_would, info-string)."""
    if not has_changes(repo):
        return False, "clean"
    branch = current_branch(repo)
    if branch not in ALLOWED_BRANCHES and not allow_any_branch:
        return False, (
            f"branch={branch!r} (refused; not in {ALLOWED_BRANCHES}; "
            f"pass --allow-any-branch to override)"
        )

    indent = "    "
    files = status_short(repo).rstrip()
    files_block = "\n".join(indent + line for line in files.splitlines())

    if dry_run:
        hint = (
            "git add -A (all lines below will be staged)"
            if add_all else
            "git add -u (only tracked lines below will be staged; "
            "untracked '??' lines stay untouched — pass --add-all to "
            "include them)"
        )
        return True, (
            f"would commit on {branch}; {hint}; status:\n{files_block}"
        )

    add_args = ("add", "-A") if add_all else ("add", "-u")
    r = _git(repo, *add_args, capture=True)
    if r.returncode != 0:
        return False, f"FAILED at git {' '.join(add_args)}: {r.stderr.strip()}"

    # If --add-u left nothing staged (e.g. only untracked files exist),
    # don't make an empty commit.
    staged = _git_out(repo, "diff", "--cached", "--name-only").strip()
    if not staged:
        return False, f"nothing staged after git {' '.join(add_args)} (untracked files only?)"

    r = _git(repo, "commit", "-m", message, capture=True)
    if r.returncode != 0:
        return False, f"FAILED at git commit: {r.stderr.strip()}"
    return True, f"committed on {branch}"


def push_one(repo: Path, dry_run: bool) -> List[str]:
    branch = current_branch(repo)
    lines: List[str] = []
    for remote in REMOTES:
        if not has_remote(repo, remote):
            lines.append(f"    {remote}: (no such remote — skipped)")
            continue
        if dry_run:
            lines.append(f"    {remote}: would push {branch}")
            continue
        r = _git(repo, "push", remote, branch, capture=True)
        if r.returncode == 0:
            lines.append(f"    {remote}: pushed {branch}")
        else:
            lines.append(f"    {remote}: FAILED — {r.stderr.strip()}")
    return lines


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--message", "-m",
        help="Commit message. Required unless --push-only.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run mutating git commands. Default is dry-run.",
    )
    parser.add_argument(
        "--add-all",
        action="store_true",
        help="Include untracked files (git add -A). Default: only "
             "previously-tracked modifications (git add -u).",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Commit but don't push.",
    )
    parser.add_argument(
        "--push-only",
        action="store_true",
        help="Skip commit; just push the current HEAD of each repo.",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated subset of repo dir names to operate on. "
             "Default: all 11.",
    )
    parser.add_argument(
        "--allow-any-branch",
        action="store_true",
        help=f"Override the {ALLOWED_BRANCHES} safety check.",
    )
    args = parser.parse_args()

    if not args.push_only and not args.message:
        parser.error("--message/-m is required unless --push-only is given.")
    if args.push_only and args.no_push:
        parser.error("--push-only and --no-push are mutually exclusive.")

    selected = args.only.split(",") if args.only else REPOS
    unknown = [r for r in selected if r not in REPOS]
    if unknown:
        parser.error(
            f"unknown repos in --only: {unknown}. Known: {', '.join(REPOS)}"
        )

    dry_run = not args.execute

    print(f"workspace: {WORKSPACE_ROOT}")
    print(f"mode:      {'DRY RUN — pass --execute to do it for real' if dry_run else 'EXECUTE'}")
    if not args.push_only:
        print(f"add mode:  {'git add -A (incl. untracked)' if args.add_all else 'git add -u (modified only)'}")
    print()

    any_action = False
    failures = 0

    for name in selected:
        repo = WORKSPACE_ROOT / name
        if not repo.is_dir():
            print(f"=== {name}: missing dir — skipping")
            failures += 1
            continue
        print(f"=== {name}")

        if not args.push_only:
            committed, info = commit_one(
                repo, args.message, args.add_all, dry_run, args.allow_any_branch,
            )
            print(f"  commit: {info}")
            if not committed:
                continue
            any_action = True

        if args.no_push:
            continue

        push_lines = push_one(repo, dry_run)
        for line in push_lines:
            print(line)
            if "FAILED" in line:
                failures += 1
        any_action = True

    print()
    if not any_action:
        print("nothing to do.")
        return 0
    if failures:
        print(f"completed with {failures} failure(s) — see lines marked FAILED above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
