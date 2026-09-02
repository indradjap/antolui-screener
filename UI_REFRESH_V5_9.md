# Antolui Screener V5.9 — UI Refresh

This refresh is focused on Streamlit Cloud readability and faster decision-making. Trading logic, scanner scoring, pattern detection, sector logic, tick rounding, entry timing, and TP/SL calculations are unchanged.

## What changed
- Forced dark navy styling in app CSS, so the UI remains readable even if `.streamlit/config.toml` is missing or Streamlit Cloud opens with a light theme.
- Shorter header: `ANTOLUI SCREENER — IDX Technical & Entry Intelligence`.
- Single Stock input focuses on ticker; benchmark moved into a collapsed `Analysis settings` section.
- Replaced the six equal-weight decision cards with one decision hero: ticker, price, execution status, pattern, Score, Timing, Market RS, and RR.
- Added a dedicated Entry Plan strip with Buy Zone, Ideal Entry, Stop, TP1, and TP2.
- Replaced 12 Pattern/Context cards with two compact information panels.
- Simplified tabs to `Overview`, `Chart`, `Levels & Entry`, and `News`.
- Advanced diagnostics moved into a collapsed Diagnostics expander.
- Chart now has an explicit dark background for Streamlit Cloud consistency.
- Added responsive CSS for narrower screens.

## Deployment note
Keep `.streamlit/config.toml` in the GitHub repository, but the main UI no longer depends on it for basic contrast/readability.
