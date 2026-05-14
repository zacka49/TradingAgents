# Local-First Compute Policy

TradingAgents now defaults to a local-only LLM budget policy. The business can
iterate many times per day, so hosted LLM calls are blocked unless you
deliberately opt in.

## Default behavior

- `llm_provider` defaults to `ollama`.
- Hosted providers such as OpenAI, Anthropic, Google, Groq, OpenRouter, xAI,
  DeepSeek, Qwen, GLM, and Azure are forced back to local Ollama in
  `local_only` mode.
- Ollama cloud models such as names ending in `:cloud` are treated as online
  compute and are blocked by default.
- Local Ollama is expected at `http://localhost:11434` and the OpenAI-compatible
  endpoint is `http://localhost:11434/v1`.
- A `compute_policy_report` is attached to the runtime config so runs can show
  whether a provider or model was replaced.

## Recommended local model ladder

Use the smallest model to prove the workflow, then move up only when the
machine has enough RAM/VRAM and disk headroom:

1. `qwen3:0.6b` for connectivity and cheap smoke tests.
2. `qwen3:4b` for better day-to-day local analysis on modest hardware.
3. `qwen3:8b` for the quick-thinking role when memory allows.
4. `gpt-oss:20b` for the deep-thinking role on a stronger local machine.

The guard will inspect installed local Ollama models with `/api/tags` and pick
the strongest installed option from the configured priority lists. Cloud models
reported by Ollama are ignored. If the local Ollama endpoint is unavailable, the
guard falls back to `qwen3:0.6b` instead of trying a hosted provider.

## Opting into hosted LLMs

Only opt in when you are comfortable with quota and billing risk:

```powershell
$env:TRADINGAGENTS_ALLOW_ONLINE_LLM = "1"
$env:TRADINGAGENTS_LLM_BUDGET_MODE = "allow_online"
```

Without both settings, CLI selections and environment variables that point to a
hosted provider are still guarded back to local Ollama.
