"""Local-only config template for TradingAgents + Ollama.

Copy this file to local_ollama_config.py and adjust model names as needed.
"""

from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()

# Local LLM provider via Ollama OpenAI-compatible API.
config["llm_provider"] = "ollama"
config["backend_url"] = "http://localhost:11434/v1"

# Start with the same model for both roles; upgrade deep model later.
config["quick_think_llm"] = "qwen3:0.6b"
config["deep_think_llm"] = "qwen3:0.6b"

# Keep costs low while validating setup.
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1

# Keep full run records for offline evaluation.
config["save_run_artifacts"] = True
