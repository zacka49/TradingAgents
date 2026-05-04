"""Minimal TradingView webhook receiver.

Receives TradingView alert payloads via HTTP POST and appends them to
results/webhooks/tradingview_alerts.jsonl.

Use only on trusted local networks or behind an authenticated tunnel.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv


class Handler(BaseHTTPRequestHandler):
    secret: str = ""
    output_path: Path

    def _json_response(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length).decode("utf-8")

        # Optional shared-secret guard: expect JSON with {"secret":"..."}.
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}

        if self.secret:
            provided = data.get("secret") if isinstance(data, dict) else None
            if provided != self.secret:
                self._json_response(401, {"ok": False, "error": "invalid secret"})
                return

        event = {
            "received_at_utc": datetime.now(timezone.utc).isoformat(),
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "payload": data,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        self._json_response(200, {"ok": True})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--output",
        default=str(Path("results") / "webhooks" / "tradingview_alerts.jsonl"),
    )
    args = parser.parse_args()

    load_dotenv(".env", override=True)
    Handler.secret = os.getenv("TRADINGVIEW_WEBHOOK_SECRET", "")
    Handler.output_path = Path(args.output)

    server = HTTPServer((args.host, args.port), Handler)
    print(f"TradingView webhook receiver listening on http://{args.host}:{args.port}")
    print(f"Writing alerts to: {Handler.output_path.resolve()}")
    if Handler.secret:
        print("Secret check enabled via TRADINGVIEW_WEBHOOK_SECRET")
    else:
        print("Warning: no webhook secret configured")
    server.serve_forever()


if __name__ == "__main__":
    main()
