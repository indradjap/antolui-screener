# Antolui Screener V6.1 — Refined Analyst Intelligence

## Reliability
- Yahoo retrieval keeps two independent paths (`yf.download` and `Ticker.history`) with retry/backoff.
- Universe download uses a conservative non-threaded batch mode plus per-ticker recovery.
- A valid newer listing is no longer rejected simply because it has fewer than 220 bars; 80+ raw bars are accepted and marked `LIMITED` history.
- Single Stock remains usable if IHSG is temporarily unavailable; market context becomes explicitly `DEGRADED` instead of aborting the whole analysis.
- Scanner can fall back to an equal-weight proxy built from the downloaded scan universe if the official benchmark is temporarily unavailable.
- Full traceback is hidden from normal UI; technical details remain available in an expander.
- Dependency ranges are constrained to reduce surprise changes between redeploys.

## Analyst Intelligence
- Added `SUPPORT REVERSAL`: structural support + reversal candle + oversold Stoch RSI.
- Added candlestick state: Spinning Bottom, Hammer, Bullish Engulfing.
- Added open-gap detection and gap-fill objective.
- Added `BASE FORMATION`: tight short consolidation near structural support.
- Added psychological round-level confluence.
- Added HRTA and PIPA to research memory; outcome fields remain unresolved and therefore do not affect learning yet.

## Guardrails
- New setup families still use the independent Antolui Edge layer.
- Learning remains inactive until a setup has at least 10 resolved outcomes.
- No claim of superior accuracy is made until forward outcomes support it.
