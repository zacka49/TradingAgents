from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, Iterable, List, Sequence

import yfinance as yf

from tradingagents.dataflows.utils import safe_ticker_component


DEFAULT_NEWS_POLITICS_QUERIES = [
    "market moving stock news today",
    "Federal Reserve inflation rates stocks",
    "tariffs trade policy semiconductor stocks",
    "geopolitics defense energy stocks",
    "crypto regulation bitcoin stocks",
    "US dollar forex currency market stocks",
    "AI chips data center stocks",
    "healthcare FDA Medicare drug stocks",
]


THEME_TICKERS: Dict[str, Dict[str, Any]] = {
    "rates_inflation": {
        "keywords": [
            "federal reserve",
            "fed ",
            "rate cut",
            "rate hike",
            "inflation",
            "cpi",
            "ppi",
            "yields",
            "treasury",
        ],
        "tickers": ["SPY", "QQQ", "IWM", "TLT", "GLD", "XLF", "JPM", "BAC", "GS"],
    },
    "trade_tariffs_china": {
        "keywords": [
            "tariff",
            "export control",
            "china",
            "taiwan",
            "sanction",
            "trade policy",
        ],
        "tickers": ["AAPL", "NVDA", "AMD", "AVGO", "INTC", "TSM", "MU", "SMH", "SOXX"],
    },
    "defense_geopolitics": {
        "keywords": [
            "war",
            "missile",
            "defense",
            "nato",
            "ukraine",
            "middle east",
            "geopolitical",
        ],
        "tickers": ["LMT", "NOC", "RTX", "GD", "BA", "ITA", "XLE", "USO", "GLD"],
    },
    "energy_policy": {
        "keywords": [
            "oil",
            "opec",
            "energy policy",
            "drilling",
            "pipeline",
            "natural gas",
            "crude",
        ],
        "tickers": ["XOM", "CVX", "OXY", "SLB", "COP", "XLE", "USO"],
    },
    "crypto_regulation": {
        "keywords": [
            "bitcoin",
            "crypto",
            "ethereum",
            "stablecoin",
            "sec crypto",
            "digital asset",
        ],
        "tickers": ["COIN", "MSTR", "HOOD", "IBIT", "GBTC", "BITO"],
    },
    "ai_chips_datacenter": {
        "keywords": [
            "artificial intelligence",
            " ai ",
            "chip",
            "semiconductor",
            "data center",
            "datacenter",
            "gpu",
            "memory chip",
        ],
        "tickers": ["NVDA", "AMD", "AVGO", "ARM", "SMCI", "MU", "TSM", "ORCL", "MSFT"],
    },
    "healthcare_policy": {
        "keywords": [
            "fda",
            "medicare",
            "drug price",
            "clinical trial",
            "obesity drug",
            "vaccine",
            "healthcare policy",
        ],
        "tickers": ["LLY", "NVO", "UNH", "PFE", "MRNA", "XLV"],
    },
    "bank_regulation": {
        "keywords": [
            "bank regulation",
            "capital rule",
            "basel",
            "commercial real estate",
            "bank earnings",
        ],
        "tickers": ["JPM", "BAC", "GS", "MS", "C", "XLF", "KRE"],
    },
    "election_fiscal_policy": {
        "keywords": [
            "election",
            "government shutdown",
            "debt ceiling",
            "budget bill",
            "tax policy",
            "congress",
            "white house",
        ],
        "tickers": ["SPY", "QQQ", "IWM", "TLT", "GLD", "ITA", "XLE", "XLF"],
    },
    "currency_fx_macro": {
        "keywords": [
            "dollar",
            "currency",
            "forex",
            "fx market",
            "euro",
            "yen",
            "sterling",
            "pound",
            "canadian dollar",
            "australian dollar",
        ],
        "tickers": ["UUP", "FXE", "FXY", "FXB", "FXA", "FXC", "GLD", "TLT", "SPY"],
    },
}


NEWS_RISK_KEYWORDS = [
    "investigation",
    "probe",
    "lawsuit",
    "fraud",
    "sec charges",
    "doj",
    "bankruptcy",
    "recall",
    "trading halt",
    "guidance cut",
    "downgrade",
]

_SEARCH_CACHE_TTL = timedelta(minutes=5)
_SEARCH_NEWS_CACHE: Dict[tuple[str, int], tuple[datetime, List[Dict[str, Any]]]] = {}


def _clean_symbols(symbols: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for item in symbols:
        ticker = safe_ticker_component(str(item).strip().upper())
        if ticker and ticker not in seen:
            seen.add(ticker)
            cleaned.append(ticker)
    return cleaned


def _theme_universe() -> set[str]:
    symbols: set[str] = set()
    for theme in THEME_TICKERS.values():
        symbols.update(theme.get("tickers", []))
    return symbols


def _article_text(article: Dict[str, Any]) -> Dict[str, str]:
    content = article.get("content") if isinstance(article.get("content"), dict) else {}
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
    title = str(content.get("title") or article.get("title") or "").strip()
    summary = str(content.get("summary") or article.get("summary") or "").strip()
    publisher = str(
        provider.get("displayName") or article.get("publisher") or "unknown"
    ).strip()
    return {
        "title": title,
        "summary": summary,
        "publisher": publisher,
        "text": f"{title} {summary}".strip(),
    }


def _fetch_search_news(query: str, limit: int) -> List[Dict[str, Any]]:
    cache_key = (query, max(1, limit))
    now = datetime.now(timezone.utc)
    cached = _SEARCH_NEWS_CACHE.get(cache_key)
    if cached and now - cached[0] <= _SEARCH_CACHE_TTL:
        return list(cached[1])

    search = yf.Search(
        query=query,
        news_count=max(1, limit),
        enable_fuzzy_query=True,
    )
    news = getattr(search, "news", []) or []
    items = [item for item in news if isinstance(item, dict)]
    _SEARCH_NEWS_CACHE[cache_key] = (now, items)
    return list(items)


def _extract_direct_symbols(text: str, allowed_symbols: set[str]) -> List[str]:
    matches = []
    for symbol in allowed_symbols:
        pattern = rf"(?<![A-Z0-9])\$?{re.escape(symbol)}(?![A-Z0-9])"
        if re.search(pattern, text.upper()):
            matches.append(symbol)
    return sorted(matches)


def discover_news_politics_symbols(
    base_universe: Sequence[str],
    *,
    queries: Sequence[str] | None = None,
    max_symbols: int = 60,
    articles_per_query: int = 8,
) -> Dict[str, Any]:
    """Expand a scan universe using market-moving news and policy themes.

    The function intentionally maps news themes to liquid, configurable ticker
    baskets instead of treating headlines as direct trade signals. Price,
    liquidity, spread, strategy confidence, and risk gates still decide whether
    anything can be traded.
    """
    base = _clean_symbols(base_universe)
    query_list = [str(item).strip() for item in (queries or DEFAULT_NEWS_POLITICS_QUERIES) if str(item).strip()]
    max_symbols = max(len(base), max(1, int(max_symbols)))
    articles_per_query = max(1, int(articles_per_query))

    allowed_direct = set(base) | _theme_universe()
    scores: Counter[str] = Counter()
    catalysts_by_symbol: Dict[str, List[str]] = defaultdict(list)
    themes_by_symbol: Dict[str, List[str]] = defaultdict(list)
    headlines_by_symbol: Dict[str, List[str]] = defaultdict(list)
    risk_headlines_by_symbol: Dict[str, List[str]] = defaultdict(list)
    errors: List[str] = []
    seen_headlines: set[str] = set()
    article_count = 0

    for query in query_list:
        try:
            articles = _fetch_search_news(query, articles_per_query)
        except Exception as exc:
            errors.append(f"{query}: {type(exc).__name__}: {exc}")
            continue

        for article in articles:
            extracted = _article_text(article)
            title = extracted["title"]
            if not title or title in seen_headlines:
                continue
            seen_headlines.add(title)
            article_count += 1

            text = extracted["text"]
            lower_text = f" {text.lower()} "
            headline = f"{title} ({extracted['publisher']})"
            matched_symbols: set[str] = set()

            direct_symbols = _extract_direct_symbols(text, allowed_direct)
            for symbol in direct_symbols:
                scores[symbol] += 4
                catalysts_by_symbol[symbol].append("direct_headline_match")
                matched_symbols.add(symbol)

            for theme_name, theme in THEME_TICKERS.items():
                keywords = [str(item).lower() for item in theme.get("keywords", [])]
                if not any(keyword in lower_text for keyword in keywords):
                    continue
                for symbol in theme.get("tickers", []):
                    normalized = safe_ticker_component(str(symbol).upper())
                    if not normalized:
                        continue
                    scores[normalized] += 1
                    catalysts_by_symbol[normalized].append("news_policy_theme")
                    themes_by_symbol[normalized].append(theme_name)
                    matched_symbols.add(normalized)

            if not matched_symbols:
                continue

            is_risky = any(keyword in lower_text for keyword in NEWS_RISK_KEYWORDS)
            for symbol in matched_symbols:
                if len(headlines_by_symbol[symbol]) < 3:
                    headlines_by_symbol[symbol].append(headline)
                if is_risky and len(risk_headlines_by_symbol[symbol]) < 3:
                    risk_headlines_by_symbol[symbol].append(headline)

    ranked_additions = [
        symbol
        for symbol, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if symbol not in set(base)
    ]
    symbols = _clean_symbols([*base, *ranked_additions])[:max_symbols]

    return {
        "symbols": symbols,
        "base_symbols": base,
        "added_symbols": [symbol for symbol in symbols if symbol not in set(base)],
        "queries": query_list,
        "article_count": article_count,
        "scores": dict(scores),
        "catalysts_by_symbol": {
            symbol: sorted(set(values)) for symbol, values in catalysts_by_symbol.items()
        },
        "themes_by_symbol": {
            symbol: sorted(set(values)) for symbol, values in themes_by_symbol.items()
        },
        "headlines_by_symbol": dict(headlines_by_symbol),
        "risk_headlines_by_symbol": dict(risk_headlines_by_symbol),
        "errors": errors,
    }
