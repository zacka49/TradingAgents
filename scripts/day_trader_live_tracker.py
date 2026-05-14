from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from tradingagents.execution import AlpacaPaperBroker


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = REPO_ROOT / "results" / "autonomous_day_trader" / "live_logs"
DEFAULT_RESULTS_DIR = REPO_ROOT / "results" / "autonomous_day_trader"
TAIL_BYTES = 1_500_000
MAX_EVENTS = 1500


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Day Trader Live Tracker</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #1c2430;
      --muted: #657386;
      --line: #d9dee7;
      --panel: #ffffff;
      --good: #0b7a53;
      --bad: #b42318;
      --warn: #b7791f;
      --info: #145c8f;
      --soft: #eef2f7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif;
      font-size: 14px;
      line-height: 1.4;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }
    main {
      width: min(1500px, 100%);
      margin: 0 auto;
      padding: 16px;
      display: grid;
      gap: 16px;
    }
    .statusbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--soft);
      padding: 6px 10px;
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }
    .pill.good { color: var(--good); border-color: #b7dfce; background: #edf8f3; }
    .pill.bad { color: var(--bad); border-color: #f0b4aa; background: #fff1ef; }
    .pill.warn { color: var(--warn); border-color: #efd392; background: #fff8e6; }
    .grid {
      display: grid;
      gap: 16px;
    }
    .grid.top { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .grid.two { grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    section > h2 {
      margin: 0;
      padding: 11px 14px;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      font-weight: 700;
      color: #2f3a48;
      background: #fbfcfe;
      letter-spacing: 0;
    }
    .metric {
      padding: 14px;
      min-height: 96px;
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .metric .value {
      font-size: 24px;
      line-height: 1.05;
      font-weight: 750;
      overflow-wrap: anywhere;
    }
    .metric .sub {
      color: var(--muted);
      font-size: 12px;
      margin-top: 8px;
      overflow-wrap: anywhere;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      background: #fbfcfe;
    }
    tbody tr:last-child td { border-bottom: 0; }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .events {
      max-height: 470px;
      overflow: auto;
    }
    .event {
      display: grid;
      grid-template-columns: 168px 210px minmax(0, 1fr);
      gap: 10px;
      padding: 9px 12px;
      border-bottom: 1px solid var(--line);
      font-variant-numeric: tabular-nums;
    }
    .event:last-child { border-bottom: 0; }
    .event .time { color: var(--muted); }
    .event .name { font-weight: 650; color: #263241; }
    .event .detail { color: #3c4858; overflow-wrap: anywhere; }
    .error {
      color: var(--bad);
      background: #fff1ef;
      border: 1px solid #f0b4aa;
      border-radius: 8px;
      padding: 12px;
    }
    .small {
      color: var(--muted);
      font-size: 12px;
    }
    @media (max-width: 1100px) {
      .grid.top, .grid.two { grid-template-columns: 1fr 1fr; }
      .event { grid-template-columns: 140px minmax(0, 1fr); }
      .event .detail { grid-column: 1 / -1; }
    }
    @media (max-width: 720px) {
      header { align-items: flex-start; flex-direction: column; }
      .statusbar { justify-content: flex-start; }
      .grid.top, .grid.two { grid-template-columns: 1fr; }
      .event { grid-template-columns: 1fr; }
      main { padding: 10px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Day Trader Live Tracker</h1>
      <div class="small">Alpaca paper account only</div>
    </div>
    <div class="statusbar">
      <span id="botPill" class="pill">Bot unknown</span>
      <span id="marketPill" class="pill">Market unknown</span>
      <span id="updatedPill" class="pill">Waiting for data</span>
    </div>
  </header>
  <main>
    <div id="errors"></div>
    <div class="grid top">
      <section class="metric">
        <div class="label">Bot Process</div>
        <div id="botValue" class="value">...</div>
        <div id="botSub" class="sub"></div>
      </section>
      <section class="metric">
        <div class="label">Market Clock</div>
        <div id="clockValue" class="value">...</div>
        <div id="clockSub" class="sub"></div>
      </section>
      <section class="metric">
        <div class="label">Equity</div>
        <div id="equityValue" class="value">...</div>
        <div id="equitySub" class="sub"></div>
      </section>
      <section class="metric">
        <div class="label">Latest Cycle</div>
        <div id="cycleValue" class="value">...</div>
        <div id="cycleSub" class="sub"></div>
      </section>
    </div>
    <div class="grid two">
      <section>
        <h2>Positions</h2>
        <div id="positions"></div>
      </section>
      <section>
        <h2>Open Orders</h2>
        <div id="orders"></div>
      </section>
    </div>
    <div class="grid two">
      <section>
        <h2>Latest Bot Activity</h2>
        <div id="activity" class="events"></div>
      </section>
      <section>
        <h2>Session Counters</h2>
        <div id="counters"></div>
      </section>
    </div>
  </main>
  <script>
    const fmtMoney = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });
    const fmtNum = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });

    function num(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    function money(value) {
      const parsed = num(value);
      return parsed === null ? "n/a" : fmtMoney.format(parsed);
    }

    function pct(value) {
      const parsed = num(value);
      if (parsed === null) return "n/a";
      return (parsed * 100).toFixed(2) + "%";
    }

    function text(value) {
      return value === undefined || value === null || value === "" ? "n/a" : String(value);
    }

    function pill(el, label, kind) {
      el.textContent = label;
      el.className = "pill" + (kind ? " " + kind : "");
    }

    function table(headers, rows) {
      if (!rows.length) return '<div class="metric"><div class="sub">None</div></div>';
      const head = headers.map(h => `<th class="${h.cls || ""}">${h.label}</th>`).join("");
      const body = rows.map(row => "<tr>" + headers.map(h => `<td class="${h.cls || ""}">${row[h.key]}</td>`).join("") + "</tr>").join("");
      return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function eventDetail(e) {
      if (e.event === "autonomous_ceo_position_monitor") {
        const symbols = (e.positions || []).map(p => p.symbol).filter(Boolean).join(", ");
        const exits = (e.risk_exits || []).map(x => `${x.symbol || ""} ${x.reason || ""}`).join(", ");
        return `positions ${e.positions_count || 0}${symbols ? " (" + symbols + ")" : ""}; open orders ${e.open_orders_count || 0}${exits ? "; exits " + exits : ""}`;
      }
      if (e.event === "autonomous_ceo_profile_complete") {
        const top = (e.top_candidates || []).slice(0, 5).join(", ");
        return `${e.strategy_profile || ""}; top ${top || "none"}; submitted ${e.submitted_orders || 0}; blocked ${e.blocked_orders || 0}`;
      }
      if (e.event === "autonomous_ceo_trade_submitted") {
        return `${String(e.side || "").toUpperCase()} ${e.quantity || ""} ${e.ticker || ""} for ${money(e.estimated_notional_usd)}`;
      }
      if (e.event === "autonomous_ceo_trade_not_placed") {
        return `${String(e.side || "").toUpperCase()} ${e.ticker || ""}; ${e.blocked_reason || "blocked"}`;
      }
      if (e.event === "autonomous_ceo_cycle_start") {
        return `cycle ${e.cycle}; symbols ${(e.universe || []).length}`;
      }
      if (e.event === "autonomous_ceo_cycle") {
        return `cycle ${e.cycle} complete`;
      }
      if (e.event === "waiting_for_market_open") {
        return `waiting about ${Math.round((Number(e.wait_seconds) || 0) / 60)} minutes`;
      }
      if (e.event === "day_trader_bot_start") {
        return `profiles ${(e.settings && e.settings.profiles || []).join(", ")}; log ${e.log_file || ""}`;
      }
      if (e.event === "autonomous_ceo_eod_flatten_start" || e.event === "autonomous_ceo_eod_flatten_complete") {
        return e.reason || "";
      }
      return Object.entries(e)
        .filter(([k]) => !["event", "logged_at"].includes(k))
        .slice(0, 4)
        .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
        .join("; ");
    }

    function render(data) {
      const botRunning = Boolean(data.process && data.process.running);
      const clock = data.alpaca && data.alpaca.clock || {};
      const account = data.alpaca && data.alpaca.account || {};
      const log = data.log || {};

      pill(document.getElementById("botPill"), botRunning ? "Bot running" : "Bot stopped", botRunning ? "good" : "bad");
      pill(document.getElementById("marketPill"), clock.is_open ? "Market open" : "Market closed", clock.is_open ? "good" : "warn");
      pill(document.getElementById("updatedPill"), `Updated ${new Date(data.generated_at).toLocaleTimeString()}`, "");

      document.getElementById("botValue").textContent = botRunning ? "Running" : "Stopped";
      document.getElementById("botSub").textContent = botRunning ? `PID ${data.process.processes.map(p => p.pid).join(", ")}` : "No day-trader process found";

      document.getElementById("clockValue").textContent = clock.is_open ? "Open" : "Closed";
      document.getElementById("clockSub").textContent = `next open ${text(clock.next_open)}; next close ${text(clock.next_close)}`;

      document.getElementById("equityValue").textContent = money(account.equity || account.portfolio_value);
      document.getElementById("equitySub").textContent = `buying power ${money(account.buying_power)}; cash ${money(account.cash)}`;

      document.getElementById("cycleValue").textContent = text(log.latest_cycle);
      document.getElementById("cycleSub").textContent = log.latest_event ? `${log.latest_event.event || "event"} at ${text(log.latest_event.logged_at)}` : "No log event yet";

      const errors = [];
      (data.errors || []).forEach(err => errors.push(`<div class="error">${text(err.stage)}: ${text(err.error)}</div>`));
      document.getElementById("errors").innerHTML = errors.join("");

      const positions = (data.alpaca && data.alpaca.positions || []).map(p => ({
        symbol: text(p.symbol),
        qty: text(p.qty),
        value: money(p.market_value),
        pl: money(p.unrealized_pl),
        plpc: pct(p.unrealized_plpc),
        price: money(p.current_price)
      }));
      document.getElementById("positions").innerHTML = table([
        { key: "symbol", label: "Symbol" },
        { key: "qty", label: "Qty", cls: "num" },
        { key: "value", label: "Value", cls: "num" },
        { key: "pl", label: "Unrealized", cls: "num" },
        { key: "plpc", label: "P/L %", cls: "num" },
        { key: "price", label: "Price", cls: "num" }
      ], positions);

      const orders = (data.alpaca && data.alpaca.open_orders || []).map(o => ({
        symbol: text(o.symbol),
        side: text(o.side).toUpperCase(),
        qty: text(o.qty),
        type: text(o.type),
        status: text(o.status)
      }));
      document.getElementById("orders").innerHTML = table([
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side" },
        { key: "qty", label: "Qty", cls: "num" },
        { key: "type", label: "Type" },
        { key: "status", label: "Status" }
      ], orders);

      const events = (log.recent_events || []).slice(-35).reverse();
      document.getElementById("activity").innerHTML = events.length ? events.map(e => `
        <div class="event">
          <div class="time">${text(e.logged_at)}</div>
          <div class="name">${text(e.event)}</div>
          <div class="detail">${eventDetail(e)}</div>
        </div>
      `).join("") : '<div class="metric"><div class="sub">No bot log events yet</div></div>';

      const counters = Object.entries(log.event_counts || {})
        .sort((a, b) => b[1] - a[1])
        .map(([name, count]) => ({ name, count }));
      document.getElementById("counters").innerHTML = table([
        { key: "name", label: "Event" },
        { key: "count", label: "Count", cls: "num" }
      ], counters);
    }

    async function refresh() {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        render(data);
      } catch (error) {
        document.getElementById("errors").innerHTML = `<div class="error">tracker: ${error.message}</div>`;
      }
    }

    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a local Day Trader live tracker.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--json", action="store_true", help="Print one status payload and exit.")
    parser.add_argument("--no-alpaca", action="store_true", help="Skip Alpaca API calls.")
    return parser.parse_args(argv)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def latest_log_file(log_dir: Path) -> Path | None:
    files = sorted(log_dir.glob("day_trader_bot_*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def read_recent_jsonl(path: Path, max_events: int = MAX_EVENTS) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open("rb") as handle:
        try:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - TAIL_BYTES), os.SEEK_SET)
        except OSError:
            handle.seek(0)
        raw = handle.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    if lines and not lines[0].startswith("{"):
        lines = lines[1:]
    events: list[dict[str, Any]] = []
    for line in lines[-max_events:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def summarize_log(log_dir: Path) -> dict[str, Any]:
    log_path = latest_log_file(log_dir)
    if log_path is None:
        return {
            "path": None,
            "latest_event": None,
            "latest_cycle": None,
            "recent_events": [],
            "event_counts": {},
        }
    events = read_recent_jsonl(log_path)
    counts = Counter(str(event.get("event", "unknown")) for event in events)
    latest_cycle = None
    for event in reversed(events):
        if event.get("cycle") is not None:
            latest_cycle = event.get("cycle")
            break
    compact_events = [compact_event(event) for event in events[-80:]]
    latest_event = compact_event(events[-1]) if events else None
    return {
        "path": str(log_path),
        "modified_at": datetime.fromtimestamp(log_path.stat().st_mtime, UTC).isoformat(),
        "latest_event": latest_event,
        "latest_cycle": latest_cycle,
        "recent_events": compact_events,
        "event_counts": dict(counts),
    }


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    event_name = str(event.get("event", ""))
    base: dict[str, Any] = {
        "logged_at": event.get("logged_at"),
        "event": event_name,
    }
    for key in (
        "cycle",
        "strategy_profile",
        "stage",
        "reason",
        "action",
        "ticker",
        "symbol",
        "side",
        "quantity",
        "estimated_notional_usd",
        "blocked_reason",
        "submitted_orders",
        "blocked_orders",
        "positions_count",
        "open_orders_count",
        "seconds_to_next_cycle",
        "sleep_seconds",
        "wait_seconds",
        "exit_code",
        "error_type",
        "error",
    ):
        if key in event:
            base[key] = event[key]
    if "top_candidates" in event:
        base["top_candidates"] = list(event.get("top_candidates") or [])[:10]
    if "target_weights" in event:
        base["target_weights"] = event.get("target_weights") or {}
    if "positions" in event:
        base["positions"] = [
            {
                "symbol": position.get("symbol"),
                "qty": position.get("qty"),
                "market_value": position.get("market_value"),
                "unrealized_pl": position.get("unrealized_pl"),
                "unrealized_plpc": position.get("unrealized_plpc"),
                "current_price": position.get("current_price"),
            }
            for position in list(event.get("positions") or [])[:20]
            if isinstance(position, dict)
        ]
    if "risk_exits" in event:
        base["risk_exits"] = [
            {
                "symbol": exit_event.get("symbol"),
                "reason": exit_event.get("reason"),
                "submitted": exit_event.get("submitted"),
                "blocked_reason": exit_event.get("blocked_reason"),
            }
            for exit_event in list(event.get("risk_exits") or [])[:20]
            if isinstance(exit_event, dict)
        ]
    if event_name == "day_trader_bot_start":
        settings = event.get("settings") or {}
        if isinstance(settings, dict):
            base["settings"] = {
                "profiles": settings.get("profiles"),
                "interval_seconds": settings.get("interval_seconds"),
                "position_monitor_seconds": settings.get("position_monitor_seconds"),
                "flatten_at_close": settings.get("flatten_at_close"),
            }
        base["log_file"] = event.get("log_file")
    if event_name == "autonomous_ceo_cycle_start":
        base["universe_count"] = len(event.get("universe") or [])
    return base


def find_bot_processes() -> dict[str, Any]:
    if platform.system().lower() == "windows":
        command = (
            "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | "
            "Where-Object { $_.CommandLine -like '*run_day_trader_bot.py*' -or "
            "$_.CommandLine -like '*run_autonomous_day_trader.py*' } | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception as exc:
            return {"running": False, "processes": [], "error": str(exc)}
        if completed.returncode != 0:
            return {
                "running": False,
                "processes": [],
                "error": completed.stderr.strip() or completed.stdout.strip(),
            }
        output = completed.stdout.strip()
        if not output:
            return {"running": False, "processes": []}
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return {"running": False, "processes": [], "error": output}
        rows = parsed if isinstance(parsed, list) else [parsed]
        processes = [
            {
                "pid": row.get("ProcessId"),
                "command": row.get("CommandLine", ""),
            }
            for row in rows
            if isinstance(row, dict)
        ]
        return {"running": bool(processes), "processes": processes}

    try:
        completed = subprocess.run(
            ["ps", "-eo", "pid,args"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return {"running": False, "processes": [], "error": str(exc)}
    processes = []
    for line in completed.stdout.splitlines():
        if "run_day_trader_bot.py" in line or "run_autonomous_day_trader.py" in line:
            parts = line.strip().split(maxsplit=1)
            if parts and parts[0].isdigit():
                processes.append({"pid": int(parts[0]), "command": parts[1] if len(parts) > 1 else ""})
    return {"running": bool(processes), "processes": processes}


def alpaca_status(enabled: bool) -> tuple[dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    if not enabled:
        return {"enabled": False}, errors
    load_dotenv(REPO_ROOT / ".env", override=True)
    try:
        broker = AlpacaPaperBroker(timeout=8)
    except Exception as exc:
        return {"enabled": True}, [{"stage": "alpaca_init", "error": str(exc)}]

    payload: dict[str, Any] = {"enabled": True}
    for key, method, args in (
        ("clock", broker.get_clock, ()),
        ("account", broker.get_account, ()),
        ("positions", broker.get_positions, ()),
        ("open_orders", broker.get_orders, ("open",)),
    ):
        try:
            value = method(*args)
            if key == "positions":
                value = value.get("positions", [])
            elif key == "open_orders":
                value = value.get("orders", [])
            payload[key] = value
        except Exception as exc:
            errors.append({"stage": f"alpaca_{key}", "error": str(exc)})
            payload[key] = [] if key in {"positions", "open_orders"} else {}
    return payload, errors


def build_status(log_dir: Path, include_alpaca: bool = True) -> dict[str, Any]:
    alpaca, errors = alpaca_status(include_alpaca)
    process = find_bot_processes()
    if process.get("error"):
        errors.append({"stage": "process_check", "error": str(process["error"])})
    return {
        "generated_at": utc_now(),
        "process": process,
        "log": summarize_log(log_dir),
        "alpaca": alpaca,
        "errors": errors,
    }


class TrackerHandler(BaseHTTPRequestHandler):
    server_version = "DayTraderLiveTracker/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.write_response(200, "text/html; charset=utf-8", HTML.encode("utf-8"))
            return
        if parsed.path == "/api/status":
            payload = build_status(self.server.log_dir, include_alpaca=self.server.include_alpaca)  # type: ignore[attr-defined]
            self.write_response(
                200,
                "application/json; charset=utf-8",
                json.dumps(payload, default=str).encode("utf-8"),
            )
            return
        self.write_response(404, "text/plain; charset=utf-8", b"not found")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def write_response(self, status: int, content_type: str, body: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass


class TrackerServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        log_dir: Path,
        include_alpaca: bool,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.log_dir = log_dir
        self.include_alpaca = include_alpaca


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = REPO_ROOT / log_dir
    if args.json:
        print(json.dumps(build_status(log_dir, include_alpaca=not args.no_alpaca), indent=2))
        return 0

    server = TrackerServer(
        (args.host, args.port),
        TrackerHandler,
        log_dir=log_dir,
        include_alpaca=not args.no_alpaca,
    )
    url = f"http://{args.host}:{args.port}/"
    print(f"Day Trader Live Tracker listening on {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
