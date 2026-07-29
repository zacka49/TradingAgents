# Model Specialization Plan

**Status:** Ready to execute
**Author:** Prepared for autonomous execution by Claude Code or Codex
**Last updated:** 2026-07-29
**Scope:** Specialize the LLMs behind the AI trading firm's agents using only tools the operator already has, without spending money on hosted APIs or fine-tuning services.

---

## 0. How to use this document (read first)

You are an automated coding agent (Claude Code or Codex) executing this plan. Work through it **task by task in order**. Each task has:

- **Goal** — what "done" means in one line.
- **Files / commands** — the exact edits and shell commands. Shell is Windows PowerShell unless noted.
- **Acceptance** — an objective check you must run and pass before moving on.
- **Rollback** — how to undo if the acceptance check fails.

Rules for the whole plan:

- **Do not enable hosted/online LLMs.** Keep `TRADINGAGENTS_LLM_BUDGET_MODE=local_only`. Do not set `TRADINGAGENTS_ALLOW_ONLINE_LLM`. The paper-trading business runs on local Ollama by policy.
- **Do not touch order-submission gates, risk caps, or anything under `scripts/ops/` execution paths.** This plan changes *which model answers*, never *whether an order is placed*.
- **Paper trading only.** Never flip `auto_submit_paper_orders`, `autonomous_paper_trading_enabled`, or market gates.
- **Never commit secrets.** Model overrides go in the repo-root `.env` (already git-ignored) or in `default_config.py` defaults — never hardcode API keys.
- **Stop and ask the operator** at any point marked **⏸ OPERATOR DECISION**.
- After each task, run its acceptance check and the test suite subset noted. Do not batch-commit; commit per phase with the message templates given.

If any command referencing a model fails because the model isn't installed, that is expected in early tasks — pull/create it as the task instructs rather than working around it.

---

## 1. Context: how model selection works in this repo

Understand this before editing anything.

1. **Role → model map.** `tradingagents/default_config.py` → `role_model_overrides` (~line 70) maps each of 27 agent roles to an Ollama model string. Each entry reads an env var, e.g.:
   ```python
   "bear_researcher": os.getenv("TRADINGAGENTS_BEAR_RESEARCHER_MODEL", "qwen3:4b-instruct"),
   ```
   So the intended, low-risk way to change a role's model is to **set its env var in `.env`** — no code change needed.

2. **Runtime wiring.** `tradingagents/graph/trading_graph.py` → `_create_role_llms()` (~line 182) builds one LLM client per distinct model string and hands each agent its role's client. Distinct models are cached, so reusing a model across roles costs nothing extra.

3. **The local-first guard (important).** `tradingagents/llm_clients/compute_policy.py` → the `local_only` guard (~line 277) rewrites `role_model_overrides`: **any role model that is not returned by `ollama list` is replaced** with the generic quick/deep fallback (`LOCAL_ROLE_MODEL_FALLBACKS`, ~line 64, decides which). **Consequence:** a custom model name only "sticks" if you have actually run `ollama create <name>`. Always create/pull before wiring.

4. **Personas today.** Each agent's system/instruction text is a hardcoded f-string in its file under `tradingagents/agents/**`. Example: `tradingagents/agents/researchers/bull_researcher.py`. An Ollama Modelfile `SYSTEM` prompt is *prepended* to that as a system message, so Modelfile personas stack cleanly on top of existing prompts without code edits.

5. **The job spec already exists.** `docs/agent_skill_training_matrix.md` lists every role's Department, Primary Skill, Drill, and Success Metric. **Use it as the source of truth** for each persona's behavior and for eval pass/fail criteria. Do not invent new role definitions.

### What the operator's tools can and cannot do

| Tool | Role in this plan | Can fine-tune weights? |
| --- | --- | --- |
| Claude Pro (chat) | Author personas; **generate distillation datasets**; write eval rubrics | No |
| ChatGPT Plus (chat) | Same as above; second opinion / data diversity | No (Plus ≠ API) |
| Ollama (local) | **Runtime** for every agent; host Modelfile personas and any fine-tuned GGUF | No (serves, doesn't train) |
| Free cloud GPU (Colab / Kaggle) + Unsloth | The **only** real fine-tuning path (LoRA) | Yes |

Implication: **95% of the wins here are prompt/persona/model-tier changes (Phases A–C), which need no GPU and no money.** Actual fine-tuning (Phase D) is optional and reserved for a small number of high-value roles, and even then the training runs on free cloud GPUs while Claude/ChatGPT only generate the data.

---

## 2. Current-state audit (what's wrong today)

From `role_model_overrides` and the agent files:

- **No model diversity.** 24 of 27 roles use `qwen3:4b-instruct`; 3 screeners use `llama3.2:3b`. Every "deep" decision role (research_manager, chief_investment_officer, risk_office_guardian, portfolio_manager, research_director, evaluation_analyst) runs on the same small 4B model as the screeners.
- **The debate is an echo chamber.** `bull_researcher`, `bear_researcher`, `aggressive_debator`, `conservative_debator`, `neutral_debator` share one model and near-identical prompting. A debate between five copies of the same 4B model with the same temperature produces low-signal consensus, not genuine adversarial pressure.
- **No temperature differentiation.** Analysts (want low temp, deterministic, structured) and debaters (want higher temp, divergent) get the same defaults.
- **Specialist knowledge isn't in the models.** Your `knowledge/strategy_library` and per-role specialist memory exist but aren't consistently injected as grounding for the roles that should use them.

Goal end-state: a **tiered roster** where each role runs a model + persona matched to its job, sourced from the skill matrix.

---

## 3. Target roster (end state)

Three tiers. Column "Change" = `INSTEAD` (replace current model) or `EXTRA` (new specialized persona model layered on).

| Tier | Roles | Base model | Persona (Modelfile) | Temp | Change |
| --- | --- | --- | --- | --- | --- |
| **T1 High-volume screeners** | opportunity_scout, stock_discovery, news_analyst, social_media_analyst, current_news_scout, github_researcher, copy_trading_researcher | `llama3.2:3b` (keep small/fast) | Tight, structured-output-only persona | 0.1 | EXTRA persona |
| **T2 Analysts & quant** | market_analyst, fundamentals_analyst, strategy_researcher | `qwen3:4b-instruct` | Analytical, evidence-first persona; strategy_researcher LoRA candidate | 0.2 | EXTRA persona (+ later LoRA) |
| **T3a Debate — divergent** | bull_researcher, aggressive_debator | `qwen3:4b-instruct` | Strongly opinionated bull/aggressive persona | 0.6 | EXTRA persona + temp |
| **T3a Debate — divergent** | bear_researcher, conservative_debator | `qwen3:4b-instruct` | Strongly skeptical bear/conservative persona | 0.6 | EXTRA persona + temp |
| **T3b Debate — synthesis** | neutral_debator, research_director | deep model (see task A0) | Balanced synthesis persona | 0.3 | EXTRA persona + model tier |
| **T4 Decision-makers** | research_manager, chief_investment_officer, risk_office_guardian, portfolio_manager, trader, trading_desk_strategist, portfolio_office_allocator, operations_compliance_auditor | deep model (see task A0) | Decisive, caps-aware persona; risk/CIO are LoRA candidates | 0.2 | INSTEAD (model tier up) + persona |
| **T5 Review & training** | evaluation_analyst, training_development_coach | deep model | Rubric-driven scorer persona | 0.2 | EXTRA persona |

**Deep model choice is decided in Task A0** based on what the machine can actually run — do not assume `gpt-oss:20b` fits.

---

## Phase A — Baseline & capacity (no behavior change yet)

### Task A0 — Inventory Ollama and pick the deep model
- **Goal:** Know what's installed and choose the largest deep model this PC can run at usable speed.
- **Commands:**
  ```powershell
  ollama --version
  ollama list
  # Time a quick and a deep candidate on a real prompt:
  Measure-Command { ollama run qwen3:4b-instruct "Summarize why AMD momentum faded in 2 sentences." }
  Measure-Command { ollama run qwen3:14b        "Summarize why AMD momentum faded in 2 sentences." }
  ```
- **Also run** the repo's own health check so the result lands in the ops digest:
  ```powershell
  python scripts/ops/check_ollama_health.py
  ```
- **Decision rule for the deep model (record the choice at the top of `.env` as a comment):**
  - If `qwen3:14b` (or `gpt-oss:20b`) returns in **< ~30s** for the test prompt → use it as `DEEP_MODEL`.
  - Else fall back to `qwen3:8b`.
  - If even `qwen3:8b` is slow → `DEEP_MODEL = qwen3:4b-instruct` and rely on personas alone for the deep roles.
- **Pull whatever you selected** plus the screener model:
  ```powershell
  ollama pull llama3.2:3b
  ollama pull qwen3:4b-instruct
  ollama pull <DEEP_MODEL_YOU_CHOSE>
  ```
- **Acceptance:** `ollama list` shows `llama3.2:3b`, `qwen3:4b-instruct`, and your chosen deep model; `check_ollama_health.py` prints `status: ok` (or `degraded` only for models you deliberately deferred).
- **⏸ OPERATOR DECISION** if none of the deep candidates run acceptably — ask whether to accept 4B-only for decision roles or stop here.

---

## Phase B — Persona models via Modelfiles (biggest win, zero training)

This phase creates named Ollama models that bake a role-specific system prompt + temperature into the base model, then points the role env vars at them. No Python changes.

### Task B1 — Author personas from the skill matrix
- **Goal:** One Modelfile per persona group, with `SYSTEM` text derived from `docs/agent_skill_training_matrix.md` (Primary Skill, Drill, Success Metric for that role).
- **Where:** create `ollama/modelfiles/` in the repo root. One file per model below.
- **How to write each `SYSTEM` prompt:** open the skill matrix, find the role's row, and turn its Drill + Success Metric into an instruction. Keep each under ~200 words. Keep outputs structured where the agent expects structure.
- **Models to create (name → base → source rows in skill matrix):**

  | Custom model name | FROM base | Temp | Persona source (skill-matrix roles) |
  | --- | --- | --- | --- |
  | `ta-screener:latest` | `llama3.2:3b` | 0.1 | Opportunity Scout, Stock Discovery, News/Social Analyst, Current News Scout |
  | `ta-analyst:latest` | `qwen3:4b-instruct` | 0.2 | Market Analyst, Fundamentals Analyst |
  | `ta-quant:latest` | `qwen3:4b-instruct` | 0.2 | Strategy Researcher, Backtest Lab |
  | `ta-bull:latest` | `qwen3:4b-instruct` | 0.6 | Bull Researcher, Aggressive Analyst |
  | `ta-bear:latest` | `qwen3:4b-instruct` | 0.6 | Bear Researcher, Conservative Analyst |
  | `ta-synth:latest` | `<DEEP_MODEL>` | 0.3 | Neutral Analyst, Research Director |
  | `ta-decider:latest` | `<DEEP_MODEL>` | 0.2 | Research Manager, CIO, Portfolio Manager, Trader, Trading Desk Strategist |
  | `ta-risk:latest` | `<DEEP_MODEL>` | 0.2 | Risk Office Guardian, Operations Compliance Auditor |
  | `ta-coach:latest` | `<DEEP_MODEL>` | 0.2 | Evaluation Analyst, Training Development Coach |

- **Modelfile template** (fill `SYSTEM`, adjust temp; `num_ctx`/`num_predict` mirror `default_config.py` ollama settings):
  ```dockerfile
  # ollama/modelfiles/ta-bear.Modelfile
  FROM qwen3:4b-instruct
  PARAMETER temperature 0.6
  PARAMETER num_ctx 4096
  PARAMETER num_predict 512
  SYSTEM """You are the Bear Researcher / Conservative Analyst for a paper-trading
  equities desk. Your job: challenge every long thesis on liquidity, catalyst
  quality, valuation, correlation, and backtest robustness. For each stock you
  MUST surface at least one concrete blocker or missing-evidence item, and state
  the invalidation level that would prove you wrong. Prefer 'watch-only' or
  'risk-review' over 'trade' whenever evidence is thin. Never soften a real risk
  to sound agreeable. Output: (1) top risks as bullets, (2) the single most
  likely reason this trade loses money, (3) verdict: block / watch / risk-review."""
  ```
- **Acceptance:** the folder contains one Modelfile per row above, each with a non-empty role-specific `SYSTEM`. (No models created yet — next task.)
- **Rollback:** delete `ollama/modelfiles/`.

### Task B2 — Build the persona models and a rebuild script
- **Goal:** Register every persona model in Ollama and make rebuilding reproducible.
- **Create** `scripts/build_persona_models.ps1` that loops the Modelfiles and runs `ollama create`:
  ```powershell
  # scripts/build_persona_models.ps1
  Get-ChildItem "ollama/modelfiles/*.Modelfile" | ForEach-Object {
      $name = "ta-" + ($_.BaseName -replace '^ta-','')   # ta-bear.Modelfile -> ta-bear
      Write-Host "Creating $name from $($_.Name)"
      ollama create "$name`:latest" -f $_.FullName
  }
  ollama list | Select-String "ta-"
  ```
- **Run it:** `powershell -File scripts/build_persona_models.ps1`
- **Acceptance:** `ollama list` shows every `ta-*:latest` model. Spot-check one persona actually behaves:
  ```powershell
  ollama run ta-bear:latest "Make the bull case for NVDA."   # should refuse to cheerlead and surface risks instead
  ```
- **Rollback:** `ollama rm ta-bear:latest` (etc.), or `ollama list | Select-String ta- | ...` to remove all `ta-*`.

### Task B3 — Wire roles to persona models via `.env`
- **Goal:** Point each role's env var at its persona model. Because `compute_policy` only keeps models that are installed (Task B2 guarantees that), these will stick.
- **Edit** repo-root `.env` (create if missing; it is git-ignored). Add the block below. Env var names are the exact ones read in `default_config.py`:
  ```dotenv
  # ---- Model specialization (see docs/model_specialization_plan.md) ----
  TRADINGAGENTS_LLM_PROVIDER=ollama
  TRADINGAGENTS_LLM_BUDGET_MODE=local_only

  # T1 screeners
  TRADINGAGENTS_OPPORTUNITY_SCOUT_MODEL=ta-screener:latest
  TRADINGAGENTS_STOCK_DISCOVERY_MODEL=ta-screener:latest
  TRADINGAGENTS_NEWS_ANALYST_MODEL=ta-screener:latest
  TRADINGAGENTS_SOCIAL_ANALYST_MODEL=ta-screener:latest
  TRADINGAGENTS_CURRENT_NEWS_MODEL=ta-screener:latest
  TRADINGAGENTS_GITHUB_RESEARCH_MODEL=ta-screener:latest
  TRADINGAGENTS_COPY_TRADING_MODEL=ta-screener:latest

  # T2 analysts & quant
  TRADINGAGENTS_MARKET_ANALYST_MODEL=ta-analyst:latest
  TRADINGAGENTS_FUNDAMENTALS_ANALYST_MODEL=ta-analyst:latest
  TRADINGAGENTS_STRATEGY_RESEARCHER_MODEL=ta-quant:latest

  # T3 debate
  TRADINGAGENTS_BULL_RESEARCHER_MODEL=ta-bull:latest
  TRADINGAGENTS_AGGRESSIVE_RISK_MODEL=ta-bull:latest
  TRADINGAGENTS_BEAR_RESEARCHER_MODEL=ta-bear:latest
  TRADINGAGENTS_CONSERVATIVE_RISK_MODEL=ta-bear:latest
  TRADINGAGENTS_NEUTRAL_RISK_MODEL=ta-synth:latest
  TRADINGAGENTS_RESEARCH_DIRECTOR_MODEL=ta-synth:latest

  # T4 decision-makers
  TRADINGAGENTS_RESEARCH_MANAGER_MODEL=ta-decider:latest
  TRADINGAGENTS_CIO_MODEL=ta-decider:latest
  TRADINGAGENTS_PORTFOLIO_MANAGER_MODEL=ta-decider:latest
  TRADINGAGENTS_TRADER_MODEL=ta-decider:latest
  TRADINGAGENTS_TRADING_DESK_MODEL=ta-decider:latest
  TRADINGAGENTS_PORTFOLIO_OFFICE_MODEL=ta-decider:latest
  TRADINGAGENTS_RISK_OFFICE_MODEL=ta-risk:latest
  TRADINGAGENTS_OPERATIONS_MODEL=ta-risk:latest

  # T5 review & training
  TRADINGAGENTS_EVALUATION_MODEL=ta-coach:latest
  TRADINGAGENTS_TRAINING_COACH_MODEL=ta-coach:latest
  ```
- **Acceptance:** run a script that prints the guarded config and confirm no `ta-*` model was swapped out:
  ```powershell
  python -c "from dotenv import load_dotenv; load_dotenv('.env'); from tradingagents.default_config import DEFAULT_CONFIG; from tradingagents.llm_clients.compute_policy import apply_local_first_compute_policy as g; import json; c=g(dict(DEFAULT_CONFIG)); print(json.dumps(c['compute_policy_report']['role_models'], indent=2))"
  ```
  Every role above must show its `ta-*:latest` value, **not** a fallback. If any role shows a fallback, that persona model isn't installed — re-run Task B2. (If the guard's function name differs, find it with `grep -n "def .*compute_policy" tradingagents/llm_clients/compute_policy.py` and use that name.)
- **Rollback:** delete the added block from `.env`.

### Task B4 — Smoke-test one full run
- **Goal:** Prove the specialized roster runs end-to-end and the debate now diverges.
- **Command (use the repo's normal single-ticker entrypoint):**
  ```powershell
  python main.py   # or the documented single-run command in docs/README.md / docs/setup_local_ollama_and_paper.md
  ```
- **Acceptance:** run completes without model-not-found errors; in the saved run artifacts (under `results/.../run_id/`), the bull and bear sections now take visibly different stances (not paraphrases of each other). Record the run_id.
- **Rollback:** if it errors, revert `.env` block; capture the traceback for the operator.
- **Commit (Phase B):**
  ```
  Add local persona models for agent specialization

  Create ta-* Ollama Modelfile personas per skill matrix and wire role
  overrides to them. Debate roles now use divergent personas/temperatures;
  decision roles run on the deep model tier. No training, local-only.
  ```
  (Commit `ollama/modelfiles/`, `scripts/build_persona_models.ps1`, this doc, and any `default_config.py` default changes — **not** `.env`.)

---

## Phase C — Grounding (RAG) for the knowledge-heavy roles

Give the analysts and quant roles your own strategy knowledge at inference time instead of hoping the base model knows it.

### Task C1 — Confirm what grounding already exists
- **Goal:** Avoid rebuilding what's there. Inspect the specialist-memory system and strategy library wiring.
- **Read:** `tradingagents/company/agent_learning.py`, `tradingagents/agents/utils/memory.py`, and how `specialist_memory_dir` / `strategy_library_dir` (in `default_config.py`) are consumed.
- **Acceptance:** write a 5-line note at the end of this doc's "Execution log" section stating, for `strategy_researcher` and `market_analyst`, whether strategy-library content is already injected into the prompt (yes/no + file:line).

### Task C2 — Inject strategy-library context where it's missing
- **Goal:** For roles that lack it, add the relevant `knowledge/strategy_library` snippet(s) to the prompt the agent builds.
- **Only if C1 found a gap.** Prefer the *existing* memory/injection helper over new machinery. Keep the added context small (top-k, token-bounded to respect `ollama_num_ctx`).
- **Acceptance:** a run's `strategy_researcher` output cites a strategy that exists in `knowledge/strategy_library`. Add/adjust a test in `tests/` mirroring the nearest existing agent test.
- **⏸ OPERATOR DECISION** before adding any new dependency (vector DB, embeddings model). Default recommendation: reuse the existing file-based memory; only add `nomic-embed-text` via Ollama if keyword injection proves insufficient.

---

## Phase D — Optional: real fine-tuning by distillation (only if A–C aren't enough)

Do this **only** for roles where, after Phases B–C, run artifacts still show a persistent, specific weakness (e.g. strategy_researcher keeps mis-formatting setups, or risk_office keeps missing correlation). Fine-tuning is the last resort, not the default.

The pattern combines every tool the operator has:

1. **Collect real inputs** from saved run artifacts (`results/.../run_id/`) for the target role — the actual prompts that role saw.
2. **Generate gold answers with Claude Pro / ChatGPT Plus (chat).** Paste each input and the role's skill-matrix spec; have the frontier model produce the ideal answer. Save as JSONL `{"messages":[{"role":"system",...},{"role":"user",...},{"role":"assistant",...}]}`. Target 200–500 examples per role. This is *distillation*: the big model teaches the small local one.
3. **Fine-tune on a FREE cloud GPU** — Google Colab (free T4) or Kaggle (~30 GPU-hrs/week) using **Unsloth** LoRA on the role's base model (`qwen3:4b-instruct` or the deep model). Unsloth notebooks fit these sizes in free-tier VRAM.
4. **Export to GGUF** from the notebook, download it, and register locally:
   ```powershell
   ollama create ta-quant-ft:latest -f ollama/modelfiles/ta-quant-ft.Modelfile   # FROM ./strategy-researcher.gguf
   ```
5. **Wire + A/B test:** point only that one role's env var at `ta-quant-ft:latest`, run the eval harness (Phase E) head-to-head against `ta-quant:latest`, and keep the fine-tune **only if it wins on the skill-matrix success metric**.

- **⏸ OPERATOR DECISION** required before starting Phase D: confirm which 1–2 roles justify it, and that the operator will run the Colab/Kaggle notebook (the agent can write the notebook and the dataset-gen prompts, but cannot execute cloud GPU jobs).
- **Deliverables the agent can produce without a GPU:** the dataset-generation prompt templates (`docs/distillation/<role>_datagen_prompt.md`), a script to extract role inputs from run artifacts into a JSONL skeleton, and a ready-to-run Unsloth Colab notebook. Hand these to the operator.

---

## Phase E — Evaluation & guardrails (do this alongside B/C, before trusting D)

### Task E1 — Persona eval harness
- **Goal:** A repeatable check that each specialized model still meets its skill-matrix Success Metric, so a persona/fine-tune change can't silently regress the firm.
- **Build** `scripts/eval_personas.py`: for each `ta-*` model, feed 3–5 canned prompts (drawn from the role's skill-matrix Drill) and assert the output contains the required structural elements (e.g. bear output must contain a blocker + an invalidation level; decider output must contain a capital cap + rejection reason).
- **Acceptance:** `python scripts/eval_personas.py` prints a pass/fail table; all personas pass their structural checks. Wire it as informational only — **do not** let it block trading.
- **Guardrail check:** re-run the existing suite to prove nothing else broke:
  ```powershell
  python -m pytest tests/test_model_validation.py tests/test_structured_agents.py -q
  ```
- **Commit (Phase E):**
  ```
  Add persona eval harness for specialized agent models

  Assert each ta-* model meets its skill-matrix success metric. Informational
  only; does not gate paper trading.
  ```

---

## 4. Order of operations (summary checklist)

- [x] A0 — inventory Ollama, choose & pull deep model
- [x] B1 — write persona Modelfiles from skill matrix
- [x] B2 — build `ta-*` models + rebuild script
- [x] B3 — wire role env vars in `.env`
- [ ] B4 — smoke-test one full run; confirm debate diverges
- [x] E1 — persona eval harness + regression tests → **commit Phases B+E**
- [x] C1 — audit existing grounding
- [x] C2 — inject strategy-library context where missing → commit Phase C
- [ ] D — **only on operator go-ahead**, distill + LoRA the 1–2 weakest roles

**Fastest path to value:** A0 → B1 → B2 → B3 → B4 delivers a fully specialized, differentiated agent roster with zero training and zero spend. Everything after is refinement.

---

## 5. Execution log (executor appends here)

<!-- Executor: after each task, append one line: date, task id, result, run_id/commit. -->
- 2026-07-29 — Integration — Refreshed the strategy library (e6d4bfb), merged Claude Track A and Codex Track B into `main` (52d2714), wired all 26 role overrides in the ignored `.env`, and hardened `.env` import order plus evaluator model unloading (72516f1).
- 2026-07-29 — Tests — Guarded config retained every `ta-*` role with zero fallbacks; targeted tests passed 15/15; full suite passed 264 tests plus 47 subtests.
- 2026-07-29 — E1 — Current installed personas pass all 27 informational structural cases: screener 3/3 (`finalcheck_20260729_164239.json`), analyst+synth+risk 9/9 (`reeval_20260729_163154.json`), quant+bull+bear 9/9 (`schema_20260729_164841.json`), decider+coach 6/6 (`final_dc_20260729_165311.json`).
- 2026-07-29 — B4 attempted — The combined graph built and all role models resolved, but NVDA propagation ran for about 34 minutes and ended without a run artifact or final decision. B4 remains open as a local-runtime performance issue; no order submission was enabled.
