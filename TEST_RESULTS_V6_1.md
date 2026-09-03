# Antolui Screener V6.1 — Test Results

## Passed locally
- Python compile: PASS (all `.py` files)
- Analyst Intelligence regression: 5/5 PASS
- Analyst learning safeguards: 2/2 PASS
- Quick Pick regression: 5/5 PASS
- New V6.1 analyst archetypes: 3/3 PASS
  - Support Reversal / HRTA-style candidate
  - Base Formation / PIPA-style candidate
  - Open-gap target detection
- IDX Tick Engine: 6/6 PASS
- Pattern Engine: 6/6 PASS
- Advanced Pattern Engine: 8/8 PASS
- Market Context: 5/5 PASS
- Tier Guardrails: 7/7 PASS
- Execution Timing: 8/8 PASS
- Scanner scoring: 8/8 PASS
- Technical Engine: 7/7 PASS

## Not claimed as tested in this build environment
- Live Yahoo Finance retrieval: not executed (no outbound/live provider dependency available here)
- Streamlit browser smoke test: not executed (`streamlit`, `yfinance`, `ta`, and `curl_cffi` are not installed in this build runtime)

V6.1 therefore has regression coverage for deterministic logic and static compilation, but live provider behavior must be verified after Streamlit deployment.
