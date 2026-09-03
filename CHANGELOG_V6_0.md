# V6.0 Changelog — Analyst Intelligence

- Upgraded Quick Pick from one universal scoring recipe to **setup-adaptive scoring**.
- Added dedicated logic for **Support Hold Rebound**, **Pullback Pivot Hold**, and **Trendline Support Rebound** alongside Pivot Breakout, Resistance Breakout, MA20 Reclaim, and Base Retest.
- Added setup-specific use of volume, MACD state, Stoch RSI, pullback quality, rejection behavior, and trendline quality.
- Added explicit **EARLY / TRIGGER / RETEST** entry styles.
- Added separate **Analyst Score**, **Edge Score**, and **Conviction Score**.
- Added independent Antolui validation using RS, market/sector context, trend quality, timing, RR, location, and supply headroom.
- Added conviction caps for bearish structure, poor RR, overextension, and nearby supply.
- Added research memory `analyst_pick_history.csv`, seeded with six supplied examples (DEWA, AMMN, CDIA, PTRO, BUVA, MBMA).
- Added outcome-based Bayesian learning guardrails in `analyst_learning.py`; frequency of picks alone never changes scoring.
- Added Analyst Intelligence to **Single Stock** analysis and made it the primary reasoning layer for **Quick Pick** scanner ranking.
- Scanner export renamed to `antolui_screener_v6_0_scanner_results.csv`.
- App version bumped to **6.0**.
