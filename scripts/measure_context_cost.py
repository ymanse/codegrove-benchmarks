#!/usr/bin/env python3
"""Measure what it costs an agent to answer "where does X happen?" in a repository.

Three arms, one question, one repository:

  A. no index      - grep/glob/read only, the way an agent works without a code index
  B. LSP           - a language server (clangd/jdtls/...) queried per file
  C. code graph    - one query against a parsed graph of the repository

Arm A and B are what this script measures directly. Arm C requires a running
CodeGrove instance and is recorded from its own `latency_ms` field.

The point is not that one tool is "better". They answer different questions:

  - grep finds strings and gives no ranking, so the agent must open files to rank them
  - an LSP is exact but needs to be told *which file* - which is the thing you do not know
  - a graph query ranks candidates across the repository from a natural-language question

Usage
-----
    python measure_context_cost.py <repo-path> [--pattern REGEX] [--json OUT]

Requires `tiktoken` (cl100k_base) for token counts. Everything else is stdlib.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import tiktoken
except ImportError:  # pragma: no cover - dependency hint only
    sys.exit("this script needs tiktoken:  pip install tiktoken")

ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(ENC.encode(text))


def run(cmd: list[str], cwd: Path) -> tuple[str, float]:
    """Run a command, returning (stdout, elapsed_ms)."""
    started = time.perf_counter()
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.stdout or "", (time.perf_counter() - started) * 1000


def measure_file_listing(repo: Path) -> dict:
    """What a full file listing costs. This is the floor: nothing has been opened yet."""
    out, elapsed = run(["git", "ls-files"], repo)
    files = [line for line in out.splitlines() if line.strip()]
    tokens = count_tokens(out)
    return {
        "arm": "file-listing",
        "files": len(files),
        "tokens": tokens,
        "tokens_per_file": round(tokens / max(len(files), 1), 2),
        "elapsed_ms": round(elapsed),
    }


def measure_grep(repo: Path, pattern: str, includes: list[str]) -> dict:
    """What one grep costs. Fast and cheap - but unranked, so it is not yet an answer."""
    cmd = ["grep", "-rn", "-i"] + [f"--include={g}" for g in includes] + [pattern, "."]
    out, elapsed = run(cmd, repo)
    hits = [line for line in out.splitlines() if line.strip()]
    return {
        "arm": "grep",
        "pattern": pattern,
        "hits": len(hits),
        "tokens": count_tokens(out),
        "elapsed_ms": round(elapsed),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", type=Path)
    ap.add_argument(
        "--pattern",
        default="permission",
        help="regex for the grep arm (default: permission)",
    )
    ap.add_argument(
        "--include",
        action="append",
        default=None,
        help="glob for grep, repeatable (default: *.cpp *.h *.java *.kt *.ts *.py)",
    )
    ap.add_argument("--json", type=Path, help="write results here as JSON")
    args = ap.parse_args()

    if not (args.repo / ".git").exists():
        sys.exit(f"not a git repository: {args.repo}")

    includes = args.include or ["*.cpp", "*.h", "*.java", "*.kt", "*.ts", "*.py"]

    results = [
        measure_file_listing(args.repo),
        measure_grep(args.repo, args.pattern, includes),
    ]

    width = max(len(r["arm"]) for r in results)
    print(f"repository: {args.repo}")
    for r in results:
        extra = (
            f"{r['files']:>7,} files"
            if "files" in r
            else f"{r['hits']:>7,} hits "
        )
        print(f"  {r['arm']:<{width}}  {r['elapsed_ms']:>7,} ms  {extra}  {r['tokens']:>8,} tokens")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
