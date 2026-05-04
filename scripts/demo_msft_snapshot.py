from tradingagents.dataflows.y_finance import (
    get_YFin_data_online,
    get_fundamentals,
    get_stock_stats_indicators_window,
)


def print_section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def main() -> None:
    symbol = "MSFT"
    trade_date = "2026-04-24"
    start_date = "2026-04-13"
    end_date = "2026-04-25"

    print("TradingAgents fresh data-flow demo")
    print(f"Symbol: {symbol}")
    print(f"Trade date: {trade_date}")

    print_section("Recent Price Data")
    price_lines = get_YFin_data_online(symbol, start_date, end_date).splitlines()
    print("\n".join(price_lines[:16]))

    for indicator in ("close_50_sma", "rsi", "macd"):
        print_section(indicator)
        indicator_lines = get_stock_stats_indicators_window(
            symbol,
            indicator,
            trade_date,
            5,
        ).splitlines()
        print("\n".join(indicator_lines[:12]))

    print_section("Fundamentals Excerpt")
    fundamentals_lines = get_fundamentals(symbol, trade_date).splitlines()
    print("\n".join(fundamentals_lines[:24]))


if __name__ == "__main__":
    main()
