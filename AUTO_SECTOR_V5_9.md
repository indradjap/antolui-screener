# Antolui Screener V5.9 — Automatic IDX-IC Sector Context

## What changed

The manual **Sector proxy (optional)** input has been removed from Single Stock.
Antolui Screener now resolves the ticker's sector automatically from the IDX listed-company directory and maps it to the official IDX-IC sector/index name.

Examples:

- ERAA → Consumer Cyclicals → IDXCYCLIC
- BBCA → Financials → IDXFINANCE
- ANTM → Basic Materials → IDXBASIC

## Data flow

1. Try the official IDX listed-company directory (`ListedCompany/GetCompanyProfiles`).
2. Cache a successful directory locally, so the app does not repeatedly hit IDX.
3. If IDX is temporarily unavailable, reuse the last successful cache.
4. For Single Stock only, Yahoo metadata is a last-resort classification fallback and is clearly labelled as such.

The IDX directory cache is reused for up to 24 hours. Streamlit also caches the lookup to reduce repeated requests.

## Single Stock

The input strip is now only:

- Ticker
- Benchmark (default `^JKSE`)
- Analyze

The result automatically shows:

- IDX-IC sector
- official sector-index code
- source of the classification
- RS vs IHSG
- RS vs Sector (when historical sector-index data can be resolved from the existing Yahoo/yfinance feed)
- Sector Regime

If the official sector name is detected but the historical sector-index series is not available from the current price provider, Antolui Screener does **not** invent data. It keeps sector classification visible and leaves sector RS unavailable.

## Scanner

For a large scan, Antolui Screener avoids making a separate sector-index network request for every stock. It:

1. maps all downloaded tickers to IDX-IC sectors,
2. groups downloaded stocks by sector,
3. builds an **equal-weight sector proxy** from the successfully downloaded stocks in each sector,
4. uses that proxy for sector regime and stock-vs-sector relative strength.

This scanner proxy uses official IDX-IC membership but is **not the official IDX sector-index weighting methodology**.

## Relative Strength

V5.9 now preserves two independent RS measurements:

- **Market RS** = stock vs IHSG
- **Sector RS** = stock vs its IDX-IC sector proxy/index

For scanner ranking, when sector RS is available:

`Combined RS = 60% Market RS + 40% Sector RS`

The original Market RS remains available separately, so existing timing/decision logic keeps its previous meaning.

## UI additions

Scanner:

- Sector column
- Sector filter
- Combined RS shown as the compact `RS` value
- Detailed columns: Market RS, Sector RS, Sector Strength, Sector Regime, sector source/index

Single Stock:

- no manual sector field
- automatic IDX-IC sector caption
- RS vs IHSG and RS vs Sector shown separately

## Failure behaviour

Sector data is additive. A sector-data failure must never prevent technical analysis, entry levels, or scanner execution. If sector data is unavailable, Antolui Screener falls back to market-only context and clearly reports the missing sector context.
