from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, Iterable, List, Sequence

import yfinance as yf

from tradingagents.dataflows.utils import safe_ticker_component


DEFAULT_NEWS_POLITICS_QUERIES = [
    "premarket stock movers news today earnings guidance",
    "stocks moving premarket analyst upgrades downgrades today",
    "market moving stock news today mergers FDA regulatory approval",
    "Federal Reserve inflation jobs report rates stocks today",
    "tariffs trade policy semiconductor stocks today",
    "geopolitics defense energy oil stocks today",
    "crypto regulation bitcoin stocks premarket",
    "US dollar forex currency market stocks today",
    "AI chips data center stocks earnings guidance",
    "healthcare FDA Medicare drug stocks clinical trial today",
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
    "halted",
    "guidance cut",
    "downgrade",
    "secondary offering",
    "registered direct",
    "dilution",
    "going concern",
    "delisting",
    "buyout",
    "acquisition agreement",
]


DAY_TRADE_CATALYST_RULES: Dict[str, Dict[str, Any]] = {
    "earnings_guidance": {
        "keywords": [
            "earnings",
            "revenue",
            "profit",
            "guidance",
            "outlook",
            "forecast",
            "preliminary results",
        ],
        "weight": 4,
    },
    "analyst_action": {
        "keywords": [
            "upgrade",
            "downgrade",
            "price target",
            "initiated",
            "raised to",
            "cut to",
        ],
        "weight": 3,
    },
    "merger_or_buyout": {
        "keywords": [
            "acquisition",
            "merger",
            "takeover",
            "buyout",
            "strategic alternatives",
        ],
        "weight": 2,
    },
    "regulatory_fda": {
        "keywords": [
            "fda",
            "approval",
            "clinical trial",
            "phase 2",
            "phase 3",
            "medicare",
            "regulatory",
        ],
        "weight": 4,
    },
    "macro_policy": {
        "keywords": [
            "federal reserve",
            "fed ",
            "cpi",
            "ppi",
            "jobs report",
            "inflation",
            "rate cut",
            "rate hike",
            "tariff",
            "sanction",
            "export control",
        ],
        "weight": 2,
    },
    "product_or_contract": {
        "keywords": [
            "launches",
            "unveils",
            "contract",
            "partnership",
            "wins order",
            "data center",
            "chip",
            "gpu",
        ],
        "weight": 3,
    },
    "commodity_fx_crypto": {
        "keywords": [
            "oil",
            "crude",
            "gold",
            "dollar",
            "yen",
            "euro",
            "forex",
            "bitcoin",
            "ethereum",
            "crypto",
        ],
        "weight": 2,
    },
}


BULLISH_KEYWORDS = [
    "beats",
    "beat estimates",
    "raises guidance",
    "upgrade",
    "approval",
    "wins",
    "surges",
    "rallies",
]


BEARISH_KEYWORDS = [
    "misses",
    "cuts guidance",
    "downgrade",
    "probe",
    "lawsuit",
    "falls",
    "slumps",
    "recall",
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


def _article_symbols(article: Dict[str, Any]) -> List[str]:
    symbols: List[str] = []
    for key in ("relatedTickers", "symbols", "tickers"):
        raw = article.get(key)
        if isinstance(raw, str):
            symbols.append(raw)
        elif isinstance(raw, Sequence):
            symbols.extend(str(item) for item in raw)
    content = article.get("content") if isinstance(article.get("content"), dict) else {}
    for key in ("relatedTickers", "symbols", "tickers"):
        raw = content.get(key)
        if isinstance(raw, str):
            symbols.append(raw)
        elif isinstance(raw, Sequence):
            symbols.extend(str(item) for item in raw)
    return _clean_symbols(symbols)


def _classify_day_trade_catalysts(lower_text: str) -> List[str]:
    tags: List[str] = []
    for tag, rule in DAY_TRADE_CATALYST_RULES.items():
        keywords = [str(item).lower() for item in rule.get("keywords", [])]
        if any(keyword in lower_text for keyword in keywords):
            tags.append(tag)
    return tags


def _catalyst_weight(tags: Sequence[str]) -> int:
    weights = [
        int(DAY_TRADE_CATALYST_RULES.get(tag, {}).get("weight", 1))
        for tag in tags
    ]
    return max(weights) if weights else 0


def _direction_label(lower_text: str) -> str:
    bullish = any(keyword in lower_text for keyword in BULLISH_KEYWORDS)
    bearish = any(keyword in lower_text for keyword in BEARISH_KEYWORDS)
    if bullish and bearish:
        return "mixed"
    if bullish:
        return "bullish"
    if bearish:
        return "bearish"
    return "unknown"


def _risk_tags(lower_text: str) -> List[str]:
    tags: List[str] = []
    for keyword in NEWS_RISK_KEYWORDS:
        if keyword in lower_text:
            normalized = keyword.replace(" ", "_")
            tags.append(normalized)
    return sorted(set(tags))


def _research_action(score: float, risk_tags: Sequence[str]) -> str:
    if risk_tags:
        return "risk_review"
    if score >= 8:
        return "priority_research"
    if score >= 4:
        return "confirm_at_open"
    return "watch"


def _build_thesis(
    symbol: str,
    *,
    score: float,
    catalysts: Sequence[str],
    themes: Sequence[str],
    direction: str,
    risk_tags: Sequence[str],
) -> str:
    pieces = []
    if catalysts:
        pieces.append(", ".join(sorted(set(catalysts))[:3]))
    if themes:
        pieces.append("themes: " + ", ".join(sorted(set(themes))[:2]))
    if not pieces:
        pieces.append("headline/theme interest")
    risk_text = f"; risks: {', '.join(sorted(set(risk_tags))[:3])}" if risk_tags else ""
    return (
        f"{symbol} pre-open research score {score:.1f}: "
        f"{'; '.join(pieces)}; direction {direction}{risk_text}."
    )


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
    catalyst_tags_by_symbol: Dict[str, List[str]] = defaultdict(list)
    themes_by_symbol: Dict[str, List[str]] = defaultdict(list)
    headlines_by_symbol: Dict[str, List[str]] = defaultdict(list)
    risk_headlines_by_symbol: Dict[str, List[str]] = defaultdict(list)
    risk_tags_by_symbol: Dict[str, List[str]] = defaultdict(list)
    directions_by_symbol: Dict[str, List[str]] = defaultdict(list)
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
            catalyst_tags = _classify_day_trade_catalysts(lower_text)
            catalyst_weight = _catalyst_weight(catalyst_tags)
            direction = _direction_label(lower_text)
            article_risk_tags = _risk_tags(lower_text)

            direct_symbols = sorted(
                set(_extract_direct_symbols(text, allowed_direct))
                | set(_article_symbols(article))
            )
            for symbol in direct_symbols:
                scores[symbol] += 4 + catalyst_weight
                catalysts_by_symbol[symbol].append("direct_headline_match")
                catalyst_tags_by_symbol[symbol].extend(catalyst_tags)
                directions_by_symbol[symbol].append(direction)
                risk_tags_by_symbol[symbol].extend(article_risk_tags)
                matched_symbols.add(symbol)

            for theme_name, theme in THEME_TICKERS.items():
                keywords = [str(item).lower() for item in theme.get("keywords", [])]
                if not any(keyword in lower_text for keyword in keywords):
                    continue
                for symbol in theme.get("tickers", []):
                    normalized = safe_ticker_component(str(symbol).upper())
                    if not normalized:
                        continue
                    scores[normalized] += 1 + min(catalyst_weight, 2)
                    catalysts_by_symbol[normalized].append("news_policy_theme")
                    catalyst_tags_by_symbol[normalized].extend(catalyst_tags)
                    themes_by_symbol[normalized].append(theme_name)
                    directions_by_symbol[normalized].append(direction)
                    risk_tags_by_symbol[normalized].extend(article_risk_tags)
                    matched_symbols.add(normalized)

            if not matched_symbols:
                continue

            is_risky = bool(article_risk_tags)
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
    day_trade_research_by_symbol: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        score = float(scores.get(symbol, 0.0))
        if score <= 0:
            continue
        catalyst_tags = sorted(set(catalyst_tags_by_symbol.get(symbol, [])))
        themes = sorted(set(themes_by_symbol.get(symbol, [])))
        risk_tags = sorted(set(risk_tags_by_symbol.get(symbol, [])))
        directions = [
            item
            for item in directions_by_symbol.get(symbol, [])
            if item and item != "unknown"
        ]
        direction = Counter(directions).most_common(1)[0][0] if directions else "unknown"
        action = _research_action(score, risk_tags)
        day_trade_research_by_symbol[symbol] = {
            "symbol": symbol,
            "score": round(score, 3),
            "action": action,
            "direction": direction,
            "catalyst_tags": catalyst_tags,
            "themes": themes,
            "risk_tags": risk_tags,
            "headlines": headlines_by_symbol.get(symbol, [])[:3],
            "thesis": _build_thesis(
                symbol,
                score=score,
                catalysts=catalyst_tags,
                themes=themes,
                direction=direction,
                risk_tags=risk_tags,
            ),
        }

    ranked_research_queue = sorted(
        day_trade_research_by_symbol.values(),
        key=lambda item: (-float(item["score"]), item["symbol"]),
    )

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
        "catalyst_tags_by_symbol": {
            symbol: sorted(set(values)) for symbol, values in catalyst_tags_by_symbol.items()
        },
        "themes_by_symbol": {
            symbol: sorted(set(values)) for symbol, values in themes_by_symbol.items()
        },
        "headlines_by_symbol": dict(headlines_by_symbol),
        "risk_headlines_by_symbol": dict(risk_headlines_by_symbol),
        "risk_tags_by_symbol": {
            symbol: sorted(set(values)) for symbol, values in risk_tags_by_symbol.items()
        },
        "directions_by_symbol": {
            symbol: Counter(
                item for item in values if item and item != "unknown"
            ).most_common(1)[0][0]
            if [item for item in values if item and item != "unknown"]
            else "unknown"
            for symbol, values in directions_by_symbol.items()
        },
        "day_trade_research_by_symbol": day_trade_research_by_symbol,
        "ranked_research_queue": ranked_research_queue,
        "errors": errors,
    }
