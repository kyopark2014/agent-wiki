#!/usr/bin/env python3
"""Export agent-wiki tasks.db turns to markdown corpus (no LLM)."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from lib.config import corpus_dir, tasks_db_path
from lib.corpus import export_turns, safe_slug
from lib.tasks_db import build_turns


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Examples:\n"
            "  python export_corpus.py                       # all users\n"
            "  python export_corpus.py --per-user            # corpus/{user}/\n"
            "  python export_corpus.py --user ksdyb          # one user\n"
            "  python export_corpus.py --user ksdyb --limit 20\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", type=Path, default=None, help="Path to tasks.db")
    parser.add_argument("--out", type=Path, default=None, help="Corpus output directory")
    parser.add_argument(
        "--user",
        default=None,
        help="Filter by user_id (omit to export all users)",
    )
    parser.add_argument(
        "--per-user",
        action="store_true",
        help="Write each user into corpus/{user}/",
    )
    parser.add_argument("--task-limit", type=int, default=None, help="Max tasks")
    parser.add_argument("--limit", type=int, default=None, help="Max turns")
    parser.add_argument("--prompt-max", type=int, default=2000, help="Max user chars")
    parser.add_argument("--reply-max", type=int, default=3000, help="Max assistant chars")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete existing turn-*.md before writing",
    )
    args = parser.parse_args()

    db = (args.db or tasks_db_path()).expanduser().resolve()
    out = (args.out or corpus_dir()).expanduser().resolve()
    turns = build_turns(
        db,
        user_id=args.user,
        task_limit=args.task_limit,
        turn_limit=args.limit,
    )

    if args.per_user:
        by_user: dict[str, list] = defaultdict(list)
        for turn in turns:
            by_user[turn.task.user_id].append(turn)
        total = 0
        print(f"Exporting {len(by_user)} user corpus folder(s) under {out}")
        for user_id, user_turns in sorted(by_user.items(), key=lambda x: (-len(x[1]), x[0])):
            user_dir = out / safe_slug(user_id)
            paths = export_turns(
                user_turns,
                user_dir,
                prompt_max=args.prompt_max,
                reply_max=args.reply_max,
                clean=not args.no_clean,
            )
            total += len(paths)
            print(f"  - {user_id}: {len(paths)} → {user_dir}")
        print(f"Exported {total} turn(s) from {db}")
        print()
        print("Next: python run_extract.py   # or python run_pipeline.py")
        return

    paths = export_turns(
        turns,
        out,
        prompt_max=args.prompt_max,
        reply_max=args.reply_max,
        clean=not args.no_clean,
    )

    by_user_counts = Counter(t.task.user_id for t in turns)
    scope = f"user={args.user}" if args.user else f"all users ({len(by_user_counts)})"
    print(f"Exported {len(paths)} turn(s) from {db} [{scope}]")
    for uid, n in by_user_counts.most_common():
        print(f"  - {uid}: {n}")
    print(f"Corpus: {out}")
    if paths:
        print(f"Example: {paths[0].name}")
    print()
    print("Next: python run_extract.py && python publish_out.py")
    print("  # or: python run_pipeline.py")


if __name__ == "__main__":
    main()
