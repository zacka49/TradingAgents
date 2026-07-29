# Optional Role Distillation Kit

This kit prepares—but does not authorize—Phase D of the model-specialization plan. Actual dataset generation and LoRA training require the operator decision described in `docs/model_specialization_plan.md`. Fine-tuning should be attempted only after persona and grounding evaluations identify a persistent, role-specific weakness.

Prepared candidate roles:

| Role | Why it is a candidate | Gold-answer template |
| --- | --- | --- |
| Strategy Researcher | Formatting and evidence discipline directly affect whether ideas become testable. | `strategy_researcher_datagen_prompt.md` |
| Risk Office Guardian | Missing a correlation, staleness, or size blocker is high impact. | `risk_office_guardian_datagen_prompt.md` |
| Chief Investment Officer | Capital/desk-cap synthesis may benefit from higher-quality demonstrations. | `chief_investment_officer_datagen_prompt.md` |

## Workflow

1. Run `scripts/extract_role_inputs.py --role <role> --results-dir results --dry-run`.
2. Extract at most 500 skeletons to `docs/distillation/datasets/<role>_skeleton.jsonl`.
3. Review and redact every input. Saved-state inputs are reconstructed from the upstream report fields available to that role; raw prompts were not persisted.
4. Use the matching data-generation template in Claude Pro or ChatGPT Plus. Generate diverse gold answers in batches, keeping exactly one JSON object per line.
5. Human-review every answer. Reject invented prices, missing blockers, unauthorized order language, and any answer that changes a strategy’s recorded promotion status.
6. Keep 10–20% of examples as a held-out test set. Deduplicate by ticker/date/scenario, not merely exact text.
7. Upload the reviewed JSONL to `notebooks/finetune_role_lora.ipynb` in Colab/Kaggle. Set `BASE_MODEL` and `ROLE_NAME` explicitly.
8. Export Q4_K_M GGUF, register it under a new `ta-*-ft` Ollama name, and A/B test against the persona-only model with `scripts/eval_personas.py`.
9. Keep the fine-tune only if it wins the held-out, skill-matrix evaluation without weakening risk language.

## Data Rules

- Target 200–500 reviewed examples for one role; do not mix roles in one adapter.
- Keep generated datasets and GGUF files out of Git. The local `datasets/` and `exports/` paths are ignored.
- Use conversational JSONL with `system`, `user`, and non-empty `assistant` messages.
- Do not train on blank skeletons, existing weak baseline outputs, secrets, live credentials, broker responses, or future/downstream reports unavailable to the role.
- Do not teach research agents that they can approve or submit orders.
- Prefer direct, auditable answers. Private chain-of-thought is neither requested nor required.

## Validation Gates

- Dataset validator in the notebook reports zero blank assistants and exactly one role.
- Held-out examples are never passed to the trainer.
- Persona eval results improve or remain equal, especially all risk/blocker checks.
- Manual review confirms exact strategy IDs and promotion status are preserved.
- Fine-tuned model remains local-only and paper-only.

Current implementation references were checked against the official Unsloth Qwen3 and GGUF documentation and Hugging Face TRL conversational/prompt-completion dataset documentation on 2026-07-29.
