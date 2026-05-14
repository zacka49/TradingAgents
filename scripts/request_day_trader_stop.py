from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path


DEFAULT_RESULTS_DIR = "results/autonomous_day_trader"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ask the running autonomous day trader to stop cleanly."
    )
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--stop-file",
        default=None,
        help=(
            "Override the stop-request file watched by the bot. Defaults to "
            "<results-dir>/control/stop_requested.json."
        ),
    )
    parser.add_argument(
        "--action",
        choices=["flatten", "stop"],
        default="flatten",
        help=(
            "flatten cancels working orders and closes paper positions before "
            "exit; stop exits without flattening."
        ),
    )
    parser.add_argument("--reason", default="manual stop requested")
    return parser


def resolve_stop_file(results_dir: str, stop_file: str | None) -> Path:
    if stop_file:
        return Path(stop_file)
    return Path(results_dir) / "control" / "stop_requested.json"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = resolve_stop_file(args.results_dir, args.stop_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "action": args.action,
        "reason": args.reason,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    print(f"Stop request written: {path}")
    print(f"Action: {args.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
