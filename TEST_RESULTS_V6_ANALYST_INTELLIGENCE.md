# Antolui Screener V6.0 — Analyst Intelligence Test Results

Build target: Quick Pick V6 setup-adaptive analyst reasoning + independent Antolui Edge layer.

## Tests executed in the build environment

- Analyst Intelligence archetypes: **5/5 PASS**
  - DEWA-style pivot breakout / volume-driven reasoning
  - AMMN-style structural support-hold rebound
  - BUVA-style pullback pivot hold after a resistance test
  - rising trendline support detector / MBMA-style candidate path
  - poor-RR conviction cap / eligibility veto
- Analyst learning safeguards: **2/2 PASS**
  - selection frequency alone cannot create a learned edge adjustment
  - outcome calibration activates only after sufficient resolved examples
- Quick Pick V5 regression archetypes: **5/5 PASS**
- IDX tick engine: **6/6 PASS**
- Advanced pattern engine: **8/8 PASS**
- Market context: **5/5 PASS**
- Tier guardrails: **7/7 PASS**
- Execution Timing engine: **8/8 PASS**
- Python compilation for all `.py` files: **PASS**

## Environment limitation

The build environment does not currently have `ta`, `streamlit`, or `yfinance` installed, so a live Streamlit browser smoke test and tests that execute the full download/indicator stack were not run here. Those dependencies remain in `requirements.txt` for Streamlit Cloud installation.

No claim of superior forecasting accuracy is made from these unit/regression tests. Forward comparison against the analyst picks is the validation target.
