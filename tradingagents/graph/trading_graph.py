# TradingAgents/graph/trading_graph.py

import logging
import os
from pathlib import Path
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

from langgraph.prebuilt import ToolNode

from tradingagents.llm_clients import create_llm_client
from tradingagents.execution import (
    AlpacaPaperBroker,
    decision_to_order_intent,
    evaluate_order_policy,
)

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news
)
from tradingagents.agents.utils.copy_trading_tools import (
    get_congressional_trades,
    get_institutional_holders,
    get_sec_disclosure_filings,
)

from .checkpointer import checkpoint_step, clear_checkpoint, get_checkpointer, thread_id
from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()
        
        self.memory_log = TradingMemoryLog(self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
            self.config,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict
        self.last_run_artifact_dir: Optional[Path] = None

        # Set up the graph: keep the workflow for recompilation with a checkpointer.
        self.workflow = self.graph_setup.setup_graph(selected_analysts)
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
            "current_news": ToolNode(
                [
                    get_news,
                    get_global_news,
                ]
            ),
            "strategy": ToolNode(
                [
                    get_stock_data,
                    get_indicators,
                    get_news,
                ]
            ),
            "copy_trading": ToolNode(
                [
                    get_congressional_trades,
                    get_institutional_holders,
                    get_sec_disclosure_filings,
                    get_insider_transactions,
                ]
            ),
        }

    def _fetch_returns(
        self, ticker: str, trade_date: str, holding_days: int = 5
    ) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        """Fetch raw and alpha return for ticker over holding_days from trade_date.

        Returns (raw_return, alpha_return, actual_holding_days) or
        (None, None, None) if price data is unavailable (too recent, delisted,
        or network error).
        """
        try:
            start = datetime.strptime(trade_date, "%Y-%m-%d")
            end = start + timedelta(days=holding_days + 7)  # buffer for weekends/holidays
            end_str = end.strftime("%Y-%m-%d")

            stock = yf.Ticker(ticker).history(start=trade_date, end=end_str)
            spy = yf.Ticker("SPY").history(start=trade_date, end=end_str)

            if len(stock) < 2 or len(spy) < 2:
                return None, None, None

            actual_days = min(holding_days, len(stock) - 1, len(spy) - 1)
            raw = float(
                (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                / stock["Close"].iloc[0]
            )
            spy_ret = float(
                (spy["Close"].iloc[actual_days] - spy["Close"].iloc[0])
                / spy["Close"].iloc[0]
            )
            alpha = raw - spy_ret
            return raw, alpha, actual_days
        except Exception as e:
            logger.warning(
                "Could not resolve outcome for %s on %s (will retry next run): %s",
                ticker, trade_date, e,
            )
            return None, None, None

    def _resolve_pending_entries(self, ticker: str) -> None:
        """Resolve pending log entries for ticker at the start of a new run.

        Fetches returns for each same-ticker pending entry, generates reflections,
        then writes all updates in a single atomic batch write to avoid redundant I/O.
        Skips entries whose price data is not yet available (too recent or delisted).

        Trade-off: only same-ticker entries are resolved per run.  Entries for
        other tickers accumulate until that ticker is run again.
        """
        pending = [e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker]
        if not pending:
            return

        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(ticker, entry["date"])
            if raw is None:
                continue  # price not available yet — try again next run
            reflection = self.reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw,
                alpha_return=alpha,
            )
            updates.append({
                "ticker": ticker,
                "trade_date": entry["date"],
                "raw_return": raw,
                "alpha_return": alpha,
                "holding_days": days,
                "reflection": reflection,
            })

        if updates:
            self.memory_log.batch_update_with_outcomes(updates)

    def propagate(self, company_name, trade_date):
        """Run the trading agents graph for a company on a specific date.

        When ``checkpoint_enabled`` is set in config, the graph is recompiled
        with a per-ticker SqliteSaver so a crashed run can resume from the last
        successful node on a subsequent invocation with the same ticker+date.
        """
        self.ticker = company_name

        # Resolve any pending memory-log entries for this ticker before the pipeline runs.
        self._resolve_pending_entries(company_name)

        # Recompile with a checkpointer if the user opted in.
        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(
                self.config["data_cache_dir"], company_name
            )
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)

            step = checkpoint_step(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
            if step is not None:
                logger.info(
                    "Resuming from step %d for %s on %s", step, company_name, trade_date
                )
            else:
                logger.info("Starting fresh for %s on %s", company_name, trade_date)

        try:
            return self._run_graph(company_name, trade_date)
        finally:
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.graph = self.workflow.compile()

    def _run_graph(self, company_name, trade_date):
        """Execute the graph and write the resulting state to disk and memory log."""
        # Initialize state — inject memory log context for PM.
        past_context = self.memory_log.get_past_context(company_name)
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, past_context=past_context
        )
        args = self.propagator.get_graph_args()

        # Inject thread_id so same ticker+date resumes, different date starts fresh.
        if self.config.get("checkpoint_enabled"):
            tid = thread_id(company_name, str(trade_date))
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = tid

        if self.debug:
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)
            final_state = trace[-1]
        else:
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection.
        self.curr_state = final_state

        # Log state to disk.
        logged_state = self._log_state(trade_date, final_state)
        signal = self.process_signal(final_state["final_trade_decision"])
        if self.config.get("save_run_artifacts", True):
            self._save_run_artifacts(
                trade_date=trade_date,
                final_state=final_state,
                logged_state=logged_state,
                signal=signal,
            )

        if self.config.get("auto_submit_paper_orders", False):
            self._maybe_submit_paper_order(
                ticker=company_name,
                final_trade_decision=final_state["final_trade_decision"],
            )

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )

        # Clear checkpoint on successful completion to avoid stale state.
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )

        return final_state, signal

    def _build_logged_state(self, final_state):
        """Build a JSON-serializable state view used for logs and artifacts."""
        return {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "current_news_report": final_state.get("current_news_report", ""),
            "strategy_report": final_state.get("strategy_report", ""),
            "copy_trading_report": final_state.get("copy_trading_report", ""),
            "research_department_report": final_state.get("research_department_report", ""),
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        logged_state = self._build_logged_state(final_state)
        self.log_states_dict[str(trade_date)] = logged_state

        # Save to file. Reject ticker values that would escape the
        # results directory when joined as a path component.
        safe_ticker = safe_ticker_component(self.ticker)
        directory = Path(self.config["results_dir"]) / safe_ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        log_path = directory / f"full_states_log_{trade_date}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logged_state, f, indent=4)

        return logged_state

    def _save_run_artifacts(self, trade_date, final_state, logged_state, signal):
        """Save a complete per-run artifact bundle for reproducibility."""
        safe_ticker = safe_ticker_component(self.ticker)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        run_dir = (
            Path(self.config["results_dir"])
            / safe_ticker
            / str(trade_date)
            / f"run_{timestamp}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        self.last_run_artifact_dir = run_dir

        (run_dir / "final_state.json").write_text(
            json.dumps(logged_state, indent=2),
            encoding="utf-8",
        )
        (run_dir / "final_decision.md").write_text(
            final_state["final_trade_decision"],
            encoding="utf-8",
        )
        (run_dir / "signal.txt").write_text(f"{signal}\n", encoding="utf-8")

        metadata = {
            "ticker": self.ticker,
            "trade_date": str(trade_date),
            "run_timestamp_utc": timestamp,
            "llm_provider": self.config.get("llm_provider"),
            "quick_think_llm": self.config.get("quick_think_llm"),
            "deep_think_llm": self.config.get("deep_think_llm"),
            "max_debate_rounds": self.config.get("max_debate_rounds"),
            "max_risk_discuss_rounds": self.config.get("max_risk_discuss_rounds"),
            "checkpoint_enabled": bool(self.config.get("checkpoint_enabled")),
            "signal": signal,
        }
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        reports_dir = run_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_map = {
            "market_report.md": final_state.get("market_report", ""),
            "sentiment_report.md": final_state.get("sentiment_report", ""),
            "news_report.md": final_state.get("news_report", ""),
            "fundamentals_report.md": final_state.get("fundamentals_report", ""),
            "current_news_report.md": final_state.get("current_news_report", ""),
            "strategy_report.md": final_state.get("strategy_report", ""),
            "copy_trading_report.md": final_state.get("copy_trading_report", ""),
            "research_department_report.md": final_state.get("research_department_report", ""),
            "investment_plan.md": final_state.get("investment_plan", ""),
            "trader_investment_plan.md": final_state.get("trader_investment_plan", ""),
            "final_trade_decision.md": final_state.get("final_trade_decision", ""),
        }
        for filename, content in report_map.items():
            if content:
                (reports_dir / filename).write_text(content, encoding="utf-8")

        board_lines = [
            f"Ticker: {self.ticker}",
            f"Trade Date: {trade_date}",
            f"Signal: {signal}",
            f"Provider: {self.config.get('llm_provider')}",
            f"Quick LLM: {self.config.get('quick_think_llm')}",
            f"Deep LLM: {self.config.get('deep_think_llm')}",
            "",
            "Final Decision:",
            final_state.get("final_trade_decision", ""),
        ]
        (run_dir / "board_summary.md").write_text(
            "\n".join(board_lines),
            encoding="utf-8",
        )

    def _maybe_submit_paper_order(self, ticker: str, final_trade_decision: str) -> None:
        """Map final decision to order intent and optionally submit to Alpaca paper."""
        intent = decision_to_order_intent(
            ticker=ticker,
            final_trade_decision=final_trade_decision,
            base_quantity=float(self.config.get("paper_order_quantity", 1.0)),
        )
        if intent is None:
            logger.info("No paper order submitted (Hold decision).")
            if self.last_run_artifact_dir:
                (self.last_run_artifact_dir / "paper_order_result.json").write_text(
                    json.dumps({"submitted": False, "reason": "hold_decision"}, indent=2),
                    encoding="utf-8",
                )
            return

        broker = AlpacaPaperBroker()
        account = broker.get_account()
        clock = broker.get_clock()
        latest_trade = broker.get_latest_trade(ticker)
        latest_price = latest_trade.get("p")

        policy = evaluate_order_policy(
            intent=intent,
            account=account,
            market_open=bool(clock.get("is_open")),
            latest_price=float(latest_price) if latest_price is not None else None,
            config=self.config,
        )
        if not policy.allow:
            logger.info("Paper order blocked by policy: %s", policy.reason)
            if self.last_run_artifact_dir:
                (self.last_run_artifact_dir / "paper_order_result.json").write_text(
                    json.dumps(
                        {
                            "submitted": False,
                            "reason": "policy_blocked",
                            "policy_reason": policy.reason,
                            "intent": intent.__dict__,
                            "latest_trade": latest_trade,
                            "market_open": clock.get("is_open"),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            return

        order = broker.submit_order(intent)
        logger.info(
            "Paper order submitted: id=%s status=%s symbol=%s side=%s qty=%s",
            order.get("id"),
            order.get("status"),
            order.get("symbol"),
            order.get("side"),
            order.get("qty"),
        )
        if self.last_run_artifact_dir:
            (self.last_run_artifact_dir / "paper_order_result.json").write_text(
                json.dumps(
                    {
                        "submitted": True,
                        "intent": intent.__dict__,
                        "policy_reason": policy.reason,
                        "order_notional_usd": policy.order_notional_usd,
                        "latest_trade": latest_trade,
                        "order": order,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
