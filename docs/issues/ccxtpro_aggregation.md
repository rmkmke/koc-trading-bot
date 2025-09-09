Title: Add ccxt.pro WebSocket Aggregation

Description:
Aggregate multiple exchange streams (e.g., Binance, KuCoin, Bitfinex) into a unified queue and display combined/selected feeds in the GUI chart. Add resilience for reconnects.

Acceptance Criteria:
- DataPipeline handles N streams concurrently
- GUI can select feeds or show average
- Reconnect logic with backoff and logging

Labels: enhancement, priority:medium

