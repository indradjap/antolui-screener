# Antolui Screener V5.9 — Test Results

## New V5.9 timing engine
- `tests_timing.py`: **8/8 PASS**
  - demand retest -> BUY NOW
  - price above demand -> WAIT RETEST
  - price below pivot -> WAIT BREAKOUT
  - confirmed breakout -> BUY NOW
  - overextended price -> TOO EXTENDED
  - bearish structure -> AVOID
  - stop breached -> INVALIDATED
  - currently actionable breakout can supersede a better-but-distant theoretical retest

## Regression tests passed
- Technical regime engine: **7/7 PASS**
- Intelligent price-level engine: **PASS**
- Market context / RS engine: **5/5 PASS**
- Scanner scoring engine: **8/8 PASS**
- Tier guardrails: **7/7 PASS**
- IDX tick engine: **6/6 PASS**
- Legacy pattern engine: **6/6 PASS**
- V5.7 focused pattern engine: **8/8 PASS**
- News & narrative engine: **PASS**
- Python syntax / compile: **PASS**

## Environment note
The separate V5.8 end-to-end `tests_entry.py` imports the external `ta` package. That dependency is not installed in this build container, so that one integration test was not re-run here. The V5.9 timing layer itself is dependency-light and passed its dedicated 8-scenario suite; the source tree also compiles successfully.
