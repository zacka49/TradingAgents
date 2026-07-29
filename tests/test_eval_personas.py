from scripts import eval_personas


def test_run_cases_unloads_at_persona_boundaries(monkeypatch):
    first_model_cases = tuple(
        case for case in eval_personas.CASES if case.model == "ta-screener:latest"
    )[:2]
    next_model_case = next(
        case for case in eval_personas.CASES if case.model == "ta-analyst:latest"
    )
    cases = (*first_model_cases, next_model_case)
    calls = []

    def fake_generate(**kwargs):
        calls.append((kwargs["model"], kwargs["keep_alive"]))
        return ""

    monkeypatch.setattr(eval_personas, "_generate", fake_generate)

    results = eval_personas.run_cases(
        cases,
        base_url="http://localhost:11434",
        timeout_seconds=1,
    )

    assert len(results) == 3
    assert calls == [
        ("ta-screener:latest", "5m"),
        ("ta-screener:latest", 0),
        ("ta-analyst:latest", 0),
    ]