Title: Extend Order Routing and Rate Limits

Description:
Implement full order execution paths in APIManager for supported venues and parse rate limit headers for KuCoin/Bitfinex. Warn on high latency (>500ms).

Acceptance Criteria:
- execute_order covers market/limit for supported venues
- KuCoin/Bitfinex rate limit tracking
- Latency benchmark harness and logs

Labels: enhancement, priority:medium

