# V5.9 Consolidated — Included Changes

This build merges the latest work into one V5.9 package.

## Merged into V5.9
- Compact/professional Streamlit UI
- Reduced main-table clutter
- Numeric RS Score in compact scanner
- Single execution RR in compact scanner
- Level-aware IDX tick-size engine (including boundary-crossing levels such as ERAA > Rp500)
- Quality-200 Tier A/B/C scanner universe and guardrails
- High-value pattern suite and SUPER SETUP
- News / narrative / rumor classification
- Intelligent support/resistance
- Supply & demand zones
- Confluence Entry engine
- Entry Timing / Execution engine

## Main decision hierarchy

1. Is the structure/setup good?
2. Is the stock strong relative to IHSG?
3. Is liquidity/risk acceptable?
4. Is there a high-quality pattern or confluence?
5. Where is demand/supply?
6. What is the best theoretical entry?
7. Is that entry actionable now?
8. Is there a verified catalyst or only rumor?

## Main scanner view

The compact table focuses on:
- Ticker
- Tier
- Scanner Score
- Pattern
- Execution
- Timing Score
- Buy Entry
- Entry Type
- RS Score
- Buy Entry RR
- Buy Stop
- TP2

Everything else remains available under detailed diagnostics.


## Auto IDX-IC Sector enhancement

V5.9 now removes the manual sector proxy input. Sector membership is loaded automatically from the IDX listed-company directory with local cache fallback. The scanner also calculates stock-vs-sector RS using an equal-weight proxy built from downloaded constituents in the same IDX-IC sector. The compact scanner exposes Combined RS while detailed results preserve Market RS and Sector RS separately.
