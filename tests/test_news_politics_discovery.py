from tradingagents.dataflows import news_politics_discovery


def test_news_politics_discovery_adds_theme_tickers(monkeypatch):
    articles = [
        {
            "content": {
                "title": "Federal Reserve rate cut hopes lift bank stocks",
                "summary": "Yields fell as traders repriced inflation risk.",
                "provider": {"displayName": "TestWire"},
            }
        },
        {
            "content": {
                "title": "AI chip export controls put NVDA and AMD in focus",
                "summary": "New trade policy could affect semiconductor demand and earnings guidance.",
                "provider": {"displayName": "PolicyDesk"},
            }
        },
    ]

    monkeypatch.setattr(
        news_politics_discovery,
        "_fetch_search_news",
        lambda query, limit: articles,
    )

    result = news_politics_discovery.discover_news_politics_symbols(
        ["SPY"],
        queries=["policy test"],
        max_symbols=20,
        articles_per_query=2,
    )

    assert "JPM" in result["symbols"]
    assert "NVDA" in result["symbols"]
    assert "AMD" in result["symbols"]
    assert "rates_inflation" in result["themes_by_symbol"]["JPM"]
    assert "ai_chips_datacenter" in result["themes_by_symbol"]["NVDA"]
    assert result["scores"]["NVDA"] >= 4
    assert "macro_policy" in result["catalyst_tags_by_symbol"]["NVDA"]
    assert result["day_trade_research_by_symbol"]["NVDA"]["action"] in {
        "priority_research",
        "confirm_at_open",
    }
    assert result["ranked_research_queue"][0]["score"] >= result["ranked_research_queue"][-1]["score"]


def test_news_politics_discovery_marks_risk_review(monkeypatch):
    articles = [
        {
            "relatedTickers": ["XYZ"],
            "content": {
                "title": "XYZ surges after FDA approval but announces secondary offering",
                "summary": "The stock is active premarket after regulatory news and dilution risk.",
                "provider": {"displayName": "TestWire"},
            },
        }
    ]

    monkeypatch.setattr(
        news_politics_discovery,
        "_fetch_search_news",
        lambda query, limit: articles,
    )

    result = news_politics_discovery.discover_news_politics_symbols(
        ["SPY"],
        queries=["risk test"],
        max_symbols=10,
    )

    assert "XYZ" in result["symbols"]
    assert result["day_trade_research_by_symbol"]["XYZ"]["action"] == "risk_review"
    assert "secondary_offering" in result["risk_tags_by_symbol"]["XYZ"]


def test_news_politics_discovery_falls_back_to_base_on_empty_news(monkeypatch):
    monkeypatch.setattr(
        news_politics_discovery,
        "_fetch_search_news",
        lambda query, limit: [],
    )

    result = news_politics_discovery.discover_news_politics_symbols(
        ["QQQ", "SPY"],
        queries=["empty"],
        max_symbols=10,
    )

    assert result["symbols"] == ["QQQ", "SPY"]
    assert result["added_symbols"] == []
