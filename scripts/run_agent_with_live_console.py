"""Run TradingAgents with live terminal progress output.

Usage examples:
  python -u scripts/run_agent_with_live_console.py --symbol NVDA --trade-date 2026-05-01
  python -u scripts/run_agent_with_live_console.py --symbol NVDA --trade-date 2026-05-01 --submit-order
"""

from __future__ import annotations

import argparse
from datetime import datetime

from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import AlpacaPaperBroker, decision_to_order_intent
from tradingagents.graph.trading_graph import TradingAgentsGraph


def ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. NVDA")
    parser.add_argument(
        "--trade-date",
        required=True,
        help="Analysis date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--submit-order",
        action="store_true",
        help="If set, submit mapped buy/sell intent to Alpaca paper account.",
    )
    parser.add_argument(
        "--order-qty",
        type=float,
        default=1.0,
        help="Share quantity for mapped buy/sell order (default: 1.0).",
    )
    parser.add_argument(
        "--model",
        default="qwen3:0.6b",
        help="Ollama model name for both quick/deep roles.",
    )
    args = parser.parse_args()

    load_dotenv(".env", override=True)

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "ollama"
    config["backend_url"] = "http://localhost:11434/v1"
    config["quick_think_llm"] = args.model
    config["deep_think_llm"] = args.model
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["save_run_artifacts"] = True

    print(f"[{ts()}] Starting run for {args.symbol} on {args.trade_date}")
    print(
        f"[{ts()}] Provider=ollama model={args.model} submit_order={args.submit_order}"
    )
    print(f"[{ts()}] Live progress will stream below from graph nodes...")

    # debug=True streams intermediate messages to console.
    graph = TradingAgentsGraph(debug=True, config=config)
    final_state, signal = graph.propagate(args.symbol.upper(), args.trade_date)

    decision_text = final_state.get("final_trade_decision", "")
    print(f"[{ts()}] Run completed. Signal={signal}")
    print(f"[{ts()}] Decision preview: {decision_text[:260].replace(chr(10), ' ')}")

    intent = decision_to_order_intent(
        args.symbol.upper(),
        decision_text,
        base_quantity=args.order_qty,
    )
    if intent is None:
        print(f"[{ts()}] No order mapped (Hold).")
        return

    print(
        f"[{ts()}] Mapped order intent: side={intent.side} symbol={intent.ticker} qty={intent.quantity}"
    )
    if not args.submit_order:
        print(f"[{ts()}] Dry run only. No order submitted.")
        return

    broker = AlpacaPaperBroker()
    order = broker.submit_order(intent)
    print(
        f"[{ts()}] Order submitted: id={order.get('id')} status={order.get('status')} "
        f"symbol={order.get('symbol')} side={order.get('side')} qty={order.get('qty')}"
    )


if __name__ == "__main__":
    main()
