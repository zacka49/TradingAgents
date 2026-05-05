# Live Data Architecture (Alpaca + TradingView)

This project should use Alpaca as the primary live data source and TradingView as an alert/event source.

## What should provide what

1. **Live prices and bars**: Alpaca Market Data API  
2. **Latest quotes/trades**: Alpaca Market Data API  
3. **News feed**: Alpaca Market Data API (news endpoint)  
4. **Chart/indicator alerts**: TradingView webhooks to local receiver
5. **Order-flow features**: derived locally from Alpaca trades and quotes
   - recent tick prints / time and sales
   - top-of-book bid/ask, spread, and quote imbalance
   - volume-at-price profile, point of control, and value area
   - footprint-style buy/sell delta and large prints
   - simple absorption flags when aggressive flow fails to move price

## Order-flow depth roadmap

The first implementation uses Alpaca L1 trades and quotes because those fit the
current authenticated data stack. That covers the most useful low-cost features
from the "$1 vs $1,000 Trading Charts" video: volume profile, large prints,
delta, and absorption.

True liquidity heatmaps need order-book depth, not just latest quote data. Add a
depth provider when you want that final layer:

- **Databento MBP-10** for top-10 level market-by-price depth.
- **Databento MBO** for full order-by-order L3 data.
- **Polygon trades/quotes/second aggregates** as a practical real-time middle
  tier where plan coverage fits.

The current tool reports `l2_heatmap_available=false` so agents know not to
pretend they have passive liquidity walls until a depth feed is configured.

## Why this split

- TradingView is excellent for charting and alert logic.
- TradingView webhooks are the officially supported automation bridge.
- Alpaca provides authenticated market data endpoints and websocket streams for programmatic consumption.

## Setup checklist

1. Set these env vars in `.env`:
   - `APCA_API_KEY_ID`
   - `APCA_API_SECRET_KEY`
   - `APCA_API_BASE_URL=https://paper-api.alpaca.markets`
   - `ALPACA_STOCK_FEED=iex` (or `sip` if your plan supports it)
   - `ORDER_FLOW_LARGE_TRADE_MIN_SIZE=1000` (optional)
   - `TRADINGVIEW_WEBHOOK_SECRET=<random-shared-secret>`

2. Use preflight checker before strategy runs:
   - `scripts/check_live_data_stack.py`

3. Run TradingView webhook intake service when needed:
   - `scripts/tradingview_webhook_receiver.py`

4. In TradingView alert UI:
   - Enable webhook URL
   - URL should target your receiver endpoint (local tunnel if remote delivery needed)
   - Include `secret` field in alert JSON body matching `TRADINGVIEW_WEBHOOK_SECRET`

## Example TradingView alert JSON body

```json
{
  "secret": "replace-with-your-secret",
  "symbol": "{{ticker}}",
  "exchange": "{{exchange}}",
  "interval": "{{interval}}",
  "close": "{{close}}",
  "volume": "{{volume}}",
  "time": "{{time}}",
  "strategy_action": "{{strategy.order.action}}",
  "strategy_contracts": "{{strategy.order.contracts}}",
  "message": "Breakout condition fired"
}
```

## Notes on plans and limitations

- Alpaca Basic plan provides IEX real-time for equities and has symbol/subscription limits.
- Full consolidated US exchange feed typically requires paid plan tiers.
- If an endpoint returns authorization/subscription errors, keep trading API keys the same but adjust your market-data feed (`iex` vs `sip`) and subscription tier.
