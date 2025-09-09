import pandas as pd

def to_dataframe(ohlcv, columns=("timestamp", "open", "high", "low", "close", "volume")):
    if not ohlcv:
        return pd.DataFrame(columns=[c for c in columns if c != "timestamp"]).astype(float)
    df = pd.DataFrame(ohlcv, columns=list(columns)[: len(ohlcv[0])])
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df.sort_index()

