from datetime import UTC, datetime

import pandas as pd

from tradingagents.company.news_reversion_desk import (
    NewsCatalyst,
    evaluate_news_reversion_event,
    run_news_reversion_event_study,
)


def _history(closes):
    dates = pd.to_datetime(list(closes.keys()))
    return pd.DataFrame({"Close": list(closes.values())}, index=dates)


def test_news_reversion_event_detects_upside_fade():
    catalyst = NewsCatalyst(
        ticker="AAA",
        headline="AAA rallies on product news",
        publisher="TestWire",
        published_at=datetime(2026, 1, 6, 15, 0, tzinfo=UTC),
    )
    history = _history(
        {
            "2026-01-05": 100.0,
            "2026-01-06": 110.0,
            "2026-01-07": 103.0,
        }
    )

    event = evaluate_news_reversion_event(catalyst, history=history)

    assert event is not None
    assert event.event_move_pct == 10.0
    assert event.fade_return_pct == 6.364
    assert event.reversion_capture_pct == 70.0
    assert event.reverted_by_1d is True


def test_news_reversion_event_detects_downside_fade():
    catalyst = NewsCatalyst(
        ticker="BBB",
        headline="BBB drops after guidance cut",
        publisher="TestWire",
        published_at=datetime(2026, 1, 6, 15, 0, tzinfo=UTC),
    )
    history = _history(
        {
            "2026-01-05": 100.0,
            "2026-01-06": 90.0,
            "2026-01-07": 97.0,
        }
    )

    event = evaluate_news_reversion_event(catalyst, history=history)

    assert event is not None
    assert event.event_move_pct == -10.0
    assert event.fade_return_pct == 7.778
    assert event.reversion_capture_pct == 70.0
    assert event.reverted_by_1d is True


def test_news_after_cash_close_shifts_to_next_trading_session():
    catalyst = NewsCatalyst(
        ticker="CCC",
        headline="CCC reports after close",
        publisher="TestWire",
        published_at=datetime(2026, 1, 5, 22, 0, tzinfo=UTC),
    )
    history = _history(
        {
            "2026-01-05": 100.0,
            "2026-01-06": 108.0,
            "2026-01-07": 105.0,
        }
    )

    event = evaluate_news_reversion_event(catalyst, history=history)

    assert event is not None
    assert event.before_session == "2026-01-05"
    assert event.event_session == "2026-01-06"
    assert event.one_day_after_session == "2026-01-07"


def test_news_reversion_event_study_summarizes_supplied_data():
    news = {
        "AAA": [
            NewsCatalyst(
                ticker="AAA",
                headline="AAA rallies on product news",
                publisher="TestWire",
                published_at=datetime(2026, 1, 6, 15, 0, tzinfo=UTC),
            )
        ],
        "BBB": [
            NewsCatalyst(
                ticker="BBB",
                headline="BBB holds flat after update",
                publisher="TestWire",
                published_at=datetime(2026, 1, 6, 15, 0, tzinfo=UTC),
            )
        ],
    }
    histories = {
        "AAA": _history({"2026-01-05": 100.0, "2026-01-06": 110.0, "2026-01-07": 103.0}),
        "BBB": _history({"2026-01-05": 100.0, "2026-01-06": 100.4, "2026-01-07": 100.2}),
    }

    report = run_news_reversion_event_study(
        universe=["AAA", "BBB"],
        news_by_symbol=news,
        history_by_symbol=histories,
        lookback_days=10,
        now=datetime(2026, 1, 8, tzinfo=UTC),
    )

    assert report.event_count == 2
    assert report.eligible_event_count == 1
    assert report.reverted_event_count == 1
    assert report.avg_fade_return_pct == 6.364
    assert report.verdict == "insufficient_sample"
