import yfinance as yf
import pandas as pd


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if ticker.startswith("^") or ticker.endswith(".JK") or "=" in ticker:
        return ticker
    return ticker + ".JK"


def load_symbol(symbol: str, period: str = "2y", add_jk_suffix: bool = True):
    symbol = symbol.strip().upper()
    if add_jk_suffix:
        symbol = normalize_ticker(symbol)

    df = yf.download(
        symbol,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"Data {symbol} tidak ditemukan.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if len(df) < 220:
        raise ValueError(f"{symbol}: minimal sekitar 220 bar data diperlukan.")

    return symbol, df


def load_stock(ticker: str, period: str = "2y"):
    return load_symbol(ticker, period=period, add_jk_suffix=True)


def load_benchmark(symbol: str = "^JKSE", period: str = "2y"):
    return load_symbol(symbol, period=period, add_jk_suffix=False)


def download_universe(tickers, period: str = "2y", chunk_size: int = 60):
    """Batch-download many IDX symbols efficiently.

    Returns (frames, errors), where frames maps normalized Yahoo symbols to OHLCV frames.
    The scanner can therefore download hundreds of symbols in chunks instead of one HTTP
    request per stock.
    """
    symbols = []
    seen = set()
    for t in tickers:
        s = normalize_ticker(str(t))
        if s not in seen:
            symbols.append(s)
            seen.add(s)

    frames = {}
    errors = {}
    required = ["Open", "High", "Low", "Close", "Volume"]

    for start in range(0, len(symbols), max(int(chunk_size), 1)):
        chunk = symbols[start:start + max(int(chunk_size), 1)]
        try:
            raw = yf.download(
                tickers=chunk,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
            )
        except Exception as e:
            for s in chunk:
                errors[s] = f"batch download error: {e}"
            continue

        if raw is None or raw.empty:
            for s in chunk:
                errors[s] = "empty download"
            continue

        for s in chunk:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    lvl0 = set(map(str, raw.columns.get_level_values(0)))
                    lvl1 = set(map(str, raw.columns.get_level_values(1)))
                    if s in lvl1:
                        df = raw.xs(s, axis=1, level=1).copy()
                    elif s in lvl0:
                        df = raw.xs(s, axis=1, level=0).copy()
                    elif len(chunk) == 1:
                        df = raw.copy()
                        df.columns = df.columns.get_level_values(0)
                    else:
                        raise KeyError("symbol not present in batch response")
                else:
                    if len(chunk) != 1:
                        raise KeyError("unexpected non-MultiIndex batch response")
                    df = raw.copy()

                missing = [c for c in required if c not in df.columns]
                if missing:
                    raise ValueError(f"missing columns {missing}")
                df = df[required].dropna(how="any")
                df = df[df["Close"] > 0]
                if len(df) < 220:
                    raise ValueError(f"only {len(df)} bars")
                frames[s] = df
            except Exception as e:
                errors[s] = str(e)

    return frames, errors
