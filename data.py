import time
import yfinance as yf
import pandas as pd


REQUIRED_OHLCV = ["Open", "High", "Low", "Close", "Volume"]
MIN_USABLE_BARS = 80
FULL_HISTORY_BARS = 220


class MarketDataError(ValueError):
    """Market-data retrieval failed after all provider paths were attempted."""


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if ticker.startswith("^") or ticker.endswith(".JK") or "=" in ticker:
        return ticker
    return ticker + ".JK"


def _clean_download(df, symbol: str):
    if df is None or getattr(df, "empty", True):
        return None

    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = set(map(str, df.columns.get_level_values(0)))
        lvl1 = set(map(str, df.columns.get_level_values(1)))
        if symbol in lvl1:
            df = df.xs(symbol, axis=1, level=1).copy()
        elif symbol in lvl0:
            df = df.xs(symbol, axis=1, level=0).copy()
        else:
            df.columns = df.columns.get_level_values(0)

    missing = [c for c in REQUIRED_OHLCV if c not in df.columns]
    if missing:
        return None

    df = df[REQUIRED_OHLCV].copy()
    for c in REQUIRED_OHLCV:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["Close"] > 0) & (df["High"] > 0) & (df["Low"] > 0)]
    df["Volume"] = df["Volume"].fillna(0)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df if not df.empty else None


def _mark_meta(df: pd.DataFrame, *, symbol: str, provider: str, attempt: int, requested_period: str):
    out = df.copy()
    out.attrs["antolui_symbol"] = symbol
    out.attrs["antolui_provider"] = provider
    out.attrs["antolui_provider_attempt"] = int(attempt)
    out.attrs["antolui_requested_period"] = requested_period
    out.attrs["antolui_bars"] = int(len(out))
    out.attrs["antolui_history_quality"] = "FULL" if len(out) >= FULL_HISTORY_BARS else "LIMITED"
    return out


def data_health(df: pd.DataFrame | None) -> dict:
    if df is None:
        return {"provider": "N/A", "bars": 0, "history_quality": "UNAVAILABLE"}
    return {
        "provider": df.attrs.get("antolui_provider", "Yahoo Finance"),
        "bars": int(df.attrs.get("antolui_bars", len(df))),
        "history_quality": df.attrs.get("antolui_history_quality", "FULL" if len(df) >= FULL_HISTORY_BARS else "LIMITED"),
        "attempt": df.attrs.get("antolui_provider_attempt"),
    }


def _download_via_download(symbol: str, period: str):
    return yf.download(
        symbol,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
        timeout=15,
    )


def _download_via_history(symbol: str, period: str):
    return yf.Ticker(symbol).history(
        period=period,
        interval="1d",
        auto_adjust=False,
        actions=False,
        repair=False,
        timeout=15,
    )


def load_symbol(symbol: str, period: str = "2y", add_jk_suffix: bool = True):
    symbol = symbol.strip().upper()
    if add_jk_suffix:
        symbol = normalize_ticker(symbol)

    errors = []
    methods = (("yf.download", _download_via_download), ("Ticker.history", _download_via_history))
    for method_name, method in methods:
        for attempt in range(1, 4):
            try:
                raw = method(symbol, period)
                df = _clean_download(raw, symbol)
                if df is not None and len(df) >= MIN_USABLE_BARS:
                    return symbol, _mark_meta(df, symbol=symbol, provider=method_name, attempt=attempt, requested_period=period)
                if df is None:
                    errors.append(f"{method_name} #{attempt}: empty response")
                else:
                    errors.append(f"{method_name} #{attempt}: only {len(df)} bars")
            except Exception as exc:
                errors.append(f"{method_name} #{attempt}: {type(exc).__name__}: {exc}")
            if attempt < 3:
                time.sleep(0.7 * attempt)

    detail = " | ".join(errors[-6:])
    raise MarketDataError(
        f"Data {symbol} sementara tidak dapat diambil dengan history yang cukup. "
        f"Ini belum tentu berarti ticker salah/delisted. Coba lagi beberapa saat. Detail: {detail}"
    )


def load_stock(ticker: str, period: str = "2y"):
    return load_symbol(ticker, period=period, add_jk_suffix=True)


def load_benchmark(symbol: str = "^JKSE", period: str = "2y"):
    return load_symbol(symbol, period=period, add_jk_suffix=False)


def download_universe(tickers, period: str = "2y", chunk_size: int = 60):
    """Batch-download IDX symbols with a conservative cloud-safe recovery pass."""
    symbols, seen = [], set()
    for t in tickers:
        s = normalize_ticker(str(t))
        if s not in seen:
            symbols.append(s); seen.add(s)

    frames, errors = {}, {}
    chunk_size = max(int(chunk_size), 1)

    for start in range(0, len(symbols), chunk_size):
        chunk = symbols[start:start + chunk_size]
        raw, batch_error = None, None
        for attempt in range(1, 3):
            try:
                # threads=False is intentionally more conservative on shared cloud IPs.
                raw = yf.download(
                    tickers=chunk,
                    period=period,
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                    group_by="column",
                    timeout=20,
                )
                if raw is not None and not raw.empty:
                    break
                batch_error = "empty batch response"
            except Exception as exc:
                batch_error = f"{type(exc).__name__}: {exc}"
            if attempt == 1:
                time.sleep(0.8)

        if raw is not None and not raw.empty:
            for s in chunk:
                try:
                    candidate = None
                    if isinstance(raw.columns, pd.MultiIndex):
                        lvl0 = set(map(str, raw.columns.get_level_values(0)))
                        lvl1 = set(map(str, raw.columns.get_level_values(1)))
                        if s in lvl1:
                            candidate = raw.xs(s, axis=1, level=1).copy()
                        elif s in lvl0:
                            candidate = raw.xs(s, axis=1, level=0).copy()
                        elif len(chunk) == 1:
                            candidate = raw.copy(); candidate.columns = candidate.columns.get_level_values(0)
                    elif len(chunk) == 1:
                        candidate = raw.copy()

                    df = _clean_download(candidate, s) if candidate is not None else None
                    if df is not None and len(df) >= MIN_USABLE_BARS:
                        frames[s] = _mark_meta(df, symbol=s, provider="yf.download batch", attempt=1, requested_period=period)
                    else:
                        errors[s] = "missing/insufficient data in batch response"
                except Exception as exc:
                    errors[s] = str(exc)
        else:
            for s in chunk:
                errors[s] = f"batch download error: {batch_error}"

    # Individual recovery is deliberately independent of the batch result.
    for s in [x for x in symbols if x not in frames]:
        try:
            _, df = load_symbol(s, period=period, add_jk_suffix=False)
            frames[s] = df
            errors.pop(s, None)
        except Exception as exc:
            errors[s] = str(exc)

    return frames, errors
