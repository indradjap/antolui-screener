# Quick Pick Build Test Results

Build: Antolui Screener V5.9 + Quick Pick

## Passed in build environment

- Python compile: PASS for all `.py` files
- Quick Pick synthetic regression: **5/5 PASS**
  - pivot breakout / DEWA-style archetype
  - MA20 reclaim / CDIA-style archetype
  - base retest / PTRO-style archetype
  - overextended rejection
- IDX tick engine: **6/6 PASS**
- Legacy pattern engine: **6/6 PASS**
- V5.7 pattern engine: **8/8 PASS**
- Market context: **5/5 PASS**
- Tier guardrails: **7/7 PASS**
- Technical engine: **7/7 PASS**
- Execution timing engine: **8/8 PASS**

## Environment limitation

The build container does not have the packages in `requirements.txt` installed and cannot access PyPI, so Streamlit/browser smoke testing and tests that import `ta`/`yfinance` were not rerun here. Streamlit Cloud installs those packages from `requirements.txt` during deployment. No claim is made that a live browser render was tested in this container.
