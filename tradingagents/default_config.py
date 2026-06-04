import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    "training_memory_log_path": os.getenv("TRADINGAGENTS_TRAINING_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "agent_training_memory.md")),
    "specialist_memory_dir": os.getenv("TRADINGAGENTS_SPECIALIST_MEMORY_DIR", os.path.join(_TRADINGAGENTS_HOME, "memory", "specialists")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    "training_memory_max_entries": 10,
    "training_memory_context_entries": 3,
    "specialist_memory_max_entries": 30,
    "specialist_memory_context_entries": 2,
    "specialist_memory_enabled": True,
    "agent_scorecards_enabled": True,
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
    "deep_think_llm": os.getenv("TRADINGAGENTS_DEEP_MODEL", os.getenv("OLLAMA_DEEP_MODEL", "qwen3:4b-instruct")),
    "quick_think_llm": os.getenv("TRADINGAGENTS_QUICK_MODEL", os.getenv("OLLAMA_QUICK_MODEL", "qwen3:4b-instruct")),
    # Local-first compute policy. Hosted LLM providers and Ollama cloud models
    # are blocked by default so iterative runs do not quietly burn token quota.
    # To opt in deliberately, set:
    #   TRADINGAGENTS_ALLOW_ONLINE_LLM=1
    #   TRADINGAGENTS_LLM_BUDGET_MODE=allow_online
    "llm_budget_mode": os.getenv("TRADINGAGENTS_LLM_BUDGET_MODE", "local_only"),
    "allow_online_llm": os.getenv("TRADINGAGENTS_ALLOW_ONLINE_LLM", "").strip().lower()
    in {"1", "true", "yes", "y", "on"},
    "ollama_model_probe_timeout_seconds": 1.0,
    "local_quick_model_priority": [
        "qwen3:4b-instruct",
        "llama3.2:3b",
        "phi4-mini:latest",
        "qwen3:8b",
        "qwen3:latest",
        "qwen3:4b",
        "qwen3:1.7b",
        "qwen3:0.6b",
    ],
    "local_deep_model_priority": [
        "qwen3:4b-instruct",
        "phi4-mini-reasoning:latest",
        "phi4-mini:latest",
        "gpt-oss:20b",
        "gpt-oss:latest",
        "qwen3:30b",
        "qwen3:32b",
        "qwen3:14b",
        "qwen3:8b",
        "qwen3:latest",
        "qwen3:4b",
        "qwen3:0.6b",
    ],
    "role_model_overrides": {
        "opportunity_scout": os.getenv("TRADINGAGENTS_OPPORTUNITY_SCOUT_MODEL", "llama3.2:3b"),
        "stock_discovery": os.getenv("TRADINGAGENTS_STOCK_DISCOVERY_MODEL", "qwen3:4b-instruct"),
        "market_analyst": os.getenv("TRADINGAGENTS_MARKET_ANALYST_MODEL", "qwen3:4b-instruct"),
        "social_media_analyst": os.getenv("TRADINGAGENTS_SOCIAL_ANALYST_MODEL", "llama3.2:3b"),
        "news_analyst": os.getenv("TRADINGAGENTS_NEWS_ANALYST_MODEL", "llama3.2:3b"),
        "fundamentals_analyst": os.getenv("TRADINGAGENTS_FUNDAMENTALS_ANALYST_MODEL", "qwen3:4b-instruct"),
        "current_news_scout": os.getenv("TRADINGAGENTS_CURRENT_NEWS_MODEL", "llama3.2:3b"),
        "strategy_researcher": os.getenv("TRADINGAGENTS_STRATEGY_RESEARCHER_MODEL", "qwen3:4b-instruct"),
        "copy_trading_researcher": os.getenv("TRADINGAGENTS_COPY_TRADING_MODEL", "qwen3:4b-instruct"),
        "github_researcher": os.getenv("TRADINGAGENTS_GITHUB_RESEARCH_MODEL", "llama3.2:3b"),
        "research_director": os.getenv("TRADINGAGENTS_RESEARCH_DIRECTOR_MODEL", "qwen3:4b-instruct"),
        "bull_researcher": os.getenv("TRADINGAGENTS_BULL_RESEARCHER_MODEL", "qwen3:4b-instruct"),
        "bear_researcher": os.getenv("TRADINGAGENTS_BEAR_RESEARCHER_MODEL", "qwen3:4b-instruct"),
        "research_manager": os.getenv("TRADINGAGENTS_RESEARCH_MANAGER_MODEL", "qwen3:4b-instruct"),
        "chief_investment_officer": os.getenv("TRADINGAGENTS_CIO_MODEL", "qwen3:4b-instruct"),
        "trading_desk_strategist": os.getenv("TRADINGAGENTS_TRADING_DESK_MODEL", "qwen3:4b-instruct"),
        "risk_office_guardian": os.getenv("TRADINGAGENTS_RISK_OFFICE_MODEL", "qwen3:4b-instruct"),
        "portfolio_office_allocator": os.getenv("TRADINGAGENTS_PORTFOLIO_OFFICE_MODEL", "qwen3:4b-instruct"),
        "operations_compliance_auditor": os.getenv("TRADINGAGENTS_OPERATIONS_MODEL", "qwen3:4b-instruct"),
        "evaluation_analyst": os.getenv("TRADINGAGENTS_EVALUATION_MODEL", "qwen3:4b-instruct"),
        "training_development_coach": os.getenv("TRADINGAGENTS_TRAINING_COACH_MODEL", "qwen3:4b-instruct"),
        "trader": os.getenv("TRADINGAGENTS_TRADER_MODEL", "qwen3:4b-instruct"),
        "aggressive_debator": os.getenv("TRADINGAGENTS_AGGRESSIVE_RISK_MODEL", "qwen3:4b-instruct"),
        "neutral_debator": os.getenv("TRADINGAGENTS_NEUTRAL_RISK_MODEL", "qwen3:4b-instruct"),
        "conservative_debator": os.getenv("TRADINGAGENTS_CONSERVATIVE_RISK_MODEL", "qwen3:4b-instruct"),
        "portfolio_manager": os.getenv("TRADINGAGENTS_PORTFOLIO_MANAGER_MODEL", "qwen3:4b-instruct"),
    },
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "xhigh", "high", "medium", "low"
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
    "ollama_staff_model": os.getenv("OLLAMA_STAFF_MODEL", os.getenv("OLLAMA_QUICK_MODEL", "qwen3:4b-instruct")),
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
    "codex_ceo_news_political_scan_enabled": True,
    "codex_ceo_news_political_max_symbols": 60,
    "codex_ceo_news_political_articles_per_query": 8,
    "codex_ceo_news_political_queries": [],
    "codex_ceo_news_political_fallback_to_base": True,
    "codex_ceo_news_catalyst_score_bonus": 0.25,
    "codex_ceo_news_catalyst_max_bonus": 1.5,
    "codex_ceo_news_day_trade_fit_bonus": 0.20,
    "codex_ceo_news_day_trade_fit_max_bonus": 2.0,
    "strategy_profile_name": "balanced",
    "codex_ceo_realtime_scan_enabled": False,
    "codex_ceo_realtime_fallback_to_daily": True,
    "codex_ceo_realtime_lookback_minutes": 90,
    "codex_ceo_realtime_min_recent_volume": 2_500,
    "codex_ceo_realtime_max_spread_pct": 0.12,
    "codex_ceo_realtime_high_volatility_pct": 0.85,
    "codex_ceo_realtime_max_trade_age_seconds": 180,
    "codex_ceo_order_flow_enrichment_limit": 6,
    "codex_ceo_day_trade_min_fit_score": 0.0,
    "codex_ceo_day_trade_preferred_min_volume_ratio": 1.05,
    "codex_ceo_day_trade_preferred_min_volatility_pct": 0.6,
    "codex_ceo_day_trade_preferred_max_volatility_pct": 4.5,
    "codex_ceo_day_trade_min_abs_move_pct": 1.0,
    "alpaca_data_timeout_seconds": 20,
    "portfolio_target_positions": 5,
    "portfolio_deploy_pct": 0.60,
    "portfolio_max_position_weight": 0.20,
    "portfolio_max_deploy_usd": 1500.0,
    "portfolio_min_order_notional_usd": 25.0,
    "portfolio_liquidate_non_targets": False,
    "day_trader_flatten_at_close": True,
    "day_trader_flatten_minutes_before_close": 5,
    "day_trader_stop_new_entries_minutes_before_close": 15,
    "day_trader_flatten_on_max_cycles": True,
    "day_trader_cancel_orders_before_flatten": True,
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
    "strategy_research_enabled": True,
    "strategy_research_gate_candidates": True,
    "strategy_research_gate_targets": True,
    "strategy_research_min_status_for_trading": "paper_trade_candidate",
    "strategy_library_dir": os.getenv(
        "TRADINGAGENTS_STRATEGY_LIBRARY_DIR",
        "knowledge/strategy_library",
    ),
    "strategy_research_evidence_root": os.getenv(
        "TRADINGAGENTS_STRATEGY_EVIDENCE_ROOT",
        "",
    ),
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
