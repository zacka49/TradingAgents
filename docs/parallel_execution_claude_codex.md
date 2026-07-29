# Parallel Execution Plan — Claude + Codex at the same time

**Goal:** Run Claude Code and Codex simultaneously on `docs/model_specialization_plan.md` to roughly double throughput, with **zero file collisions** and a single, simple rule for the one shared resource (your local Ollama).

**Companion doc:** `docs/model_specialization_plan.md` (the actual task detail). This doc only covers *how to run two agents in parallel*.

---

## 1. TL;DR — the split

Two independent tracks. They touch **disjoint files** and Track B needs neither Ollama nor Claude's output, so they can run fully in parallel.

| | **Track A → CLAUDE** ("Runtime & Personas") | **Track B → CODEX** ("Evals, Distillation kit & Grounding") |
| --- | --- | --- |
| Owns | Ollama runtime, model building, wiring, pipeline runs | Pure file/code authoring — no Ollama, no pipeline runs |
| Plan tasks | A0, B1, B2, B3, B4 | E1 (harness code), C1, C2, Phase-D prep kit |
| Writes files | `ollama/modelfiles/**`, `scripts/build_persona_models.ps1`, repo-root `.env` | `scripts/eval_personas.py`, `scripts/extract_role_inputs.py`, `docs/distillation/**`, `notebooks/finetune_role_lora.ipynb`, `tradingagents/agents/**` (C2), `tests/test_grounding_*.py` |
| Needs the deep-model choice? | Yes (picks it in A0) | **No** (distillation data is base-model-agnostic) |
| Runs Ollama inference? | Yes | No (only after merge, if at all) |

**Only cross-track dependency:** none during parallel work. Integration (running Codex's eval harness against Claude's models) happens **after** both branches merge — see §5.

---

## 2. One-time setup: two worktrees, two venvs (operator runs this)

Do this once, before starting either agent. Worktrees give each agent its own working directory + branch (no git index fights); separate venvs avoid the `pip install -e .` path clash noted in the repo history.

```powershell
# From the main repo root. Commit the plan docs first so both worktrees inherit them.
git add docs/model_specialization_plan.md docs/parallel_execution_claude_codex.md
git commit -m "Add model specialization + parallel execution plans"

# Create two worktrees on their own branches, as SIBLING folders (not nested in the repo).
git worktree add ../TA-claude  -b spec/track-a-personas
git worktree add ../TA-codex   -b spec/track-b-evals

# Give each its own venv + editable install so imports resolve to that worktree.
# NOTE: the bare `python` on this machine is a stale 3.7 Store shim; the project
# needs >=3.10. Pin to 3.13 (what the main .venv uses) via the py launcher.
# Fresh venvs have no deps yet, so this is a FULL editable install (not --no-deps).
cd ../TA-claude; py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e .
cd ../TA-codex;  py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e .
```

- Run **Claude Code in `../TA-claude`** and **Codex in `../TA-codex`**, each in its own terminal.
- Copy your working `.env` (Alpaca keys etc.) into **both** worktree roots — `.env` is git-ignored, so it won't merge and won't leak. (`cp ../TradingAgents/.env ./.env` from each worktree.)
- Ollama is a machine-level daemon, so **both worktrees see the same models** — that's exactly what we want: Claude builds the `ta-*` models, they immediately exist for Codex/integration.

> If you'd rather not use worktrees: run both agents in the **same** folder but enforce the file-ownership table in §1 strictly, and expect messier git history. Worktrees are strongly recommended.

---

## 3. The coordination contract (both agents obey)

Three rules, that's it:

1. **Stay in your lane.** Only create/edit the files in your track's row (§1). Never edit the other track's files. If you think you need one, stop and tell the operator.
2. **Ollama is single-owner = Track A (Claude).** Only Claude runs `ollama create`, `ollama pull`, `ollama run`, or the trading pipeline during parallel work. Codex must not invoke Ollama or run the pipeline — it only *writes* code/notebooks/docs. (Codex's eval harness gets executed later, at integration.)
3. **No shared-file logging.** Do **not** edit `docs/model_specialization_plan.md`'s execution log during parallel work (it would conflict). Record progress in **commit messages** on your own branch.

Readiness signal (no message-passing needed): Codex's later eval run depends on the `ta-*` models existing. That's an observable shared fact — `ollama list`. Integration proceeds once `ollama list` shows the personas.

---

## 4. Kickoff prompts (copy-paste)

### 4a. Paste into CLAUDE (running in `../TA-claude`)

```
You are Track A ("Runtime & Personas") in a two-agent parallel effort. Codex is
running Track B in a separate worktree at the same time. Read
docs/parallel_execution_claude_codex.md for the rules, then execute
docs/model_specialization_plan.md tasks A0, B1, B2, B3, B4 IN ORDER.

Strict boundaries:
- Only create/edit: ollama/modelfiles/**, scripts/build_persona_models.ps1, and
  the repo-root .env. Do NOT touch scripts/eval_personas.py,
  scripts/extract_role_inputs.py, docs/distillation/**, notebooks/**,
  tradingagents/agents/**, or tests/** — those belong to Codex.
- You are the ONLY agent allowed to run ollama or the trading pipeline.
- Do NOT edit the execution log in the specialization plan; record progress in
  commit messages on branch spec/track-a-personas.
- Keep it local-only and paper-only: never set TRADINGAGENTS_ALLOW_ONLINE_LLM,
  never touch order-submission gates or risk caps.

Run each task's Acceptance check before moving on. Author every ta-* Modelfile
SYSTEM prompt from the matching role rows in docs/agent_skill_training_matrix.md.
At A0, pick the deep model the machine can actually run and record the choice as
a comment at the top of .env. Commit after B4 with the Phase B message from the
plan. Then STOP and report the run_id + the deep-model you chose.
```

### 4b. Paste into CODEX (running in `../TA-codex`)

```
You are Track B ("Evals, Distillation kit & Grounding") in a two-agent parallel
effort. Claude is running Track A (Ollama model building) in a separate worktree
at the same time. Read docs/parallel_execution_claude_codex.md for the rules,
then execute docs/model_specialization_plan.md tasks E1, C1, C2, and the Phase D
prep deliverables.

Strict boundaries:
- Only create/edit: scripts/eval_personas.py, scripts/extract_role_inputs.py,
  docs/distillation/** (dataset-generation prompt templates per role),
  notebooks/finetune_role_lora.ipynb (an Unsloth LoRA notebook),
  tradingagents/agents/** (only the C2 grounding injection) and a new
  tests/test_grounding_*.py. Do NOT touch ollama/**,
  scripts/build_persona_models.ps1, .env, or default_config.py.
- Do NOT run ollama or the trading pipeline — Claude owns the runtime. Write the
  eval harness so it CAN run later, but do not execute model inference now.
- You do NOT need the deep-model choice: distillation datasets are base-model-
  agnostic; parameterize the notebook's base model as a variable.
- Do NOT edit the execution log in the specialization plan; record progress in
  commit messages on branch spec/track-b-evals.

For E1, drive the harness off docs/agent_skill_training_matrix.md success metrics
(structural assertions per role). For C1, produce the read-only grounding audit
note. For C2, reuse the existing memory/injection helper rather than adding a
vector DB (that needs operator sign-off). You may run `pytest` on your own new
tests only. Commit per phase; then STOP and report which roles you prepared
distillation kits for.
```

---

## 5. Integration (after both agents STOP)

Run by the operator (or hand to Claude in `../TA-claude`, which owns runtime):

```powershell
# From the main repo root:
git checkout main
git merge spec/track-a-personas   # Claude's models/wiring — disjoint files
git merge spec/track-b-evals      # Codex's evals/grounding — disjoint files, clean merge
```

Then, in one place (Claude's worktree or a fresh venv on main), run the deferred cross-track steps that need both halves:

1. **B4 re-run** on the merged tree — one full pipeline run; confirm no model-not-found and the debate diverges. Record run_id.
2. **E1 run** — `python scripts/eval_personas.py` against the now-built `ta-*` models; all personas pass their skill-matrix structural checks.
3. **C2 tests** — `python -m pytest tests/test_grounding_*.py tests/test_structured_agents.py -q`.
4. Append a single consolidated entry to the specialization plan's **Execution log** now that parallel work is over.
5. Commit the merge result. Optionally `git worktree remove ../TA-claude` and `../TA-codex`.

**⏸ OPERATOR DECISION — Phase D (fine-tuning):** Codex only prepared the *kit* (datagen prompts + extraction script + Colab notebook). Actually generating data (in Claude/ChatGPT chat) and running the LoRA (on free Colab/Kaggle) is a manual, operator-driven step. Decide then whether any role's weakness justifies it.

---

## 6. Collision map (why this is safe)

| Shared thing | Risk | Mitigation |
| --- | --- | --- |
| Files | Both edit same file | Disjoint ownership table (§1); separate worktrees/branches |
| Git index | Concurrent commits | One branch per worktree; merge at end (disjoint files → clean) |
| `pip install -e .` path | Imports resolve to wrong tree | Per-worktree venv (§2) |
| Ollama daemon/GPU | Two heavy jobs thrash | Rule 2: only Claude runs inference during parallel phase |
| Plan doc exec log | Append conflict | Rule 3: log via commit messages; one consolidated entry at integration |
| Deep-model choice | Track B blocked on Track A | Track B is base-model-agnostic — no dependency |

---

## 7. If something goes wrong

- **A `ta-*` role shows a fallback in the guarded-config check (B3):** the model wasn't `ollama create`d — Claude re-runs B2. Not a Codex problem.
- **Merge conflict:** means someone left their lane. Inspect the conflicting path against §1, revert the out-of-lane edit, re-merge.
- **Both jobs slow:** an inference job overlapped. Serialize — only one Ollama job at a time on this PC.
- **Codex needs a model to test:** it shouldn't during parallel work; defer that assertion to integration (§5).
