import csv
import json

from tradingagents.company.strategy_research_department import (
    build_strategy_research_report,
    strategy_decision_for_name,
    strategy_status_allows_paper_trade,
    write_strategy_library,
)


def test_default_strategy_research_report_allows_promoted_paper_strategies():
    report = build_strategy_research_report()

    assert "opening_range_breakout_15m" in report.approved_strategy_ids
    assert "momentum_breakout" in report.approved_strategy_ids
    assert "relative_strength_continuation" in report.paper_candidate_strategy_ids
    assert strategy_decision_for_name(report, "news_reversion_event_study").decision == "research_only"
    assert strategy_status_allows_paper_trade("paper_trade_candidate") is True
    assert strategy_status_allows_paper_trade("paper_watchlist") is False


def test_strategy_research_promotes_and_demotes_from_evidence(tmp_path):
    evidence = tmp_path / "results" / "run"
    evidence.mkdir(parents=True)
    with (evidence / "strategy_aggregate.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "strategy",
                "trades",
                "avg_win_rate_pct",
                "avg_total_return_pct",
                "avg_profit_factor",
                "avg_max_drawdown_pct",
                "avg_score",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "strategy": "opening_range_breakout_15m",
                "trades": "120",
                "avg_win_rate_pct": "52",
                "avg_total_return_pct": "4.5",
                "avg_profit_factor": "1.3",
                "avg_max_drawdown_pct": "3.5",
                "avg_score": "12",
            }
        )
        writer.writerow(
            {
                "strategy": "vwap_reclaim",
                "trades": "80",
                "avg_win_rate_pct": "42",
                "avg_total_return_pct": "-1",
                "avg_profit_factor": "0.8",
                "avg_max_drawdown_pct": "4",
                "avg_score": "1",
            }
        )
    (evidence / "news_reversion_event_study.json").write_text(
        json.dumps(
            {
                "eligible_event_count": 8,
                "win_rate_pct": 30,
                "avg_fade_return_pct": -2.0,
                "avg_reversion_capture_pct": -50,
            }
        ),
        encoding="utf-8",
    )

    report = build_strategy_research_report(evidence_root=tmp_path / "results")

    assert strategy_decision_for_name(report, "opening_range_breakout_15m").promotion_status == "approved_paper_strategy"
    assert strategy_decision_for_name(report, "vwap_reclaim").promotion_status == "retired"
    assert strategy_decision_for_name(report, "news_reversion_event_study").decision == "research_only"


def test_strategy_library_writer_outputs_machine_readable_artifacts(tmp_path):
    report = build_strategy_research_report()
    paths = write_strategy_library(report, output_dir=tmp_path / "library")

    assert set(paths) == {"report_json", "report_markdown", "approved", "research", "retired"}
    payload = json.loads((tmp_path / "library" / "strategy_research_report.json").read_text(encoding="utf-8"))
    assert payload["approved_strategy_ids"]
    assert (tmp_path / "library" / "strategy_research_report.md").exists()
