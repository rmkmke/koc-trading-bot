# Grok's K.O.C. mini demo

This repository contains a minimal proof of concept demonstrating
ccxt.pro WebSocket aggregation and a matplotlib-based mini-chart.

## Usage

```
python -m pip install -r requirements.txt
python -m src.main
```

The example streams ``BTC/USDT`` candles from multiple exchanges and
renders their close prices in a small chart.
