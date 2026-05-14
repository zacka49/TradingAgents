# Local LLM + Paper Trading Setup

This guide is setup-only. It does not require running TradingAgents yet.

## 1) Local LLM stack (Ollama)

### Why Ollama here
- TradingAgents already supports `llm_provider="ollama"` in this repo.
- Ollama exposes OpenAI-compatible endpoints at `http://localhost:11434/v1`.
- This lets the same graph code run with local models and no per-request cloud token billing.

### Model choice recommendation
Given your current machine constraints observed during setup:
- `qwen3:8b` was too large for available memory layout.
- `qwen3:4b` pull failed due to disk-space limits.
- `qwen3:0.6b` is currently the safest local baseline and was successfully pulled.

Use this progression:
1. `qwen3:0.6b` for connectivity + pipeline validation
2. `qwen3:4b` once disk space is freed
3. `qwen3:8b` or `gpt-oss:20b` only when RAM/VRAM and disk headroom are sufficient

The runtime now enforces a local-first compute policy. Hosted LLM providers and
Ollama `:cloud` models are blocked unless both opt-in environment variables are
set:

```powershell
$env:TRADINGAGENTS_ALLOW_ONLINE_LLM = "1"
$env:TRADINGAGENTS_LLM_BUDGET_MODE = "allow_online"
```

See [local_first_compute_policy.md](/D:/AI%20projects/Git%20repo%20for%20inspection/TradingAgents/docs/local_first_compute_policy.md)
for the guardrails and model priority ladder.

Reference model sizes and capabilities:
- Qwen3 library page (sizes + tool support)
- GPT-OSS library page (sizes + memory guidance)

## 2) TradingAgents local config

Use [local_ollama_config.example.py](/D:/AI%20projects/Git%20repo%20for%20inspection/TradingAgents/configs/local_ollama_config.example.py) as your template.

Key settings:
- `llm_provider = "ollama"`
- `backend_url = "http://localhost:11434/v1"`
- local model IDs for `quick_think_llm` and `deep_think_llm`
- `save_run_artifacts = True`

## 3) Paper trading account setup (Alpaca)

### Recommended paper broker
Alpaca Paper Trading is a practical first integration because:
- Public API is stable and widely used for algo workflows
- Paper endpoint mirrors live endpoint behavior with separate keys
- Easy key rotation and account reset from dashboard

### Create account + keys
1. Create/login to Alpaca.
2. Switch to Paper Trading account in dashboard.
3. Generate paper API key + secret.
4. Confirm paper base URL:
   - `https://paper-api.alpaca.markets`

### Environment variables to set
Add to your local secrets file (not committed):
- `APCA_API_KEY_ID=...`
- `APCA_API_SECRET_KEY=...`
- `APCA_API_BASE_URL=https://paper-api.alpaca.markets`

## 4) Repo scaffolding added for paper integration

Added interfaces and starter adapter:
- [paper_broker.py](/D:/AI%20projects/Git%20repo%20for%20inspection/TradingAgents/tradingagents/execution/paper_broker.py)
- [alpaca_paper.py](/D:/AI%20projects/Git%20repo%20for%20inspection/TradingAgents/tradingagents/execution/alpaca_paper.py)
- [decision_to_order.py](/D:/AI%20projects/Git%20repo%20for%20inspection/TradingAgents/tradingagents/execution/decision_to_order.py)

What this gives you now:
- Unified `PaperBroker` interface
- `AlpacaPaperBroker` with `submit_order`, `get_positions`, `get_account`
- Initial decision-to-order mapper from final rating text

## 5) Before first live paper run checklist

1. Move secrets out of `.env.example` into private `.env`.
2. Keep `.env.example` with blanks only.
3. Ensure enough disk space in `C:\Users\Zacka\.ollama\models` for chosen model.
4. Choose a model your RAM/VRAM can load.
5. Start with tiny position size and one ticker.
6. Review order payload logs before enabling automatic order submission.

## 6) Next implementation step (when you say go)

Wire the graph output to paper execution:
1. Parse `final_trade_decision` into `OrderIntent`
2. Add risk guard checks (market open, position caps, buying power)
3. Submit through `AlpacaPaperBroker`
4. Save broker request/response under per-run artifact folder
