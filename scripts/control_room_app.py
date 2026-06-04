from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from tradingagents.execution import AlpacaPaperBroker


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results" / "autonomous_day_trader"
LIVE_LOG_DIR = RESULTS_DIR / "live_logs"
CONTROL_DIR = RESULTS_DIR / "control"
CONTROL_ROOM_DIR = REPO_ROOT / "results" / "control_room"
TASK_DIR = CONTROL_ROOM_DIR / "department_tasks"
PROCESS_LOG_DIR = CONTROL_ROOM_DIR / "process_logs"
STRATEGY_EVIDENCE_DIR = REPO_ROOT / "results" / "research_department" / "strategy_evidence_2026-06-02"
TAIL_BYTES = 1_500_000
MAX_EVENTS = 900


DEPARTMENTS: dict[str, dict[str, str]] = {
    "research_director": {
        "name": "Research Director",
        "charter": (
            "Synthesize specialist research into a CEO-ready view. Separate signal, "
            "uncertainty, and what evidence is still missing."
        ),
        "teaches": "How raw research becomes a decision brief.",
    },
    "strategy_researcher": {
        "name": "Strategy Researcher",
        "charter": (
            "Turn market evidence into setup hypotheses. Focus on entry conditions, "
            "confirmation signals, invalidation, and when not to trade."
        ),
        "teaches": "How a trade setup differs from a ticker idea.",
    },
    "risk_office": {
        "name": "Risk Office",
        "charter": (
            "Challenge the trade or process. Look for exposure, drawdown, duplicate "
            "entries, open-order risk, and operational failure modes."
        ),
        "teaches": "How risk controls protect the business from clever bad ideas.",
    },
    "portfolio_office": {
        "name": "Portfolio Office",
        "charter": (
            "Translate strategy into sizing and concentration rules. Keep exposure, "
            "cash, and position count aligned with the account state."
        ),
        "teaches": "Why sizing is a separate decision from direction.",
    },
    "trading_desk": {
        "name": "Trading Desk",
        "charter": (
            "Plan execution only. Consider timing, order class, duplicate orders, "
            "liquidity, brackets, and whether the market is open."
        ),
        "teaches": "How execution quality can make or break a correct thesis.",
    },
    "operations_compliance": {
        "name": "Operations and Compliance",
        "charter": (
            "Audit process readiness. Check preflight, logs, final reports, account "
            "state, approvals, and whether the system can be explained later."
        ),
        "teaches": "Why repeatable process matters before scaling risk.",
    },
    "training_development": {
        "name": "Training and Development",
        "charter": (
            "Convert outcomes into role-specific lessons. Identify examples that "
            "should become evaluation data before any fine-tuning."
        ),
        "teaches": "How to train agents without jumping straight to fine-tuning.",
    },
    "technology_scout": {
        "name": "Technology Scout",
        "charter": (
            "Suggest technical improvements that reduce operational risk or improve "
            "research quality without adding unnecessary complexity."
        ),
        "teaches": "How tooling choices shape the business workflow.",
    },
    "evaluation": {
        "name": "Evaluation Department",
        "charter": (
            "Score a decision or session against objectives. Identify what worked, "
            "what failed, and which metric should decide the next experiment."
        ),
        "teaches": "How to turn a trading day into measurable learning.",
    },
}


ORG_FLOW: list[dict[str, str]] = [
    {
        "stage": "1",
        "name": "Market Data",
        "owner": "Research feeds",
        "detail": "Alpaca account state, Yahoo price history, news/policy discovery, and generated strategy evidence.",
    },
    {
        "stage": "2",
        "name": "Research Director",
        "owner": "Research department",
        "detail": "Combines raw evidence into a CEO-ready context brief and routes specialist questions.",
    },
    {
        "stage": "3",
        "name": "Strategy Researcher",
        "owner": "Strategy desk",
        "detail": "Turns tickers into setup hypotheses with confirmation, invalidation, and avoid rules.",
    },
    {
        "stage": "4",
        "name": "Risk Office",
        "owner": "Risk department",
        "detail": "Challenges the setup against exposure, startup gate, drawdown, duplicate orders, and carry risk.",
    },
    {
        "stage": "5",
        "name": "Portfolio Office",
        "owner": "Portfolio department",
        "detail": "Converts approved ideas into position count, gross exposure, sizing, and concentration limits.",
    },
    {
        "stage": "6",
        "name": "Trading Desk",
        "owner": "Execution desk",
        "detail": "Plans paper execution only after strategy, risk, and portfolio gates agree.",
    },
    {
        "stage": "7",
        "name": "Operations and Compliance",
        "owner": "Control room",
        "detail": "Checks preflight, logs, reports, approvals, and whether the process can be reconstructed later.",
    },
    {
        "stage": "8",
        "name": "CEO",
        "owner": "Final decision",
        "detail": "Makes the go/no-go decision, starts or stops the bot, and writes the business-level report.",
    },
    {
        "stage": "9",
        "name": "Evaluation and Training",
        "owner": "Learning loop",
        "detail": "Turns outcomes into scorecards, lessons, agent training data, and future system improvements.",
    },
]


UNIVERSE_GROUPS: dict[str, dict[str, Any]] = {
    "equity_core": {
        "name": "Core equity/ETF bot universe",
        "symbols": [
            "AMD",
            "NVDA",
            "INTC",
            "QQQ",
            "SPY",
            "PLTR",
            "MU",
            "TSLA",
            "HOOD",
            "AAPL",
            "MSFT",
            "META",
            "AMZN",
            "GOOGL",
            "AVGO",
            "ARM",
            "SMCI",
            "CRWD",
            "PANW",
            "JPM",
            "BAC",
            "GS",
            "XLF",
            "LLY",
            "NVO",
            "UNH",
            "XLV",
            "XOM",
            "CVX",
            "XLE",
            "LMT",
            "NOC",
            "RTX",
            "ITA",
            "TLT",
            "GLD",
            "UUP",
            "FXE",
            "FXY",
            "FXB",
            "FXA",
            "FXC",
            "IWM",
            "SOXX",
        ],
        "mode": "paper bot",
        "note": "Main universe for Alpaca paper stock/ETF execution.",
    },
    "crypto_linked_tradeable": {
        "name": "Crypto-linked paper-tradable instruments",
        "symbols": ["COIN", "MSTR", "IBIT", "GBTC", "BITO", "ETHA", "ETHE"],
        "mode": "paper bot",
        "note": "Equities/ETFs that give the bot crypto exposure without direct crypto order routing.",
    },
    "direct_crypto_research": {
        "name": "Direct crypto research symbols",
        "symbols": [
            "BTC-USD",
            "ETH-USD",
            "SOL-USD",
            "XRP-USD",
            "BNB-USD",
            "DOGE-USD",
            "ADA-USD",
            "LINK-USD",
        ],
        "mode": "research only",
        "note": "Included in strategy evidence. Execution stays disabled until a crypto-aware broker adapter is added.",
    },
}


@dataclass
class AppState:
    bot_process: subprocess.Popen[Any] | None = None
    bot_started_at: str = ""
    bot_command: list[str] | None = None
    research_process: subprocess.Popen[Any] | None = None
    research_started_at: str = ""
    research_command: list[str] | None = None


APP_STATE = AppState()


DEFAULT_PROJECTG_UNIVERSE = ",".join(
    [
        *UNIVERSE_GROUPS["equity_core"]["symbols"],
        *UNIVERSE_GROUPS["crypto_linked_tradeable"]["symbols"],
    ]
)


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ProjectG Quant Control Room</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-soft: #fbfcff;
      --ink: #18212f;
      --muted: #647286;
      --line: #d9e0ea;
      --accent: #176b87;
      --accent-soft: #e8f4f7;
      --good: #087443;
      --good-soft: #e8f7ef;
      --bad: #b42318;
      --bad-soft: #fff0ed;
      --warn: #9a6700;
      --warn-soft: #fff7df;
      --code: #f0f4f8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(255,255,255,0.96);
      border-bottom: 1px solid var(--line);
    }
    .head-inner {
      width: min(1640px, 100%);
      margin: 0 auto;
      padding: 14px 18px;
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 16px;
      align-items: center;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
      line-height: 1.1;
    }
    .subhead {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    button, select, input, textarea {
      font: inherit;
    }
    button {
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--ink);
      border-radius: 7px;
      padding: 8px 11px;
      cursor: pointer;
      min-height: 36px;
    }
    button:hover { border-color: #b7c3d2; background: #f9fbfe; }
    button.primary { background: var(--accent); border-color: var(--accent); color: white; }
    button.good { background: var(--good); border-color: var(--good); color: white; }
    button.warn { background: var(--warn-soft); border-color: #efd48b; color: #5c4200; }
    button.bad { background: var(--bad-soft); border-color: #f2b8ae; color: var(--bad); }
    button.ghost { background: transparent; }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    main {
      width: min(1640px, 100%);
      margin: 0 auto;
      padding: 16px 18px 28px;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }
    .tab {
      border-radius: 999px;
      padding: 7px 12px;
      background: #ffffff;
      border: 1px solid var(--line);
      color: var(--muted);
    }
    .tab.active {
      color: var(--accent);
      border-color: #9fcbd7;
      background: var(--accent-soft);
      font-weight: 700;
    }
    .view { display: none; }
    .view.active { display: grid; gap: 16px; }
    .grid { display: grid; gap: 16px; }
    .metrics { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .two { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
    .three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .wide-left { grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr); }
    section, .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    section > .section-head {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-soft);
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
    }
    h2, h3 {
      margin: 0;
      letter-spacing: 0;
      line-height: 1.2;
    }
    h2 { font-size: 14px; }
    h3 { font-size: 13px; }
    .body { padding: 14px; }
    .metric {
      padding: 14px;
      min-height: 112px;
    }
    .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 7px;
    }
    .value {
      font-size: 24px;
      line-height: 1.05;
      font-weight: 780;
      overflow-wrap: anywhere;
    }
    .sub {
      color: var(--muted);
      font-size: 12px;
      margin-top: 8px;
      overflow-wrap: anywhere;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      background: #f2f5f9;
      color: var(--muted);
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      white-space: nowrap;
    }
    .pill.good { color: var(--good); background: var(--good-soft); border-color: #aedfc8; }
    .pill.bad { color: var(--bad); background: var(--bad-soft); border-color: #efb4aa; }
    .pill.warn { color: var(--warn); background: var(--warn-soft); border-color: #eed18a; }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      text-align: left;
      vertical-align: top;
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      background: #fbfcff;
    }
    tbody tr:last-child td { border-bottom: 0; }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .muted { color: var(--muted); }
    .ok { color: var(--good); font-weight: 700; }
    .bad-text { color: var(--bad); font-weight: 700; }
    .warn-text { color: var(--warn); font-weight: 700; }
    .events {
      max-height: 520px;
      overflow: auto;
    }
    .event {
      display: grid;
      grid-template-columns: 166px 220px minmax(0, 1fr);
      gap: 10px;
      padding: 9px 12px;
      border-bottom: 1px solid var(--line);
      font-variant-numeric: tabular-nums;
    }
    .event:last-child { border-bottom: 0; }
    .event .time { color: var(--muted); }
    .event .name { font-weight: 700; color: #263141; }
    .event .detail { color: #3f4b5c; overflow-wrap: anywhere; }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .chart {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: white;
      min-height: 240px;
    }
    .chart img {
      display: block;
      width: 100%;
      height: auto;
    }
    .control-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
      gap: 16px;
    }
    .run-form {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      align-items: end;
    }
    .run-form .full { grid-column: 1 / -1; }
    .toggle-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 10px;
    }
    .toggle {
      display: inline-flex;
      gap: 7px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 10px;
      background: #ffffff;
      color: #314055;
      font-size: 12px;
      font-weight: 700;
    }
    .toggle input {
      width: auto;
      min-height: 0;
      margin: 0;
    }
    .allocation-list {
      display: grid;
      gap: 10px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: 64px minmax(0, 1fr) 62px;
      gap: 10px;
      align-items: center;
    }
    .bar-shell {
      min-width: 0;
      height: 12px;
      border: 1px solid #c8d3df;
      border-radius: 999px;
      background: #eef2f7;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #176b87, #0b744f);
    }
    .sparkline {
      width: 100%;
      min-height: 120px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 8px;
    }
    .sparkline svg {
      width: 100%;
      height: 118px;
      display: block;
    }
    .org-map {
      display: grid;
      grid-template-columns: repeat(5, minmax(170px, 1fr));
      gap: 10px;
      align-items: stretch;
    }
    .org-node {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 11px;
      min-height: 148px;
      display: grid;
      gap: 7px;
      align-content: start;
      position: relative;
    }
    .org-node::after {
      content: "->";
      position: absolute;
      right: -13px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-weight: 800;
    }
    .org-node:last-child::after { content: ""; }
    .org-stage {
      display: inline-flex;
      width: fit-content;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid #9fcbd7;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 750;
    }
    .org-owner {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .org-detail {
      color: #3f4b5c;
      font-size: 12px;
    }
    .universe-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .universe-group {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px;
      background: #ffffff;
    }
    .chip-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }
    .asset-chip {
      border: 1px solid var(--line);
      background: #f2f5f9;
      color: #2d3a4b;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      font-weight: 700;
    }
    .asset-chip.crypto { background: #eef7f1; border-color: #b7ddc2; color: #0b6b3a; }
    .asset-chip.research { background: #fff7df; border-color: #efd18a; color: #6d4b00; }
    .learn-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .lesson {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #ffffff;
      min-height: 140px;
    }
    .lesson .step {
      color: var(--accent);
      font-size: 12px;
      font-weight: 750;
      margin-bottom: 6px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 220px minmax(120px, 1fr) 180px;
      gap: 10px;
      align-items: end;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    select, input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #ffffff;
      color: var(--ink);
      padding: 9px 10px;
      min-height: 38px;
    }
    textarea {
      min-height: 150px;
      resize: vertical;
      line-height: 1.45;
    }
    .memo {
      white-space: pre-wrap;
      background: var(--code);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      max-height: 560px;
      overflow: auto;
    }
    .notice {
      border: 1px solid #9fcbd7;
      background: var(--accent-soft);
      border-radius: 8px;
      padding: 12px;
      color: #214656;
    }
    .notice.warn {
      border-color: #efd18a;
      background: var(--warn-soft);
      color: #5c4200;
    }
    .notice.bad {
      border-color: #f0b4aa;
      background: var(--bad-soft);
      color: var(--bad);
    }
    code {
      background: var(--code);
      padding: 2px 5px;
      border-radius: 5px;
    }
    @media (max-width: 1220px) {
      .metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .learn-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .two, .three, .wide-left, .chart-grid, .universe-grid, .control-grid { grid-template-columns: 1fr; }
      .run-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .org-map { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .org-node::after { content: ""; }
      .event { grid-template-columns: 150px minmax(0, 1fr); }
      .event .detail { grid-column: 1 / -1; }
      .form-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .head-inner { grid-template-columns: 1fr; }
      nav { justify-content: flex-start; }
      main { padding: 12px; }
      .metrics, .learn-grid { grid-template-columns: 1fr; }
      .run-form { grid-template-columns: 1fr; }
      .org-map { grid-template-columns: 1fr; }
      .event { grid-template-columns: 1fr; }
      .toolbar { align-items: stretch; }
      .toolbar button { flex: 1 1 auto; }
    }
  </style>
</head>
<body>
  <header>
    <div class="head-inner">
      <div>
        <h1>ProjectG Quant Control Room</h1>
        <div class="subhead">Visual paper-account cockpit for research, allocation, execution, review, and learning</div>
      </div>
      <nav>
        <button id="refreshBtn" class="primary">Refresh</button>
        <button id="preflightBtn">Run Preflight</button>
        <button id="startBtn" class="good">Start Bot</button>
        <button id="flattenStartBtn" class="warn">Start + Flatten</button>
        <button id="stopFlattenBtn" class="bad">Stop + Flatten</button>
      </nav>
    </div>
  </header>
  <main>
    <div class="tabs">
      <button class="tab active" data-view="run">Run ProjectG</button>
      <button class="tab" data-view="dashboard">Dashboard</button>
      <button class="tab" data-view="strategy">Strategy Lab</button>
      <button class="tab" data-view="departments">Departments</button>
      <button class="tab" data-view="learning">Learning</button>
      <button class="tab" data-view="reports">Reports</button>
    </div>

    <div id="run" class="view active">
      <div id="projectgNotice"></div>
      <div class="grid metrics">
        <section class="metric"><div class="label">Paper Wealth</div><div id="pgEquityValue" class="value">...</div><div id="pgEquitySub" class="sub"></div></section>
        <section class="metric"><div class="label">Daily P/L</div><div id="pgDailyValue" class="value">...</div><div id="pgDailySub" class="sub"></div></section>
        <section class="metric"><div class="label">CEO Decision</div><div id="pgDecisionValue" class="value">...</div><div id="pgDecisionSub" class="sub"></div></section>
        <section class="metric"><div class="label">Research Job</div><div id="pgResearchValue" class="value">...</div><div id="pgResearchSub" class="sub"></div></section>
        <section class="metric"><div class="label">Execution Bot</div><div id="pgBotValue" class="value">...</div><div id="pgBotSub" class="sub"></div></section>
      </div>
      <div class="control-grid">
        <section>
          <div class="section-head">
            <h2>ProjectG Run Cockpit</h2>
            <span class="pill warn">Alpaca paper only</span>
          </div>
          <div class="body">
            <div class="run-form">
              <label>Bot strategy
                <select id="pgBotStrategy">
                  <option value="both">Safe + risky</option>
                  <option value="safe">Safe only</option>
                  <option value="risky">Risky only</option>
                </select>
              </label>
              <label>CEO research profile
                <select id="pgResearchProfile">
                  <option value="safe">Safe</option>
                  <option value="risky">Risky</option>
                  <option value="balanced">Balanced</option>
                </select>
              </label>
              <label>Interval seconds<input id="pgInterval" type="number" min="5" step="5" value="30"></label>
              <label>Max cycles<input id="pgMaxCycles" type="number" min="0" step="1" value="0"></label>
              <label>Max deploy $<input id="pgMaxDeploy" type="number" min="0" step="100" placeholder="profile default"></label>
              <label>Max order $<input id="pgMaxOrder" type="number" min="0" step="100" placeholder="profile default"></label>
              <label>Target positions<input id="pgTargets" type="number" min="1" step="1" placeholder="profile default"></label>
              <label>Alpaca feed
                <select id="pgFeed">
                  <option value="">Default</option>
                  <option value="iex">IEX</option>
                  <option value="sip">SIP</option>
                  <option value="delayed_sip">Delayed SIP</option>
                  <option value="overnight">Overnight</option>
                  <option value="otc">OTC</option>
                </select>
              </label>
              <label class="full">Universe<textarea id="pgUniverse"></textarea></label>
            </div>
            <div class="toggle-row">
              <label class="toggle"><input id="pgNews" type="checkbox" checked> News scan</label>
              <label class="toggle"><input id="pgPremarket" type="checkbox" checked> Premarket research</label>
              <label class="toggle"><input id="pgStaffMemo" type="checkbox"> Staff memo</label>
              <label class="toggle"><input id="pgTechScout" type="checkbox"> Tech scout</label>
            </div>
            <div style="height:12px"></div>
            <div class="toolbar">
              <button id="pgPreflightBtn">Preflight</button>
              <button id="pgResearchBtn" class="primary">Run CEO Research</button>
              <button id="pgEvidenceBtn">Generate Evidence</button>
              <button id="pgStartBtn" class="good">Start Paper Bot</button>
              <button id="pgOnceBtn">One Cycle</button>
              <button id="pgFlattenStartBtn" class="warn">Start + Flatten</button>
              <button id="pgStopFlattenBtn" class="bad">Stop + Flatten</button>
            </div>
            <div id="projectgActionResult" class="sub"></div>
          </div>
        </section>
        <section>
          <div class="section-head"><h2>Paper Account Curve</h2><span id="pgCurvePill" class="pill">...</span></div>
          <div class="body">
            <div id="pgSparkline" class="sparkline"></div>
            <div style="height:12px"></div>
            <div id="pgSessionTable"></div>
          </div>
        </section>
      </div>
      <div class="grid two">
        <section>
          <div class="section-head"><h2>Latest CEO Research Decision</h2><span id="pgDecisionPill" class="pill">...</span></div>
          <div id="pgDecisionSummary" class="body"></div>
        </section>
        <section>
          <div class="section-head"><h2>Capital Allocation</h2><span id="pgAllocationPill" class="pill">...</span></div>
          <div id="pgAllocation" class="body"></div>
        </section>
      </div>
      <div class="grid two">
        <section>
          <div class="section-head"><h2>Top Candidates</h2><span class="pill">Research ranking</span></div>
          <div id="pgCandidates"></div>
        </section>
        <section>
          <div class="section-head"><h2>Recent Activity</h2><span class="pill">Live log</span></div>
          <div id="pgActivity" class="events"></div>
        </section>
      </div>
    </div>

    <div id="dashboard" class="view">
      <div id="topNotice"></div>
      <div class="grid metrics">
        <section class="metric"><div class="label">Startup Gate</div><div id="gateValue" class="value">...</div><div id="gateSub" class="sub"></div></section>
        <section class="metric"><div class="label">Bot Process</div><div id="botValue" class="value">...</div><div id="botSub" class="sub"></div></section>
        <section class="metric"><div class="label">Market Clock</div><div id="clockValue" class="value">...</div><div id="clockSub" class="sub"></div></section>
        <section class="metric"><div class="label">Equity</div><div id="equityValue" class="value">...</div><div id="equitySub" class="sub"></div></section>
        <section class="metric"><div class="label">Latest Cycle</div><div id="cycleValue" class="value">...</div><div id="cycleSub" class="sub"></div></section>
      </div>
      <section>
        <div class="section-head">
          <h2>Business Organagram and Information Flow</h2>
          <span class="pill">Agents, gates, and feedback loops</span>
        </div>
        <div class="body">
          <div id="organagram" class="org-map"></div>
          <div style="height:14px"></div>
          <div class="notice">
            Information flows left to right until the CEO makes a go/no-go decision. After the session, reports flow back into Evaluation and Training so the agents improve from evidence rather than vibes.
          </div>
        </div>
      </section>
      <section>
        <div class="section-head">
          <h2>Ticker Coverage</h2>
          <span class="pill warn">Crypto research added</span>
        </div>
        <div class="body">
          <div id="universeBreakdown" class="universe-grid"></div>
        </div>
      </section>
      <div class="grid two">
        <section>
          <div class="section-head"><h2>Safety Checks</h2><span id="readyPill" class="pill">Unknown</span></div>
          <div id="safetyChecks" class="body"></div>
        </section>
        <section>
          <div class="section-head"><h2>Run Controls</h2><span class="pill warn">Paper only</span></div>
          <div class="body">
            <div class="notice warn">
              Start Bot uses the safe default: the bot itself refuses to start if positions or orders already exist. Start + Flatten asks it to flatten first, then run. Stop + Flatten writes the watched control file.
            </div>
            <div style="height:12px"></div>
            <div class="toolbar">
              <button id="startOnceBtn">One Cycle</button>
              <button id="allowCarryBtn" class="warn">Start With Carry Risk</button>
              <button id="stopOnlyBtn">Stop Only</button>
            </div>
            <div id="actionResult" class="sub"></div>
          </div>
        </section>
      </div>
      <div class="grid two">
        <section><div class="section-head"><h2>Positions</h2><span id="positionsPill" class="pill">...</span></div><div id="positions"></div></section>
        <section><div class="section-head"><h2>Open Orders</h2><span id="ordersPill" class="pill">...</span></div><div id="orders"></div></section>
      </div>
      <div class="grid wide-left">
        <section><div class="section-head"><h2>Latest Bot Activity</h2><span id="logPill" class="pill">No log</span></div><div id="activity" class="events"></div></section>
        <section><div class="section-head"><h2>Session Counters</h2></div><div id="counters"></div></section>
      </div>
    </div>

    <div id="strategy" class="view">
      <section>
        <div class="section-head">
          <h2>Strategy Evidence</h2>
          <div class="toolbar">
            <button id="generateEvidenceBtn">Generate Evidence</button>
            <span id="strategyPill" class="pill">...</span>
          </div>
        </div>
        <div class="body">
          <div class="notice">
            This lab is for evidence, not instructions. A name needs premarket strength, intraday confirmation, liquidity, and risk approval before it becomes an executable trade.
          </div>
          <div style="height:12px"></div>
          <div id="strategySummary"></div>
          <div style="height:12px"></div>
          <div id="charts" class="chart-grid"></div>
        </div>
      </section>
    </div>

    <div id="departments" class="view">
      <section>
        <div class="section-head">
          <h2>Agent Department Workbench</h2>
          <span class="pill warn">Research only - no orders</span>
        </div>
        <div class="body">
          <div class="notice">
            Use this to ask individual departments for side memos, critiques, training notes, or checklists. It can use local Ollama when available and always stores the task so you can learn from the thread.
          </div>
          <div style="height:14px"></div>
          <div class="form-grid">
            <label>Department<select id="departmentSelect"></select></label>
            <label>Ticker or topic<input id="taskTopic" placeholder="e.g. SOXX, flat-start process, opening range breakout"></label>
            <label>Model<input id="taskModel" value="qwen3:4b-instruct"></label>
          </div>
          <div style="height:10px"></div>
          <label>Task<textarea id="taskText" placeholder="Ask a focused task. Example: Risk Office, critique yesterday's remaining exposure and define a safer startup checklist."></textarea></label>
          <div style="height:10px"></div>
          <div class="toolbar">
            <button id="runDepartmentBtn" class="primary">Ask Department</button>
            <button id="templateRiskBtn">Risk Template</button>
            <button id="templateTrainingBtn">Training Template</button>
            <button id="templateStrategyBtn">Strategy Template</button>
          </div>
        </div>
      </section>
      <div class="grid two">
        <section><div class="section-head"><h2>Department Memo</h2><span id="taskPill" class="pill">Idle</span></div><div class="body"><div id="memoOutput" class="memo">No memo yet.</div></div></section>
        <section><div class="section-head"><h2>Department History</h2></div><div id="taskHistory"></div></section>
      </div>
    </div>

    <div id="learning" class="view">
      <section>
        <div class="section-head"><h2>How The System Thinks</h2><span class="pill">Teaching mode</span></div>
        <div class="body">
          <div class="learn-grid">
            <div class="lesson"><div class="step">1. Evidence</div><h3>Research is not a trade</h3><p>A ticker can look strong and still fail risk checks. Evidence creates candidates; it does not grant execution permission.</p></div>
            <div class="lesson"><div class="step">2. Strategy</div><h3>Setup before opinion</h3><p>The strategy desk asks what exact pattern is present, what confirms it, and what invalidates it.</p></div>
            <div class="lesson"><div class="step">3. Risk</div><h3>Survival is the product</h3><p>The risk office protects the account from duplicate entries, stale exposure, late-day trades, and unknown carry risk.</p></div>
            <div class="lesson"><div class="step">4. Execution</div><h3>Orders are operations</h3><p>The trading desk turns approved intent into brackets, sizing, cooldowns, and logs that can be audited.</p></div>
          </div>
          <div style="height:14px"></div>
          <div class="grid two">
            <section>
              <div class="section-head"><h2>Why This App Exists</h2></div>
              <div class="body">
                <p>The Python script is best as the engine because it is testable, schedulable, and easy to recover. The webapp is best as the cockpit because it makes state visible before you press dangerous buttons.</p>
                <p>The split is intentional: the app teaches and controls, while the script executes. That keeps the serious code small and the learning surface rich.</p>
              </div>
            </section>
            <section>
              <div class="section-head"><h2>Useful Vocabulary</h2></div>
              <div class="body" id="glossary"></div>
            </section>
          </div>
        </div>
      </section>
    </div>

    <div id="reports" class="view">
      <section>
        <div class="section-head"><h2>Reports and Artifacts</h2><button id="refreshReportsBtn">Refresh Reports</button></div>
        <div id="reportsList"></div>
      </section>
      <section>
        <div class="section-head"><h2>Selected Report</h2></div>
        <div class="body"><div id="reportText" class="memo">Choose a report from the list.</div></div>
      </section>
    </div>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let latestStatus = null;

    const glossary = [
      ["Flat", "No open positions and no open orders. This is the safest day-trading start state."],
      ["Carry risk", "Starting a new session while yesterday's exposure still exists."],
      ["Bracket order", "A parent order with protective take-profit and stop-loss exit legs."],
      ["Cooldown", "A temporary block that stops the bot re-buying a symbol too soon."],
      ["Preflight", "A checklist that verifies account, environment, models, and safety gates."],
      ["Evidence", "Data that supports a setup. It is not a guarantee or a trade command."],
      ["Direct crypto", "Crypto symbols such as BTC-USD that are included in research evidence but not sent through the stock/ETF execution path."]
    ];

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || data.message || "Request failed");
      }
      return data;
    }

    function money(value) {
      const n = Number(value || 0);
      return "$" + n.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }

    function pct(value) {
      const n = Number(value || 0);
      return n.toFixed(3) + "%";
    }

    function safe(text) {
      return String(text ?? "").replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    function pillClass(ok, warn=false) {
      if (ok) return "pill good";
      if (warn) return "pill warn";
      return "pill bad";
    }

    function setMetric(id, value, sub) {
      $(id + "Value").textContent = value;
      $(id + "Sub").textContent = sub || "";
    }

    function table(headers, rows, emptyText) {
      if (!rows || !rows.length) return `<div class="body muted">${safe(emptyText || "No rows.")}</div>`;
      return `<table><thead><tr>${headers.map(h => `<th class="${h.num ? "num" : ""}">${safe(h.label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${headers.map(h => `<td class="${h.num ? "num" : ""}">${safe(row[h.key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }

    function renderStatus(data) {
      latestStatus = data;
      const positions = data.alpaca.positions || [];
      const orders = data.alpaca.open_orders || [];
      const flat = positions.length === 0 && orders.length === 0;
      const marketOpen = Boolean(data.alpaca.clock && data.alpaca.clock.is_open);
      const botRunning = Boolean(data.bot.running);
      const account = data.alpaca.account || {};
      const equity = Number(account.equity || account.portfolio_value || 0);
      const lastEquity = Number(account.last_equity || 0);
      const change = lastEquity ? equity - lastEquity : 0;
      const latestCycle = data.log.latest_cycle || {};

      setMetric("gate", flat ? "Flat" : "Blocked", flat ? "Safe to start by default" : `${positions.length} positions, ${orders.length} orders`);
      setMetric("bot", botRunning ? "Running" : "Stopped", data.bot.detail || "No app-started process is active");
      setMetric("clock", marketOpen ? "Open" : "Closed", data.alpaca.clock ? `Next open: ${data.alpaca.clock.next_open || "unknown"}` : "Clock unavailable");
      setMetric("equity", equity ? money(equity) : "Unknown", lastEquity ? `Change vs last equity: ${money(change)}` : "No last-equity reference");
      setMetric("cycle", latestCycle.cycle ? String(latestCycle.cycle) : "None", latestCycle.finished_at || latestCycle.logged_at || "No cycle event found");

      $("readyPill").className = pillClass(flat && !botRunning, !flat);
      $("readyPill").textContent = flat ? "Flat account" : "Needs review";
      $("positionsPill").className = pillClass(positions.length === 0, positions.length > 0);
      $("positionsPill").textContent = `${positions.length} open`;
      $("ordersPill").className = pillClass(orders.length === 0, orders.length > 0);
      $("ordersPill").textContent = `${orders.length} open`;
      $("logPill").textContent = data.log.latest_log ? data.log.latest_log.name : "No log";

      $("topNotice").innerHTML = flat
        ? `<div class="notice">Account looks flat from the latest snapshot. The normal Start Bot path is available.</div>`
        : `<div class="notice bad">Account is not flat. The default bot startup gate should block a normal run. Review positions/orders, then use Start + Flatten or explicitly accept carry risk.</div>`;

      $("positions").innerHTML = table([
        {key:"symbol", label:"Symbol"},
        {key:"qty", label:"Qty", num:true},
        {key:"market_value", label:"Market Value", num:true},
        {key:"unrealized_pl", label:"Unrealized P/L", num:true},
        {key:"current_price", label:"Price", num:true}
      ], positions.map(p => ({
        symbol: p.symbol,
        qty: p.qty,
        market_value: money(p.market_value),
        unrealized_pl: money(p.unrealized_pl),
        current_price: p.current_price
      })), "No open positions.");

      $("orders").innerHTML = table([
        {key:"symbol", label:"Symbol"},
        {key:"side", label:"Side"},
        {key:"qty", label:"Qty", num:true},
        {key:"type", label:"Type"},
        {key:"status", label:"Status"},
        {key:"limit_price", label:"Limit", num:true},
        {key:"stop_price", label:"Stop", num:true}
      ], orders.map(o => ({
        symbol: o.symbol,
        side: o.side,
        qty: o.qty,
        type: o.type || o.order_type,
        status: o.status,
        limit_price: o.limit_price || "",
        stop_price: o.stop_price || ""
      })), "No open orders.");

      renderSafety(data);
      renderEvents(data.log.events || []);
      renderCounters(data.log.event_counts || {});
      renderStrategy(data.strategy || {});
      renderReports(data.reports || []);
      renderTaskHistory(data.department_tasks || []);
      renderProjectG(data.projectg || {}, data);
    }

    function renderSafety(data) {
      const checks = [
        ["Flat positions", data.alpaca.positions.length === 0],
        ["No open orders", data.alpaca.open_orders.length === 0],
        ["Account active", (data.alpaca.account || {}).status === "ACTIVE"],
        ["Trading not blocked", !Boolean((data.alpaca.account || {}).trading_blocked)],
        ["Final reports enabled", true],
        ["Startup gate enforced", true]
      ];
      $("safetyChecks").innerHTML = `<table><tbody>${checks.map(([name, ok]) => `<tr><td>${safe(name)}</td><td class="${ok ? "ok" : "bad-text"}">${ok ? "pass" : "review"}</td></tr>`).join("")}</tbody></table>`;
    }

    function renderEvents(events) {
      $("activity").innerHTML = events.slice(-120).reverse().map(e => {
        const detail = e.detail || e.reason || e.ticker || e.symbol || e.action || "";
        return `<div class="event"><div class="time">${safe(e.logged_at || e.timestamp || "")}</div><div class="name">${safe(e.event || "event")}</div><div class="detail">${safe(detail)}</div></div>`;
      }).join("") || `<div class="body muted">No bot events found.</div>`;
    }

    function renderCounters(counts) {
      const rows = Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0, 18).map(([event, count]) => ({event, count}));
      $("counters").innerHTML = table([{key:"event", label:"Event"}, {key:"count", label:"Count", num:true}], rows, "No counters.");
    }

    function renderProjectG(projectg, fullStatus) {
      const account = (fullStatus.alpaca || {}).account || {};
      const equity = Number(account.equity || account.portfolio_value || 0);
      const lastEquity = Number(account.last_equity || 0);
      const daily = lastEquity ? equity - lastEquity : Number(projectg.latest_session_change || 0);
      const decision = projectg.latest_company_run ? (projectg.latest_company_run.ceo_decision_summary || {}) : {};
      const research = projectg.research_process || {};
      const bot = fullStatus.bot || {};

      setMetric("pgEquity", equity ? money(equity) : "Unknown", "Current Alpaca paper equity");
      setMetric("pgDaily", money(daily), lastEquity ? "Versus Alpaca last equity" : "Latest report change");
      $("pgDailyValue").className = "value " + (daily >= 0 ? "ok" : "bad-text");
      setMetric("pgDecision", decision.decision || "No run", decision.outcome || "Run CEO Research to refresh");
      setMetric("pgResearch", research.running ? "Running" : (research.exit_code === 0 ? "Done" : "Idle"), research.detail || "");
      setMetric("pgBot", bot.running ? "Running" : "Stopped", bot.detail || "");

      const positions = (fullStatus.alpaca || {}).positions || [];
      const orders = (fullStatus.alpaca || {}).open_orders || [];
      const flat = positions.length === 0 && orders.length === 0;
      $("projectgNotice").innerHTML = flat
        ? `<div class="notice">ProjectG sees a flat paper account. You can run research, preflight, then start the paper bot from this page.</div>`
        : `<div class="notice bad">ProjectG sees existing exposure: ${positions.length} position(s), ${orders.length} order(s). Use Start + Flatten or review before allowing carry risk.</div>`;

      renderProjectGDecision(decision);
      renderProjectGAllocation(projectg.latest_company_run || {});
      renderProjectGCandidates(projectg.latest_company_run || {});
      renderProjectGSessions(projectg.sessions || []);
      renderProjectGActivity((fullStatus.log || {}).events || []);
    }

    function renderProjectGDecision(decision) {
      const reasons = decision.reasons || [];
      const actions = decision.next_actions || [];
      $("pgDecisionPill").textContent = decision.decision || "No decision";
      $("pgDecisionPill").className = decision.decision === "trade" ? "pill good" : decision.decision === "no_trade" ? "pill warn" : "pill";
      $("pgDecisionSummary").innerHTML = `
        <table><tbody>
          <tr><td><strong>Decision</strong></td><td>${safe(decision.decision || "No CEO research run found")}</td></tr>
          <tr><td><strong>Outcome</strong></td><td>${safe(decision.outcome || "Run CEO Research to create a fresh decision")}</td></tr>
          <tr><td><strong>Reasons</strong></td><td>${safe(reasons.join(", ") || "none")}</td></tr>
          <tr><td><strong>Next actions</strong></td><td>${safe(actions.join("; ") || "none")}</td></tr>
        </tbody></table>`;
    }

    function renderProjectGAllocation(companyRun) {
      const weights = companyRun.target_weights || {};
      const rationale = companyRun.target_weight_rationale || {};
      const entries = Object.entries(weights);
      $("pgAllocationPill").textContent = entries.length ? `${entries.length} target(s)` : "No targets";
      if (!entries.length) {
        $("pgAllocation").innerHTML = `<div class="muted">No target allocation in the latest CEO run.</div>`;
        return;
      }
      const maxWeight = Math.max(...entries.map(([, w]) => Number(w || 0)), 0.01);
      $("pgAllocation").innerHTML = `<div class="allocation-list">${entries.map(([ticker, weight]) => {
        const r = rationale[ticker] || {};
        const width = Math.max(3, Number(weight || 0) / maxWeight * 100);
        return `<div>
          <div class="bar-row">
            <strong>${safe(ticker)}</strong>
            <div class="bar-shell"><div class="bar-fill" style="width:${width.toFixed(1)}%"></div></div>
            <div class="num">${(Number(weight || 0) * 100).toFixed(1)}%</div>
          </div>
          <div class="sub">Quality ${Number(r.quality_score || 0).toFixed(2)} - ${safe((r.drivers || []).slice(0, 5).join(", ") || "no rationale")}</div>
        </div>`;
      }).join("")}</div>`;
    }

    function renderProjectGCandidates(companyRun) {
      const rows = (companyRun.candidates || []).slice(0, 10).map(c => ({
        ticker: c.ticker,
        strategy: c.strategy,
        status: c.strategy_promotion_status || "",
        fit: Number(c.day_trade_fit_score || 0).toFixed(1),
        score: Number(c.score || 0).toFixed(2),
        risk: (c.risk_flags || []).join(", ") || "none"
      }));
      $("pgCandidates").innerHTML = table([
        {key:"ticker", label:"Ticker"},
        {key:"strategy", label:"Strategy"},
        {key:"status", label:"Status"},
        {key:"fit", label:"Fit", num:true},
        {key:"score", label:"Score", num:true},
        {key:"risk", label:"Risk"}
      ], rows, "No CEO candidate list found yet.");
    }

    function renderProjectGSessions(sessions) {
      $("pgCurvePill").textContent = sessions.length ? `${sessions.length} report(s)` : "No reports";
      const points = sessions.map(s => Number(s.final_equity || 0)).filter(v => v > 0);
      $("pgSparkline").innerHTML = sparkline(points);
      $("pgSessionTable").innerHTML = table([
        {key:"session_id", label:"Session"},
        {key:"cycles", label:"Cycles", num:true},
        {key:"final_equity", label:"Final Equity", num:true},
        {key:"change", label:"Change", num:true},
        {key:"flat", label:"Flat"}
      ], sessions.slice(-8).reverse().map(s => ({
        session_id: s.session_id,
        cycles: s.cycles_completed,
        final_equity: money(s.final_equity),
        change: money(s.change),
        flat: s.flat ? "yes" : "no"
      })), "No final session reports found.");
    }

    function sparkline(points) {
      if (!points.length) return `<div class="muted">No equity points yet.</div>`;
      if (points.length === 1) points = [points[0], points[0]];
      const min = Math.min(...points);
      const max = Math.max(...points);
      const span = Math.max(1, max - min);
      const coords = points.map((p, i) => {
        const x = 8 + i * (284 / Math.max(1, points.length - 1));
        const y = 104 - ((p - min) / span) * 88;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      const color = points[points.length - 1] >= points[0] ? "#087443" : "#b42318";
      return `<svg viewBox="0 0 300 120" preserveAspectRatio="none">
        <line x1="8" y1="104" x2="292" y2="104" stroke="#d9e0ea" stroke-width="1"/>
        <polyline points="${coords}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${coords.split(" ").pop().split(",")[0]}" cy="${coords.split(" ").pop().split(",")[1]}" r="4" fill="${color}"/>
      </svg>`;
    }

    function renderProjectGActivity(events) {
      $("pgActivity").innerHTML = events.slice(-60).reverse().map(e => {
        const detail = e.detail || e.reason || e.action || "";
        return `<div class="event"><div class="time">${safe(e.logged_at || e.timestamp || "")}</div><div class="name">${safe(e.event || "event")}</div><div class="detail">${safe(detail)}</div></div>`;
      }).join("") || `<div class="body muted">No live events found yet.</div>`;
    }

    function renderStrategy(strategy) {
      const summary = strategy.summary || {};
      const scores = summary.top_strategy_scores || {};
      const rows = Object.entries(scores).slice(0, 12).map(([ticker, row]) => ({
        ticker,
        best_strategy: row.best_strategy,
        best_score: Number(row.best_score || 0).toFixed(1),
        rs: Number(row.rs_continuation || 0).toFixed(1),
        caution: Number(row.caution_shortlist || 0).toFixed(1)
      }));
      $("strategyPill").textContent = summary.generated_at ? `Generated ${summary.generated_at}` : "No summary";
      $("strategySummary").innerHTML = table([
        {key:"ticker", label:"Ticker"},
        {key:"best_strategy", label:"Best Strategy"},
        {key:"best_score", label:"Score", num:true},
        {key:"rs", label:"RS", num:true},
        {key:"caution", label:"Caution", num:true}
      ], rows, "No strategy scores found. Generate evidence first.");
      $("charts").innerHTML = (strategy.charts || []).map(chart => `<div class="chart"><img alt="${safe(chart.name)}" src="/file?path=${encodeURIComponent(chart.path)}"></div>`).join("") || `<div class="muted">No charts found.</div>`;
    }

    function renderReports(reports) {
      if (!reports.length) {
        $("reportsList").innerHTML = `<div class="body muted">No reports found.</div>`;
        return;
      }
      $("reportsList").innerHTML = `<table><thead><tr><th>Report</th><th>Kind</th><th>Modified</th><th>Open</th></tr></thead><tbody>${reports.map((r, index) => `<tr><td>${safe(r.name)}</td><td>${safe(r.kind)}</td><td>${safe(r.modified)}</td><td><button data-report-index="${index}">View</button></td></tr>`).join("")}</tbody></table>`;
      document.querySelectorAll("[data-report]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const data = await api(`/api/report?path=${encodeURIComponent(btn.dataset.report)}`);
          $("reportText").textContent = data.text || "";
        });
      });
      document.querySelectorAll("[data-report-index]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const report = reports[Number(btn.dataset.reportIndex)];
          const data = await api(`/api/report?path=${encodeURIComponent(report.path)}`);
          $("reportText").textContent = data.text || "";
        });
      });
    }

    function renderTaskHistory(tasks) {
      if (!tasks.length) {
        $("taskHistory").innerHTML = `<div class="body muted">No department tasks yet.</div>`;
        return;
      }
      $("taskHistory").innerHTML = `<table><thead><tr><th>Created</th><th>Department</th><th>Topic</th><th>Open</th></tr></thead><tbody>${tasks.map((t, index) => `<tr><td>${safe(t.created)}</td><td>${safe(t.department_name)}</td><td>${safe(t.topic)}</td><td><button data-task-index="${index}">View</button></td></tr>`).join("")}</tbody></table>`;
      document.querySelectorAll("[data-task-index]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const task = tasks[Number(btn.dataset.taskIndex)];
          const data = await api(`/api/report?path=${encodeURIComponent(task.markdown_path)}`);
          $("memoOutput").textContent = data.text || "";
        });
      });
    }

    async function refresh() {
      try {
        const data = await api("/api/status");
        renderStatus(data);
      } catch (err) {
        $("topNotice").innerHTML = `<div class="notice bad">${safe(err.message)}</div>`;
      }
    }

    async function action(path, body, label) {
      $("actionResult").textContent = `${label}...`;
      try {
        const data = await api(path, {method:"POST", body: JSON.stringify(body || {})});
        $("actionResult").textContent = data.message || "Done.";
        await refresh();
      } catch (err) {
        $("actionResult").textContent = err.message;
      }
    }

    async function projectgAction(path, body, label) {
      $("projectgActionResult").textContent = `${label}...`;
      try {
        const data = await api(path, {method:"POST", body: JSON.stringify(body || {})});
        $("projectgActionResult").textContent = data.message || "Done.";
        await refresh();
      } catch (err) {
        $("projectgActionResult").textContent = err.message;
      }
    }

    function projectgOptions(extra = {}) {
      const numberOrNull = (id) => {
        const raw = $(id).value;
        return raw === "" ? null : Number(raw);
      };
      return {
        strategy: $("pgBotStrategy").value,
        research_profile: $("pgResearchProfile").value,
        universe: $("pgUniverse").value,
        interval_seconds: numberOrNull("pgInterval"),
        max_cycles: numberOrNull("pgMaxCycles"),
        max_deploy_usd: numberOrNull("pgMaxDeploy"),
        max_order_notional_usd: numberOrNull("pgMaxOrder"),
        target_positions: numberOrNull("pgTargets"),
        alpaca_stock_feed: $("pgFeed").value,
        news_enabled: $("pgNews").checked,
        premarket_research_enabled: $("pgPremarket").checked,
        with_staff_memo: $("pgStaffMemo").checked,
        with_tech_scout: $("pgTechScout").checked,
        ...extra
      };
    }

    function setupDepartments(departments) {
      $("departmentSelect").innerHTML = Object.entries(departments).map(([key, d]) => `<option value="${key}">${safe(d.name)} - ${safe(d.teaches)}</option>`).join("");
    }

    function setupLearning() {
      $("glossary").innerHTML = `<table><tbody>${glossary.map(([term, desc]) => `<tr><td><strong>${safe(term)}</strong></td><td>${safe(desc)}</td></tr>`).join("")}</tbody></table>`;
    }

    function setupOrganagram(orgFlow) {
      $("organagram").innerHTML = (orgFlow || []).map(node => `
        <div class="org-node">
          <span class="org-stage">${safe(node.stage)}</span>
          <h3>${safe(node.name)}</h3>
          <div class="org-owner">${safe(node.owner)}</div>
          <div class="org-detail">${safe(node.detail)}</div>
        </div>
      `).join("");
    }

    function setupUniverse(groups) {
      $("universeBreakdown").innerHTML = Object.values(groups || {}).map(group => {
        const mode = String(group.mode || "").toLowerCase();
        const chipClass = mode.includes("research") ? "asset-chip research" : mode.includes("paper") && group.name.toLowerCase().includes("crypto") ? "asset-chip crypto" : "asset-chip";
        return `
          <div class="universe-group">
            <h3>${safe(group.name)}</h3>
            <div class="sub">${safe(group.mode)} - ${safe(group.note)}</div>
            <div class="chip-list">${(group.symbols || []).map(symbol => `<span class="${chipClass}">${safe(symbol)}</span>`).join("")}</div>
          </div>
        `;
      }).join("");
    }

    function setupProjectG(meta) {
      $("pgUniverse").value = meta.default_projectg_universe || "";
    }

    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
        document.querySelectorAll(".view").forEach(x => x.classList.remove("active"));
        btn.classList.add("active");
        $(btn.dataset.view).classList.add("active");
      });
    });

    $("refreshBtn").addEventListener("click", refresh);
    $("refreshReportsBtn").addEventListener("click", refresh);
    $("preflightBtn").addEventListener("click", () => action("/api/preflight", {}, "Running preflight"));
    $("startBtn").addEventListener("click", () => {
      if (confirm("Start paper bot with the default flat-start gate?")) action("/api/bot/start", {}, "Starting bot");
    });
    $("flattenStartBtn").addEventListener("click", () => {
      if (confirm("Ask the bot to flatten existing paper exposure before starting?")) action("/api/bot/start", {flatten_existing_at_start:true}, "Starting with startup flatten");
    });
    $("allowCarryBtn").addEventListener("click", () => {
      if (confirm("This intentionally allows carry risk. Continue?")) action("/api/bot/start", {allow_carry_risk:true}, "Starting with carry-risk override");
    });
    $("startOnceBtn").addEventListener("click", () => action("/api/bot/start", {once:true}, "Starting one cycle"));
    $("stopFlattenBtn").addEventListener("click", () => action("/api/bot/stop", {action:"flatten", reason:"control room stop and flatten"}, "Writing flatten stop request"));
    $("stopOnlyBtn").addEventListener("click", () => action("/api/bot/stop", {action:"stop", reason:"control room stop only"}, "Writing stop request"));
    $("generateEvidenceBtn").addEventListener("click", () => action("/api/strategy/generate", {}, "Generating strategy evidence"));
    $("pgPreflightBtn").addEventListener("click", () => projectgAction("/api/preflight", {}, "Running preflight"));
    $("pgResearchBtn").addEventListener("click", () => projectgAction("/api/projectg/research", projectgOptions(), "Starting CEO research"));
    $("pgEvidenceBtn").addEventListener("click", () => projectgAction("/api/strategy/generate", {}, "Generating evidence"));
    $("pgStartBtn").addEventListener("click", () => {
      if (confirm("Start the ProjectG paper bot with the flat-start safety gate?")) projectgAction("/api/bot/start", projectgOptions(), "Starting paper bot");
    });
    $("pgOnceBtn").addEventListener("click", () => projectgAction("/api/bot/start", projectgOptions({once:true}), "Starting one-cycle run"));
    $("pgFlattenStartBtn").addEventListener("click", () => {
      if (confirm("Ask ProjectG to flatten existing paper exposure before starting?")) projectgAction("/api/bot/start", projectgOptions({flatten_existing_at_start:true}), "Starting with flatten");
    });
    $("pgStopFlattenBtn").addEventListener("click", () => projectgAction("/api/bot/stop", {action:"flatten", reason:"ProjectG cockpit stop and flatten"}, "Writing stop + flatten request"));

    $("templateRiskBtn").addEventListener("click", () => {
      $("departmentSelect").value = "risk_office";
      $("taskText").value = "Review the latest account state and yesterday's behavior. Give me the top operational risks, the likely cause, and a safer checklist for the next run.";
    });
    $("templateTrainingBtn").addEventListener("click", () => {
      $("departmentSelect").value = "training_development";
      $("taskText").value = "Turn the latest session into role-specific lessons. Tell me what examples we should save for scout, strategy, risk, portfolio, and execution evaluation datasets.";
    });
    $("templateStrategyBtn").addEventListener("click", () => {
      $("departmentSelect").value = "strategy_researcher";
      $("taskText").value = "Use the current strategy evidence to explain which setups are strongest, what confirmation is needed after the open, and which tickers should be avoided unless conditions improve.";
    });
    $("runDepartmentBtn").addEventListener("click", async () => {
      $("taskPill").textContent = "Working";
      $("memoOutput").textContent = "Asking department...";
      try {
        const data = await api("/api/department-task", {
          method: "POST",
          body: JSON.stringify({
            department: $("departmentSelect").value,
            topic: $("taskTopic").value,
            task: $("taskText").value,
            model: $("taskModel").value
          })
        });
        $("taskPill").textContent = data.used_ollama ? "Ollama memo" : "Saved fallback";
        $("memoOutput").textContent = data.memo;
        await refresh();
      } catch (err) {
        $("taskPill").textContent = "Error";
        $("memoOutput").textContent = err.message;
      }
    });

    (async function init() {
      const meta = await api("/api/meta");
      setupDepartments(meta.departments);
      setupLearning();
      setupOrganagram(meta.org_flow);
      setupUniverse(meta.universe_groups);
      setupProjectG(meta);
      await refresh();
      setInterval(refresh, 10000);
    })();
  </script>
</body>
</html>
"""


class ControlRoomHandler(BaseHTTPRequestHandler):
    server_version = "TradingControlRoom/0.1"

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.send_html(HTML)
            elif parsed.path == "/api/meta":
                self.send_json(
                    {
                        "ok": True,
                        "departments": DEPARTMENTS,
                        "org_flow": ORG_FLOW,
                        "universe_groups": UNIVERSE_GROUPS,
                        "default_projectg_universe": DEFAULT_PROJECTG_UNIVERSE,
                    }
                )
            elif parsed.path == "/api/status":
                self.send_json(build_status())
            elif parsed.path == "/api/report":
                self.send_json(read_report_endpoint(parsed))
            elif parsed.path == "/file":
                self.send_file_endpoint(parsed)
            else:
                self.send_json({"ok": False, "error": "not found"}, status=404)
        except Exception as exc:
            self.send_exception(exc)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            body = self.read_json_body()
            if parsed.path == "/api/preflight":
                self.send_json(run_preflight_endpoint())
            elif parsed.path == "/api/bot/start":
                self.send_json(start_bot_endpoint(body))
            elif parsed.path == "/api/bot/stop":
                self.send_json(stop_bot_endpoint(body))
            elif parsed.path == "/api/strategy/generate":
                self.send_json(generate_strategy_endpoint())
            elif parsed.path == "/api/projectg/research":
                self.send_json(start_projectg_research_endpoint(body))
            elif parsed.path == "/api/department-task":
                self.send_json(department_task_endpoint(body))
            else:
                self.send_json({"ok": False, "error": "not found"}, status=404)
        except Exception as exc:
            self.send_exception(exc)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def send_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        data = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file_endpoint(self, parsed: Any) -> None:
        query = parse_qs(parsed.query)
        raw_path = query.get("path", [""])[0]
        path = resolve_repo_path(raw_path)
        if not path.exists() or not path.is_file():
            self.send_json({"ok": False, "error": "file not found"}, status=404)
            return
        content_type = "image/svg+xml" if path.suffix.lower() == ".svg" else "text/plain"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_exception(self, exc: Exception) -> None:
        self.send_json(
            {
                "ok": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            },
            status=500,
        )

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{datetime.now(UTC).isoformat()}] {self.address_string()} {format % args}")


def build_status() -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env", override=True)
    snapshot = broker_snapshot()
    log_summary = latest_log_summary()
    return {
        "ok": True,
        "checked_at": datetime.now(UTC).isoformat(),
        "bot": bot_status(),
        "alpaca": snapshot,
        "log": log_summary,
        "strategy": strategy_evidence_summary(),
        "projectg": projectg_summary(snapshot=snapshot),
        "reports": list_reports(),
        "department_tasks": list_department_tasks(),
    }


def broker_snapshot() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account": {},
        "positions": [],
        "open_orders": [],
        "clock": {},
        "errors": [],
    }
    try:
        broker = AlpacaPaperBroker()
    except Exception as exc:
        payload["errors"].append(error_payload("broker_init", exc))
        return payload

    for key, call in [
        ("account", broker.get_account),
        ("positions", lambda: broker.get_positions().get("positions", [])),
        ("open_orders", lambda: broker.get_orders("open").get("orders", [])),
        ("clock", broker.get_clock),
    ]:
        try:
            payload[key] = call()
        except Exception as exc:
            payload["errors"].append(error_payload(key, exc))
    return payload


def latest_log_summary() -> dict[str, Any]:
    latest = latest_file(LIVE_LOG_DIR, "day_trader_bot_*.jsonl")
    if latest is None:
        return {
            "latest_log": None,
            "events": [],
            "event_counts": {},
            "latest_cycle": {},
        }
    events = read_jsonl_tail(latest)
    counts = Counter(str(event.get("event", "unknown")) for event in events)
    latest_cycle = next(
        (event for event in reversed(events) if event.get("event") == "autonomous_ceo_cycle"),
        {},
    )
    compact_events = [compact_event(event) for event in events[-MAX_EVENTS:]]
    return {
        "latest_log": file_info(latest),
        "events": compact_events,
        "event_counts": dict(counts.most_common()),
        "latest_cycle": compact_event(latest_cycle) if latest_cycle else {},
    }


def read_jsonl_tail(path: Path) -> list[dict[str, Any]]:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > TAIL_BYTES:
            handle.seek(size - TAIL_BYTES)
            handle.readline()
        raw = handle.read().decode("utf-8", errors="replace")
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    if not event:
        return {}
    details = []
    for key in ("reason", "ticker", "symbol", "action", "strategy_profile"):
        if event.get(key):
            details.append(f"{key}: {event.get(key)}")
    if event.get("positions_count") is not None:
        details.append(f"positions: {event.get('positions_count')}")
    if event.get("open_orders_count") is not None:
        details.append(f"orders: {event.get('open_orders_count')}")
    if event.get("cycle") is not None:
        details.append(f"cycle: {event.get('cycle')}")
    return {
        "logged_at": event.get("logged_at") or event.get("finished_at") or event.get("started_at"),
        "event": event.get("event"),
        "cycle": event.get("cycle"),
        "detail": "; ".join(details),
        "reason": event.get("reason"),
        "ticker": event.get("ticker"),
        "symbol": event.get("symbol"),
        "action": event.get("action"),
        "finished_at": event.get("finished_at"),
    }


def bot_status() -> dict[str, Any]:
    return process_status(
        proc=APP_STATE.bot_process,
        started_at=APP_STATE.bot_started_at,
        command=APP_STATE.bot_command,
        idle_detail="No app-started bot process",
        running_detail="App-started bot process",
    )


def research_status() -> dict[str, Any]:
    return process_status(
        proc=APP_STATE.research_process,
        started_at=APP_STATE.research_started_at,
        command=APP_STATE.research_command,
        idle_detail="No app-started CEO research process",
        running_detail="App-started CEO research process",
    )


def process_status(
    *,
    proc: subprocess.Popen[Any] | None,
    started_at: str,
    command: list[str] | None,
    idle_detail: str,
    running_detail: str,
) -> dict[str, Any]:
    if proc is not None:
        code = proc.poll()
        if code is None:
            return {
                "running": True,
                "pid": proc.pid,
                "started_at": started_at,
                "command": command,
                "detail": f"{running_detail} {proc.pid}",
            }
        return {
            "running": False,
            "pid": proc.pid,
            "exit_code": code,
            "started_at": started_at,
            "command": command,
            "detail": f"Last app-started process exited with {code}",
        }
    return {"running": False, "detail": idle_detail}


def strategy_evidence_summary() -> dict[str, Any]:
    summary_path = STRATEGY_EVIDENCE_DIR / "strategy_evidence_summary.json"
    summary = read_json_file(summary_path) if summary_path.exists() else {}
    charts = []
    for path in sorted(STRATEGY_EVIDENCE_DIR.glob("*.svg")):
        charts.append({"name": path.name, "path": str(path)})
    return {
        "summary": summary,
        "summary_path": str(summary_path) if summary_path.exists() else "",
        "charts": charts,
    }


def projectg_summary(*, snapshot: dict[str, Any]) -> dict[str, Any]:
    sessions = session_report_summaries()
    latest_change = sessions[-1]["change"] if sessions else 0.0
    latest_company_run = latest_company_run_summary()
    account = snapshot.get("account", {})
    return {
        "account_status": account.get("status", ""),
        "current_equity": account.get("equity") or account.get("portfolio_value"),
        "latest_session_change": latest_change,
        "research_process": research_status(),
        "latest_company_run": latest_company_run,
        "sessions": sessions,
    }


def latest_company_run_summary() -> dict[str, Any]:
    root = REPO_ROOT / "results" / "codex_ceo_company"
    latest = latest_file_recursive(root, "company_run.json")
    if latest is None:
        return {}
    payload = read_json_file(latest)
    candidates = payload.get("candidates", [])
    order_plans = payload.get("order_plans", [])
    return {
        "path": str(latest),
        "artifact_dir": str(latest.parent),
        "modified": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds"),
        "trade_date": payload.get("trade_date", ""),
        "ceo_decision_summary": payload.get("ceo_decision_summary", {}),
        "target_weights": payload.get("target_weights", {}),
        "target_weight_rationale": payload.get("target_weight_rationale", {}),
        "order_plans": order_plans[:20] if isinstance(order_plans, list) else [],
        "order_plan_diagnostics": payload.get("order_plan_diagnostics", [])[:20],
        "agent_scorecards": payload.get("agent_scorecards", []),
        "candidates": candidates[:15] if isinstance(candidates, list) else [],
    }


def session_report_summaries() -> list[dict[str, Any]]:
    root = RESULTS_DIR / "session_reports"
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("daytrader_*_final.json"), key=lambda p: p.stat().st_mtime):
        payload = read_json_file(path)
        session = payload.get("session", {}) if isinstance(payload, dict) else {}
        initial = safe_float(session.get("initial_equity"))
        final = safe_float(session.get("final_equity"))
        rows.append(
            {
                "path": str(path),
                "session_id": session.get("session_id", path.stem),
                "started_at": session.get("started_at", ""),
                "finished_at": session.get("finished_at", ""),
                "cycles_completed": session.get("cycles_completed", 0),
                "initial_equity": initial,
                "final_equity": final,
                "change": final - initial if initial > 0 else 0.0,
                "flat": bool(payload.get("flat")),
            }
        )
    return rows[-40:]


def list_reports() -> list[dict[str, Any]]:
    candidates: list[tuple[str, Path]] = []
    for root, kind in [
        (RESULTS_DIR / "session_reports", "session"),
        (RESULTS_DIR / "day_summaries", "day summary"),
        (REPO_ROOT / "results" / "codex_ceo_company", "CEO research"),
        (REPO_ROOT / "results" / "reports", "CEO/report"),
    ]:
        if root.exists():
            for path in root.rglob("*.md"):
                candidates.append((kind, path))
    candidates.sort(key=lambda item: item[1].stat().st_mtime, reverse=True)
    return [
        {
            "kind": kind,
            "name": path.name,
            "path": str(path),
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        }
        for kind, path in candidates[:60]
    ]


def list_department_tasks() -> list[dict[str, Any]]:
    if not TASK_DIR.exists():
        return []
    rows = []
    for path in sorted(TASK_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = read_json_file(path)
        department_key = str(data.get("department", ""))
        rows.append(
            {
                "created": data.get("created_at", ""),
                "department": department_key,
                "department_name": DEPARTMENTS.get(department_key, {}).get("name", department_key),
                "topic": data.get("topic", ""),
                "json_path": str(path),
                "markdown_path": str(path.with_suffix(".md")),
            }
        )
    return rows[:40]


def run_preflight_endpoint() -> dict[str, Any]:
    preflight_module = load_script_module(
        "control_room_preflight_market_open",
        REPO_ROOT / "scripts" / "preflight_market_open.py",
    )
    run_preflight = getattr(preflight_module, "run_preflight")

    report = run_preflight(results_dir=RESULTS_DIR)
    out = RESULTS_DIR / "preflight_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return {
        "ok": True,
        "message": "Preflight complete",
        "report": report,
        "path": str(out),
    }


def start_bot_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    proc = APP_STATE.bot_process
    if proc is not None and proc.poll() is None:
        return {
            "ok": False,
            "error": f"Bot already running as PID {proc.pid}",
        }

    PROCESS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = PROCESS_LOG_DIR / f"bot_{stamp}.out.log"
    err_path = PROCESS_LOG_DIR / f"bot_{stamp}.err.log"
    command = build_bot_command(body)

    proc = start_background_process(command, out_path=out_path, err_path=err_path)
    APP_STATE.bot_process = proc
    APP_STATE.bot_started_at = datetime.now(UTC).isoformat()
    APP_STATE.bot_command = command
    return {
        "ok": True,
        "message": f"Bot started as PID {proc.pid}",
        "pid": proc.pid,
        "command": command,
        "stdout": str(out_path),
        "stderr": str(err_path),
    }


def start_projectg_research_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    proc = APP_STATE.research_process
    if proc is not None and proc.poll() is None:
        return {
            "ok": False,
            "error": f"CEO research already running as PID {proc.pid}",
        }

    PROCESS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = PROCESS_LOG_DIR / f"ceo_research_{stamp}.out.log"
    err_path = PROCESS_LOG_DIR / f"ceo_research_{stamp}.err.log"
    command = build_projectg_research_command(body)
    proc = start_background_process(command, out_path=out_path, err_path=err_path)
    APP_STATE.research_process = proc
    APP_STATE.research_started_at = datetime.now(UTC).isoformat()
    APP_STATE.research_command = command
    return {
        "ok": True,
        "message": f"CEO research started as PID {proc.pid}",
        "pid": proc.pid,
        "command": command,
        "stdout": str(out_path),
        "stderr": str(err_path),
    }


def start_background_process(
    command: list[str],
    *,
    out_path: Path,
    err_path: Path,
) -> subprocess.Popen[Any]:
    out_handle = out_path.open("a", encoding="utf-8")
    err_handle = err_path.open("a", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        stdout=out_handle,
        stderr=err_handle,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def build_bot_command(body: dict[str, Any]) -> list[str]:
    command = [sys.executable, str(REPO_ROOT / "run_day_trader_bot.py")]
    strategy = str(body.get("strategy") or "both").strip().lower()
    if strategy not in {"safe", "risky", "both"}:
        strategy = "both"
    command.extend(["--strategy", strategy])

    universe = str(body.get("universe") or "").strip()
    if universe:
        command.extend(["--universe", universe])

    append_int_arg(command, "--interval-seconds", body.get("interval_seconds"))
    append_int_arg(command, "--max-cycles", body.get("max_cycles"))
    append_float_arg(command, "--max-deploy-usd", body.get("max_deploy_usd"))
    append_float_arg(command, "--max-order-notional-usd", body.get("max_order_notional_usd"))
    append_int_arg(command, "--target-positions", body.get("target_positions"))

    feed = str(body.get("alpaca_stock_feed") or "").strip().lower()
    if feed:
        command.extend(["--alpaca-stock-feed", feed])
    if body.get("once"):
        command.append("--once")
    if body.get("flatten_existing_at_start"):
        command.append("--flatten-existing-at-start")
    if body.get("allow_carry_risk"):
        command.append("--allow-carry-risk")
    if body.get("with_staff_memo"):
        command.append("--with-staff-memo")
    if body.get("with_tech_scout"):
        command.append("--with-tech-scout")
    if body.get("news_enabled") is False:
        command.append("--disable-news-politics")
    if body.get("premarket_research_enabled") is False:
        command.append("--disable-premarket-research")
    if body.get("entry_cooldown_minutes"):
        command.extend(["--entry-cooldown-minutes", str(int(body["entry_cooldown_minutes"]))])
    return command


def build_projectg_research_command(body: dict[str, Any]) -> list[str]:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "run_codex_ceo_company.py")]
    profile = str(body.get("research_profile") or "safe").strip().lower()
    if profile not in {"balanced", "safe", "risky"}:
        profile = "safe"
    command.extend(["--strategy-profile", profile])

    universe = str(body.get("universe") or "").strip()
    if universe:
        command.extend(["--universe", universe])
    append_float_arg(command, "--max-deploy-usd", body.get("max_deploy_usd"))
    append_float_arg(command, "--max-order-notional-usd", body.get("max_order_notional_usd"))
    append_int_arg(command, "--target-positions", body.get("target_positions"))
    if not body.get("with_staff_memo"):
        command.append("--no-ollama-staff")
    if not body.get("with_tech_scout"):
        command.append("--no-tech-scout")
    return command


def append_int_arg(command: list[str], flag: str, value: Any) -> None:
    if value in (None, ""):
        return
    parsed = int(value)
    if parsed > 0:
        command.extend([flag, str(parsed)])


def append_float_arg(command: list[str], flag: str, value: Any) -> None:
    if value in (None, ""):
        return
    parsed = float(value)
    if parsed > 0:
        command.extend([flag, str(parsed)])


def stop_bot_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    action = str(body.get("action") or "flatten").lower()
    if action not in {"flatten", "stop"}:
        action = "flatten"
    reason = str(body.get("reason") or "control room stop requested")
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTROL_DIR / "stop_requested.json"
    payload = {
        "action": action,
        "reason": reason,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return {
        "ok": True,
        "message": f"Stop request written: {action}",
        "path": str(path),
        "payload": payload,
    }


def generate_strategy_endpoint() -> dict[str, Any]:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "generate_strategy_evidence.py")]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "ok": result.returncode == 0,
        "message": "Strategy evidence generated" if result.returncode == 0 else "Strategy evidence failed",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def department_task_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    department_key = str(body.get("department") or "research_director")
    department = DEPARTMENTS.get(department_key)
    if department is None:
        raise ValueError(f"Unknown department: {department_key}")
    task = str(body.get("task") or "").strip()
    if not task:
        raise ValueError("Task is required")
    topic = str(body.get("topic") or "").strip()
    model = str(body.get("model") or "qwen3:4b-instruct").strip()
    context = build_department_context()
    prompt = build_department_prompt(
        department_key=department_key,
        department=department,
        topic=topic,
        task=task,
        context=context,
    )
    used_ollama = False
    try:
        memo = call_ollama(model=model, prompt=prompt)
        used_ollama = True
    except Exception as exc:
        memo = fallback_department_memo(
            department=department,
            topic=topic,
            task=task,
            error=exc,
            context=context,
        )

    saved = save_department_task(
        department_key=department_key,
        department=department,
        topic=topic,
        task=task,
        model=model,
        prompt=prompt,
        memo=memo,
        used_ollama=used_ollama,
    )
    return {
        "ok": True,
        "used_ollama": used_ollama,
        "department": department_key,
        "department_name": department["name"],
        "topic": topic,
        "memo": memo,
        **saved,
    }


def build_department_context() -> dict[str, Any]:
    status = {
        "alpaca": broker_snapshot(),
        "log": latest_log_summary(),
        "strategy": strategy_evidence_summary(),
    }
    return status


def build_department_prompt(
    *,
    department_key: str,
    department: dict[str, str],
    topic: str,
    task: str,
    context: dict[str, Any],
) -> str:
    account = context.get("alpaca", {}).get("account", {})
    positions = context.get("alpaca", {}).get("positions", [])
    open_orders = context.get("alpaca", {}).get("open_orders", [])
    strategy_scores = (
        context.get("strategy", {})
        .get("summary", {})
        .get("top_strategy_scores", {})
    )
    top_scores = list(strategy_scores.items())[:8]
    return "\n".join(
        [
            f"You are the {department['name']} for a paper-trading AI company.",
            "Scope: research, critique, education, and memo writing only. Do not place orders.",
            f"Department charter: {department['charter']}",
            f"Topic: {topic or 'general operations'}",
            "",
            "User task:",
            task,
            "",
            "Current context:",
            f"- Account status: {account.get('status', 'unknown')}",
            f"- Equity: {account.get('equity') or account.get('portfolio_value') or 'unknown'}",
            f"- Open positions: {len(positions)}",
            f"- Open orders: {len(open_orders)}",
            f"- Latest log: {context.get('log', {}).get('latest_log', {}).get('name', 'none')}",
            f"- Top strategy scores: {json.dumps(top_scores, default=str)[:2500]}",
            "",
            "Return a concise markdown memo with: verdict, evidence, risks, recommended next actions, and one teaching note.",
        ]
    )


def call_ollama(*, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    text = str(data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned an empty response")
    return text


def fallback_department_memo(
    *,
    department: dict[str, str],
    topic: str,
    task: str,
    error: Exception,
    context: dict[str, Any],
) -> str:
    positions = context.get("alpaca", {}).get("positions", [])
    open_orders = context.get("alpaca", {}).get("open_orders", [])
    flat = not positions and not open_orders
    return "\n".join(
        [
            f"# {department['name']} Memo",
            "",
            "Local Ollama was unavailable, so this is a structured fallback memo.",
            "",
            f"## Topic\n{topic or 'General operations'}",
            "",
            "## Verdict",
            "Proceed only inside the paper-trading safety process. The side-task workbench is useful for learning and critique, but execution should remain in the main bot path.",
            "",
            "## Evidence",
            f"- Account flat from latest snapshot: {'yes' if flat else 'no'}",
            f"- Open positions: {len(positions)}",
            f"- Open orders: {len(open_orders)}",
            f"- Department charter: {department['charter']}",
            "",
            "## Recommended Next Actions",
            "- Keep department memos research-only.",
            "- Convert useful memos into checklist rules or test cases before changing execution.",
            "- Use Risk Office and Operations tasks before increasing account exposure.",
            "",
            "## Teaching Note",
            department["teaches"],
            "",
            "## Ollama Error",
            f"{type(error).__name__}: {error}",
            "",
            "## Original Task",
            task,
        ]
    )


def save_department_task(
    *,
    department_key: str,
    department: dict[str, str],
    topic: str,
    task: str,
    model: str,
    prompt: str,
    memo: str,
    used_ollama: bool,
) -> dict[str, str]:
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = safe_slug(f"{stamp}_{department_key}_{topic or 'task'}")
    json_path = TASK_DIR / f"{slug}.json"
    md_path = TASK_DIR / f"{slug}.md"
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "department": department_key,
        "department_name": department["name"],
        "topic": topic,
        "task": task,
        "model": model,
        "used_ollama": used_ollama,
        "prompt": prompt,
        "memo": memo,
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Department Task - {department['name']}",
                "",
                f"- Created: {payload['created_at']}",
                f"- Topic: {topic or 'general'}",
                f"- Model: {model}",
                f"- Ollama used: {used_ollama}",
                "",
                "## Task",
                "",
                task,
                "",
                "## Memo",
                "",
                memo,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"json_path": str(json_path), "markdown_path": str(md_path)}


def read_report_endpoint(parsed: Any) -> dict[str, Any]:
    query = parse_qs(parsed.query)
    raw_path = query.get("path", [""])[0]
    path = resolve_repo_path(raw_path)
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "file not found"}
    return {
        "ok": True,
        "path": str(path),
        "text": path.read_text(encoding="utf-8", errors="replace"),
    }


def latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def latest_file_recursive(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.rglob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_script_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def error_payload(stage: str, exc: Exception) -> dict[str, str]:
    return {
        "stage": stage,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def resolve_repo_path(raw_path: str) -> Path:
    if not raw_path:
        raise ValueError("path is required")
    path = Path(raw_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    root = REPO_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("path must stay inside the repository")
    return resolved


def safe_slug(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {" ", "-", "_", "."}:
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:120] or "task"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Trading Control Room webapp.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(REPO_ROOT / ".env", override=True)
    CONTROL_ROOM_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), ControlRoomHandler)
    print(f"Trading Control Room running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Trading Control Room")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
