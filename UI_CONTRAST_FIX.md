# Antolui Screener V5.9 — Streamlit Cloud Contrast Fix

This patch fixes low-contrast/invisible option text observed on Streamlit Community Cloud.

Changes:
- Forces readable text for widget labels.
- Forces readable radio and checkbox option text.
- Forces dark expander headers instead of white Streamlit Cloud strips.
- Keeps inactive tab labels readable.
- Preserves the existing dark Antolui theme and trading logic.

Regression tests executed after the UI-only patch:
- IDX tick engine: 6/6 PASS
- V5.7 pattern engine: 8/8 PASS
- Market context: 5/5 PASS
- Scanner engine: 8/8 PASS
- Python compile: PASS
