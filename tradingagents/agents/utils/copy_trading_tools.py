from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import Annotated, Any

import pandas as pd
import requests
import yfinance as yf
from langchain_core.tools import tool

from tradingagents.dataflows.stockstats_utils import yf_retry


SENATE_TRADES_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/"
    "aggregate/all_transactions.json"
)
HOUSE_TRADES_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/"
    "data/all_transactions.json"
)
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def _fetch_json(url: str, timeout: int = 15) -> Any:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _fetch_sec_json(url: str, timeout: int = 15) -> Any:
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise RuntimeError(
            "SEC_USER_AGENT is not set. Set it to a descriptive app/company "
            "name and contact email before calling SEC EDGAR."
        )
    response = requests.get(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov" if "data.sec.gov" in url else "www.sec.gov",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _trade_ticker(trade: dict[str, Any]) -> str:
    for key in ("ticker", "symbol"):
        value = trade.get(key)
        if value:
            return str(value).strip().upper()
    return ""


def _trade_person(trade: dict[str, Any], chamber: str) -> str:
    if trade.get("representative"):
        return str(trade["representative"])
    if trade.get("senator"):
        return str(trade["senator"])
    first = str(trade.get("first_name", "")).strip()
    last = str(trade.get("last_name", "")).strip()
    name = " ".join(part for part in (first, last) if part)
    return name or chamber


def _table_cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def _normalise_trade(trade: dict[str, Any], chamber: str) -> dict[str, str]:
    return {
        "chamber": chamber,
        "person": _trade_person(trade, chamber),
        "ticker": _trade_ticker(trade),
        "transaction_date": str(
            trade.get("transaction_date")
            or trade.get("transactionDate")
            or trade.get("transaction_date_formatted")
            or ""
        ),
        "disclosure_date": str(
            trade.get("disclosure_date")
            or trade.get("date_recieved")
            or trade.get("date_received")
            or trade.get("filing_date")
            or ""
        ),
        "type": str(
            trade.get("type")
            or trade.get("transaction_type")
            or trade.get("transaction")
            or ""
        ),
        "amount": str(trade.get("amount") or trade.get("value") or ""),
        "asset": str(trade.get("asset_description") or trade.get("asset") or ""),
    }


def _filter_trades(
    trades: list[dict[str, Any]],
    ticker: str,
    chamber: str,
    cutoff: datetime,
) -> list[dict[str, str]]:
    ticker = ticker.upper()
    matches = []
    for trade in trades:
        normalised = _normalise_trade(trade, chamber)
        if normalised["ticker"] != ticker:
            continue

        trade_date = _parse_date(normalised["transaction_date"])
        disclosure_date = _parse_date(normalised["disclosure_date"])
        relevant_date = trade_date or disclosure_date
        if relevant_date and relevant_date < cutoff:
            continue
        matches.append(normalised)
    return matches


def _render_trades_table(trades: list[dict[str, str]], ticker: str, limit: int) -> str:
    if not trades:
        return (
            f"No matching congressional trade rows were found for {ticker} "
            "inside the requested lookback window."
        )

    def sort_key(row: dict[str, str]) -> datetime:
        return (
            _parse_date(row.get("disclosure_date"))
            or _parse_date(row.get("transaction_date"))
            or datetime.min
        )

    rows = sorted(trades, key=sort_key, reverse=True)[:limit]
    lines = [
        "| Chamber | Person | Type | Amount | Transaction Date | Disclosure Date | Asset |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {chamber} | {person} | {type} | {amount} | {transaction_date} | "
            "{disclosure_date} | {asset} |".format(
                **{key: _table_cell(value) for key, value in row.items()}
            )
        )
    return "\n".join(lines)


def _lookup_cik(ticker: str) -> str | None:
    payload = _fetch_sec_json(SEC_TICKERS_URL)
    target = ticker.strip().upper()
    for entry in payload.values():
        if str(entry.get("ticker", "")).upper() == target:
            return str(entry.get("cik_str", "")).zfill(10)
    return None


@tool
def get_sec_disclosure_filings(
    ticker: Annotated[str, "Ticker symbol"],
    form_types: Annotated[
        str,
        "Comma-separated SEC forms to include, e.g. '4,SC 13D,SC 13G,13F-HR'",
    ] = "4,SC 13D,SC 13G,13F-HR",
    limit: Annotated[int, "Maximum filings to return"] = 20,
) -> str:
    """Return recent SEC disclosure filings for a ticker.

    This official EDGAR path is best for Form 4 insider activity and
    beneficial-ownership disclosures such as Schedule 13D/13G. It is not a
    complete reverse 13F holder search for every famous investor.
    """
    ticker = ticker.strip().upper()
    wanted = {form.strip().upper() for form in form_types.split(",") if form.strip()}
    try:
        cik = _lookup_cik(ticker)
        if not cik:
            return f"No SEC CIK mapping found for ticker {ticker}."
        submissions = _fetch_sec_json(SEC_SUBMISSIONS_URL.format(cik=cik))
    except Exception as exc:
        return f"Error retrieving SEC filings for {ticker}: {exc}"

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    rows = []
    for idx, form in enumerate(forms):
        if wanted and str(form).upper() not in wanted:
            continue
        accession = accessions[idx] if idx < len(accessions) else ""
        document = primary_docs[idx] if idx < len(primary_docs) else ""
        accession_path = accession.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession_path}/{document}"
            if accession and document
            else ""
        )
        rows.append(
            {
                "form": str(form),
                "filing_date": filing_dates[idx] if idx < len(filing_dates) else "",
                "report_date": report_dates[idx] if idx < len(report_dates) else "",
                "description": descriptions[idx] if idx < len(descriptions) else "",
                "url": url,
            }
        )
        if len(rows) >= limit:
            break

    if not rows:
        return f"No recent SEC filings matched forms {form_types} for {ticker}."

    lines = [
        f"# SEC disclosure filings for {ticker}",
        f"CIK: {cik}",
        "| Form | Filing Date | Report Date | Description | URL |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {form} | {filing_date} | {report_date} | {description} | {url} |".format(
                **{key: _table_cell(value) for key, value in row.items()}
            )
        )
    return "\n".join(lines)


@tool
def get_congressional_trades(
    ticker: Annotated[str, "Ticker symbol to search for"],
    look_back_days: Annotated[int, "How many days of disclosures to inspect"] = 365,
    limit: Annotated[int, "Maximum rows to return"] = 20,
) -> str:
    """Search public House and Senate stock-trade disclosure datasets for a ticker.

    These community datasets mirror public STOCK Act disclosures. They can lag
    official filings and one chamber can be unavailable, so the report includes
    source status instead of failing the whole agent.
    """
    cutoff = datetime.utcnow() - timedelta(days=max(1, look_back_days))
    ticker = ticker.strip().upper()
    all_matches: list[dict[str, str]] = []
    source_notes: list[str] = []

    for chamber, url in (("Senate", SENATE_TRADES_URL), ("House", HOUSE_TRADES_URL)):
        try:
            payload = _fetch_json(url)
            if not isinstance(payload, list):
                source_notes.append(f"{chamber}: unexpected payload shape")
                continue
            matches = _filter_trades(payload, ticker, chamber, cutoff)
            all_matches.extend(matches)
            source_notes.append(f"{chamber}: {len(matches)} matching rows")
        except Exception as exc:
            source_notes.append(f"{chamber}: unavailable ({exc})")

    return "\n\n".join(
        [
            f"# Congressional trade disclosures for {ticker}",
            f"Lookback days: {look_back_days}",
            "Source status: " + "; ".join(source_notes),
            _render_trades_table(all_matches, ticker, limit),
        ]
    )


def _safe_dataframe_to_markdown(data: Any, limit: int) -> str:
    if data is None:
        return "No data returned."
    if isinstance(data, pd.DataFrame):
        if data.empty:
            return "No rows returned."
        frame = data.head(limit).fillna("")
        columns = [str(col) for col in frame.columns]
        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join(["---"] * len(columns)) + " |",
        ]
        for _, row in frame.iterrows():
            values = [_table_cell(row[col]) for col in frame.columns]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)
    return str(data)


@tool
def get_institutional_holders(
    ticker: Annotated[str, "Ticker symbol"],
    limit: Annotated[int, "Maximum rows to return"] = 20,
) -> str:
    """Return large holder snapshots from yfinance for copy-trading context."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        institutional = yf_retry(lambda: ticker_obj.institutional_holders)
        mutual_funds = yf_retry(lambda: ticker_obj.mutualfund_holders)
        major_holders = yf_retry(lambda: ticker_obj.major_holders)
    except Exception as exc:
        return f"Error retrieving holder data for {ticker}: {exc}"

    sections = [
        f"# Public holder snapshot for {ticker.upper()}",
        "## Major Holders",
        _safe_dataframe_to_markdown(major_holders, limit),
        "## Institutional Holders",
        _safe_dataframe_to_markdown(institutional, limit),
        "## Mutual Fund Holders",
        _safe_dataframe_to_markdown(mutual_funds, limit),
    ]
    return "\n\n".join(sections)
