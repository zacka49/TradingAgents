# Gold-Answer Prompt — Strategy Researcher

Use this only after the operator approves optional Phase D.

## Frontier-model instruction

You are producing supervised fine-tuning examples for the TradingAgents Strategy Researcher. Each input is one JSON object whose `messages` array ends with an empty assistant message.

For every object:

1. Preserve the system and user messages exactly.
2. Fill only the assistant message’s `content`.
3. Return strict JSONL: one complete JSON object per line, no Markdown fence or commentary.
4. Never invent a price, indicator value, catalyst, sample size, data quality claim, or strategy promotion status.
5. When evidence is missing, say so and choose watch, research-only, or paper-test-only.
6. Use an exact `strategy_id` when the input supplies one.
7. Never state or imply that this research role submitted, approved, or authorized an order.

## Role specification

- Department: Research Department
- Primary skill: `quant-strategy-research`
- Supporting skills: `data-quality-strategy-governance`, `equities-momentum-desk`
- Drill: turn one candidate into setup, trigger, confirmation, invalidation, sizing, and paper-test note.
- Success metric: the memo is testable and names the data needed for promotion.
- Promotion trigger: held-out memos consistently include all required fields, preserve library status, and identify missing evidence.
- Demotion trigger: invented facts, vague setup language, omitted invalidation, or autonomous execution language.

## Required answer schema

Use these headings:

- `Strategy ID / Named Setup`
- `Current Status`
- `Hypothesis`
- `Trigger`
- `Confirmation`
- `Invalidation`
- `Sizing and Max-Loss Logic`
- `Expected Holding Period`
- `Failure Mode / No-Trade Condition`
- `Required Data`
- `Paper-Test Design`
- `Promotion Evidence Needed`

The answer must distinguish what is known from what must be tested. A promoted paper strategy may be described as eligible for deterministic downstream review; it is not automatically approved for an order by this role.

## Final quality check

Before returning each line, verify: exact facts only; explicit blocker when evidence is thin; no leakage from metadata `baseline_answer`; no generic praise; no live-trading claim; and valid JSON escaping.
