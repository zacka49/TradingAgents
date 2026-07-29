# Persona models (Track A of the model specialization plan)

Nine `ta-*` Ollama models that give each agent role a purpose-built system prompt
and temperature, layered on a size-appropriate base. See
`docs/model_specialization_plan.md` for the full rationale.

## What's here

| Model | Base | Temp | Roles it serves |
| --- | --- | --- | --- |
| `ta-screener` | `llama3.2:3b` | 0.1 | opportunity scout, stock discovery, news, social, current-news, github, copy-trading |
| `ta-analyst` | `qwen3:4b-instruct` | 0.2 | market analyst, fundamentals analyst |
| `ta-quant` | `qwen3:4b-instruct` | 0.2 | strategy researcher |
| `ta-bull` | `qwen3:4b-instruct` | 0.6 | bull researcher, aggressive debator |
| `ta-bear` | `qwen3:4b-instruct` | 0.6 | bear researcher, conservative debator |
| `ta-synth` | `llama3.1:8b` | 0.3 | neutral debator, research director |
| `ta-decider` | `llama3.1:8b` | 0.2 | research manager, CIO, portfolio manager, trader, trading-desk, portfolio-office |
| `ta-risk` | `llama3.1:8b` | 0.2 | risk office, operations/compliance |
| `ta-coach` | `llama3.1:8b` | 0.2 | evaluation analyst, training coach |

Deep tier = `llama3.1:8b`, chosen in A0: fast (~6s/answer warm, ~22 tok/s),
non-reasoning so it emits clean structured verdicts. `qwen3.5:9b` was rejected
(3m+ cold, verbose chain-of-thought). To trade speed for quality, rebuild the
four deep personas `FROM qwen3.5:9b`.

## Build (or rebuild) the models

```powershell
powershell -File scripts/build_persona_models.ps1
```
Idempotent. The custom names **must** appear in `ollama list`, or the local-first
compute policy falls each role back to the generic quick/deep model.

## Wire the roles

Append `ollama/persona_role_overrides.env` to your real (git-ignored) `.env`:
```bash
cat ollama/persona_role_overrides.env >> .env
```

## Verify the wiring survived the guard

```python
from dotenv import load_dotenv; load_dotenv(".env")
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.compute_policy import apply_compute_policy
roles = apply_compute_policy(dict(DEFAULT_CONFIG))["role_model_overrides"]
missing = [r for r, m in roles.items() if not str(m).startswith("ta-")]
print("all wired" if not missing else f"fell back: {missing}")
```
Expect `all wired` (26 roles).
