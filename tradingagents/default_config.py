import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    "training_memory_log_path": os.getenv("TRADINGAGENTS_TRAINING_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "agent_training_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    "training_memory_max_entries": 10,
    "training_memory_context_entries": 3,
    # Persist comprehensive per-run artifacts (state, decision, reports) under
    # results_dir/<ticker>/<trade_date>/<run_id>/.
    "save_run_artifacts": True,
    # Optional: execute paper orders from final team decisions.
    "auto_submit_paper_orders": False,
    "paper_order_quantity": 1.0,
    # CEO risk policy defaults (paper-trading safety rails)
    "enforce_market_open": True,
    "max_position_notional_usd": 1000.0,
    "max_order_notional_usd": 250.0,
    "allowed_symbols": [],  # empty => allow all symbols
    # LLM settings
    "llm_provider": os.getenv("TRADINGAGENTS_LLM_PROVIDER", "ollama"),
    "deep_think_llm": os.getenv("TRADINGAGENTS_DEEP_MODEL", os.getenv("OLLAMA_DEEP_MODEL", "qwen3:0.6b")),
    "quick_think_llm": os.getenv("TRADINGAGENTS_QUICK_MODEL", os.getenv("OLLAMA_QUICK_MODEL", "qwen3:0.6b")),
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # AI research department: runs after core analysts and before the
    # bull/bear debate, adding current-news, strategy, and copy-trading memos.
    "research_department_enabled": True,
    "github_research_enabled": True,
    # Pre-market discovery runs before the core analyst team and suggests 10
    # stocks/ETFs the rest of the business should consider.
    "opportunity_scout_enabled": True,
    "opportunity_scout_updates_focus_ticker": True,
    "stock_discovery_enabled": True,
    "autonomous_discovery_universe": [],
    "autonomous_discovery_max_universe": 45,
    "autonomous_discovery_history_period": "90d",
    "autonomous_discovery_enrichment_limit": 12,
    "autonomous_discovery_order_flow_limit": 3,
    "autonomous_discovery_min_price": 5.0,
    "autonomous_discovery_min_avg_volume": 1_000_000,
    # Expanded AI business departments around the core trading flow:
    # Investment Committee, Trading Desk, Risk Office, Portfolio Office,
    # Operations/Compliance, and Evaluation.
    "business_departments_enabled": True,
    "training_development_enabled": True,
    # Codex CEO mode: compute-light daily company workflow. Local Ollama can
    # provide one short staff memo, while Codex reviews the briefing pack in
    # this workspace before paper execution.
    "company_operating_mode": "codex_ceo",
    "compute_mode": "efficient",
    "ceo_approval_required": True,
    "autonomous_paper_trading_enabled": False,
    "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "ollama_staff_memo_enabled": True,
    "ollama_staff_model": os.getenv("OLLAMA_STAFF_MODEL", os.getenv("OLLAMA_QUICK_MODEL", "qwen3:0.6b")),
    "ollama_temperature": 0.1,
    "ollama_num_ctx": 2048,
    "ollama_num_predict": 350,
    "ollama_timeout_seconds": 90,
    "codex_ceo_max_universe": 30,
    "codex_ceo_watchlist_size": 10,
    "codex_ceo_history_period": "60d",
    "codex_ceo_min_price": 5.0,
    "codex_ceo_min_avg_volume": 1_000_000,
    "codex_ceo_universe": [],
    "strategy_profile_name": "balanced",
    "codex_ceo_realtime_scan_enabled": False,
    "codex_ceo_realtime_fallback_to_daily": True,
    "codex_ceo_realtime_lookback_minutes": 90,
    "codex_ceo_realtime_min_recent_volume": 2_500,
    "codex_ceo_realtime_max_spread_pct": 0.12,
    "codex_ceo_realtime_high_volatility_pct": 0.85,
    "codex_ceo_realtime_max_trade_age_seconds": 180,
    "codex_ceo_order_flow_enrichment_limit": 6,
    "alpaca_data_timeout_seconds": 20,
    "portfolio_target_positions": 5,
    "portfolio_deploy_pct": 0.60,
    "portfolio_max_position_weight": 0.20,
    "portfolio_max_deploy_usd": 1500.0,
    "portfolio_min_order_notional_usd": 25.0,
    "portfolio_liquidate_non_targets": False,
    "day_trade_auto_strategies": [
        "momentum_breakout",
        "relative_strength_continuation",
    ],
    "day_trade_min_strategy_confidence": 0.58,
    "day_trade_stop_loss_multiplier": 1.0,
    "day_trade_take_profit_multiplier": 1.0,
    "day_trade_min_stop_loss_pct": 0.005,
    "day_trade_max_stop_loss_pct": 0.10,
    "day_trade_min_take_profit_pct": 0.01,
    "day_trade_max_take_profit_pct": 0.20,
    "day_trade_block_risk_flags": [],
    "realtime_score_minimum": -9999.0,
    "use_bracket_orders": True,
    "refresh_live_prices_before_submit": True,
    # Live order-flow tooling uses Alpaca L1 trades/quotes by default. It
    # derives volume profile, delta, large prints, and absorption flags; true
    # L2/L3 heatmaps require an additional depth provider.
    "order_flow_enabled": True,
    "order_flow_provider": os.getenv("ORDER_FLOW_PROVIDER", "alpaca"),
    "order_flow_lookback_minutes": 15,
    "order_flow_large_trade_min_size": int(os.getenv("ORDER_FLOW_LARGE_TRADE_MIN_SIZE", "1000")),
    "backtest_lab_enabled": True,
    "backtest_lab_gate_targets": True,
    "backtest_lab_min_bars": 40,
    "backtest_lab_min_strategy_return_pct": -10.0,
    "backtest_lab_min_excess_return_pct": -8.0,
    "technology_scout_enabled": True,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}
