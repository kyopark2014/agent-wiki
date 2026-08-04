#!/usr/bin/env python3
"""Full standalone pipeline: tasks.db → corpus → LLM extract → out/graph_{user}.html.

Does NOT use the Cursor /graphify skill. Requires LiteLLM gateway credentials.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(HERE))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_pipeline.py\n"
            "  python run_pipeline.py --user ksdyb --limit 10\n"
            "  python run_pipeline.py --skip-export   # reuse corpus/\n"
            "  python run_pipeline.py --skip-extract  # reuse graphify-out/graph.json\n"
        ),
    )
    parser.add_argument("--user", default=None, help="Filter export by user_id")
    parser.add_argument("--limit", type=int, default=None, help="Max turns on export")
    parser.add_argument("--per-user", action="store_true", help="corpus/{user}/ layout")
    parser.add_argument("--deep", action="store_true", help="Deep semantic extraction")
    parser.add_argument("--model", default=None, help="Override GRAPHIFY_LLM_MODEL")
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--file-limit", type=int, default=None, help="Max .md files to extract")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_export:
        cmd = [py, "export_corpus.py"]
        if args.user:
            cmd += ["--user", args.user]
        if args.limit is not None:
            cmd += ["--limit", str(args.limit)]
        if args.per_user:
            cmd.append("--per-user")
        _run(cmd)

    if not args.skip_extract:
        cmd = [py, "run_extract.py", "--chunk-size", str(args.chunk_size)]
        if args.deep:
            cmd.append("--deep")
        if args.model:
            cmd += ["--model", args.model]
        if args.file_limit is not None:
            cmd += ["--limit", str(args.file_limit)]
        _run(cmd)

    if not args.skip_publish:
        graph = HERE / "graphify-out" / "graph.json"
        cmd = [py, "publish_out.py", "--graph", str(graph)]
        if args.user:
            cmd += ["--user", args.user]
        _run(cmd)

    print()
    print("Done. Open e.g.: open out/graph_ksdyb.html")


if __name__ == "__main__":
    main()
