"""Local-only config template for TradingAgents + Ollama.

Copy this file to local_ollama_config.py and adjust model names as needed.
"""

from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()

# Local LLM provider via Ollama OpenAI-compatible API.
config["llm_provider"] = "ollama"
config["backend_url"] = "http://localhost:11434/v1"
config["ollama_base_url"] = "http://localhost:11434"
config["llm_budget_mode"] = "local_only"
config["allow_online_llm"] = False

# Good local defaults for modest hardware. `qwen3:4b-instruct` is the main
# instruction-following worker; `llama3.2:3b` is a faster summarizer; Phi is
# useful for risk/evaluation-style review.
config["quick_think_llm"] = "qwen3:4b-instruct"
config["deep_think_llm"] = "qwen3:4b-instruct"
config["ollama_staff_model"] = "qwen3:4b-instruct"

config["role_model_overrides"] = {
    "current_news_scout": "llama3.2:3b",
    "github_researcher": "llama3.2:3b",
}

# Keep costs low while validating setup.
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1

# Keep full run records for offline evaluation.
config["save_run_artifacts"] = True
