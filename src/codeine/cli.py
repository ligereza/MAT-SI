"""Terminal interface for CODEINE v0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .core import (
    CodeineError,
    assess,
    checkpoint,
    finish,
    replay_export,
    replay_session,
    start,
    write_export,
)


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _common_session(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session", type=Path, default=None, help="session JSON path (default: artifacts/codeine-v0/session.json)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codeine", description="CODEINE v0 auditable local Git checkpoints")
    commands = parser.add_subparsers(dest="command", required=True)

    start_parser = commands.add_parser("start", help="capture the initial before snapshot")
    start_parser.add_argument("--repo", type=Path, default=Path("."))
    _common_session(start_parser)
    start_parser.add_argument("--test-command", default=None, help="command to run at every snapshot")
    start_parser.add_argument("--task", default=None, help="human context only; not an observation label")
    start_parser.add_argument("--force", action="store_true", help="replace a finished or abandoned local session")

    checkpoint_parser = commands.add_parser("checkpoint", help="capture one opaque intervention and its after snapshot")
    _common_session(checkpoint_parser)
    checkpoint_parser.add_argument("--token", default=None, help="opaque token; its wording is hashed and not retained")

    assess_parser = commands.add_parser("assess", help="emit the explicit persistence recommendation")
    _common_session(assess_parser)
    assess_parser.add_argument("--summary", action="store_true", help="print only the decision and its evidence")

    finish_parser = commands.add_parser("finish", help="capture final observation and close the session")
    _common_session(finish_parser)

    export_parser = commands.add_parser("export", help="write the deterministic committable session record")
    _common_session(export_parser)
    export_parser.add_argument("--out", type=Path, default=None, help="export path (default: results/codeine-session-export.json)")

    replay_parser = commands.add_parser("replay", help="recompute recommendations from recorded observations")
    _common_session(replay_parser)
    replay_parser.add_argument("--export", type=Path, default=None, help="replay this export instead of the local session")
    replay_parser.add_argument("--verify-export", type=Path, default=None, help="also check the export is byte-for-byte reproducible from the session")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            result = start(args.repo, args.session, args.test_command, args.task, args.force)
        elif args.command == "checkpoint":
            result = checkpoint(args.session, args.token)
        elif args.command == "assess":
            result = assess(args.session)
            if args.summary:
                recommendation = result["recommendation"]
                result = {
                    "decision": result["decision"],
                    "recommendation_id": recommendation["recommendation_id"],
                    "evidence_for": recommendation["evidence_for"],
                    "evidence_against": recommendation["evidence_against"],
                    "evidence_strength": recommendation["evidence_strength"],
                    "reason": recommendation["reason"],
                }
        elif args.command == "export":
            result = write_export(args.session, args.out)
        elif args.command == "replay":
            if args.export is not None:
                result = replay_export(args.export)
            else:
                result = replay_session(args.session, args.verify_export)
        else:
            result = finish(args.session)
        _emit(result)
        return 0 if result.get("deterministic", True) else 1
    except (CodeineError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"codeine: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
