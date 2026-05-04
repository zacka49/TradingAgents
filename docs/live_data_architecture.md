# Live Data Architecture (Alpaca + TradingView)

This project should use Alpaca as the primary live data source and TradingView as an alert/event source.

## What should provide what

1. **Live prices and bars**: Alpaca Market Data API  
2. **Latest quotes/trades**: Alpaca Market Data API  
3. **News feed**: Alpaca Market Data API (news endpoint)  
4. **Chart/indicator alerts**: TradingView webhooks to local receiver

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
