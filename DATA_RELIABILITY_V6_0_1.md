# Antolui V6.0.1 — Data Reliability Hotfix

- Robust Yahoo/yfinance retry path for single-stock analysis.
- Falls back from `yf.download()` to `Ticker.history()` when Yahoo returns an empty payload.
- Scanner retries failed batch symbols individually.
- Ignores transient NaN OHLC rows.
- User-facing data-provider errors no longer expose a full traceback.
- Recommended Streamlit Community Cloud runtime: Python 3.12.
