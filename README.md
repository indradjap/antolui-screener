# Antolui Screener V5.9 — Consolidated Build

V5.9 is the single consolidated build of Antolui Screener. It combines the latest technical, pattern, execution, market-context, news, and UI changes in one package.

## V5.9 Auto IDX-IC Sector

The consolidated V5.9 build now auto-detects sector classification from the IDX listed-company directory. The manual sector input was removed. Single Stock shows the detected IDX-IC sector/index automatically; Scanner groups downloaded names by IDX-IC sector and builds a cached equal-weight sector proxy for sector regime and stock-vs-sector RS. When available, scanner ranking uses 60% Market RS + 40% Sector RS. See `AUTO_SECTOR_V5_9.md`.

## Core workflow

**Universe → Quality/Liquidity Filter → Technical Structure → Pattern Engine → Relative Strength / Market Context → Supply & Demand → Confluence Entry → Execution Timing → News/Narrative enrichment**

## Included engines

### 1. Technical / market-state engine
- Structure: Bullish / Neutral / Bearish
- Phase: continuation, pullback, pre-breakout, confirmed breakout, consolidation, overextended
- Momentum state
- Technical Quality score
- ATR / RSI / MACD / ADX / MA and EMA context

### 2. Intelligent levels + IDX execution prices
- Swing-based support/resistance clustering
- Level scoring / confluence
- Level-aware IDX tick-size conversion
- Directional rounding:
  - breakout trigger → up to valid tick
  - stop → down to valid tick
  - TP → conservative valid tick
  - support/resistance → nearest valid tick

IDX planning fractions used by the engine:
- < 200 → Rp1
- 200–499 → Rp2
- 500–1,999 → Rp5
- 2,000–4,999 → Rp10
- >= 5,000 → Rp25

### 3. Quality-200 tiered universe
- Tier A / B / C guardrails
- Liquidity screening by 20D average traded value
- Stricter requirements for higher-beta Tier C names

### 4. Pattern screener
Primary daily-workflow patterns:
- VCP / Early VCP
- Flat Base / Tight Base
- Cup & Handle
- Darvas Box
- Bull Flag
- High Tight Flag (higher-risk treatment)
- NR7 / Volatility Squeeze
- Ascending Triangle
- EMA20/50 Golden Cross
- Pre-Golden Cross
- Pattern Breakout
- Uptrend
- 52-Week Leader
- SUPER SETUP / Priority Setup confluence

Lower-value/noisier pattern presets are de-emphasized from the main workflow but may remain in diagnostics.

### 5. Relative Strength + market context
- Relative Strength vs IHSG (RS Score)
- Multi-horizon relative performance
- Benchmark regime
- Market-context score
- Volume-flow context

**RS in Antolui Screener means Relative Strength vs IHSG, not RSI.**

### 6. News & Narrative engine
- Confirmed / official news
- Reported news
- Market narrative
- Unconfirmed rumor classification
- Catalyst bias / Catalyst Score
- Narrative heat / Rumor risk
- Optional confirmed-news ranking overlay

Rumors do not automatically boost ranking.

### 7. Supply & Demand engine
Heuristic price-action zones based on:
- base + departure behavior
- ATR departure strength
- volume
- freshness / retests
- MA/EMA confluence
- invalidation

Supply/demand zones are decision-support heuristics, not proof of institutional orders.

### 8. Confluence Entry engine
Compares multiple entry candidates:
- Demand Retest
- Pullback Confluence
- Pattern Pivot
- Breakout Confirmation

Outputs:
- Ideal Entry
- Entry Zone
- Entry Type
- Entry Score
- Demand / Supply zones
- Candidate-specific stop
- RR

### 9. Execution Timing engine
Separates setup quality from whether the stock is actionable **now**.

Execution states:
- BUY NOW
- WAIT RETEST
- WAIT BREAKOUT
- WAIT CONFIRMATION
- WAIT RECLAIM
- TOO EXTENDED
- AVOID
- INVALIDATED

Outputs:
- Timing Score
- Timing Confidence
- Active Buy Entry / Buy Entry Zone
- Buy Stop
- Buy Entry RR
- Confirmation Score
- Distance to Entry
- Supply Headroom

## Compact scanner UI

The main scanner intentionally prioritizes only high-value fields:

`Ticker | Tier | Score | Pattern | Execution | Timing | Entry | Entry Type | RS | RR | SL | TP2`

- **RS** is shown as a numeric Relative Strength score rather than repetitive “Outperforming” text.
- **RR** is a single execution-relevant RR for the active entry; detailed TP1/TP2 RR remains available in diagnostics.
- Lower-priority diagnostics remain in the expandable detailed table.

## Recommended daily workflow

1. Universe: **Quality 200 (Tiered)**
2. Strict Tier rules: **ON**
3. Min Avg Traded Value: **Rp5B** baseline
4. Min RR: **1.5–2.0** depending on strictness
5. Start with presets:
   - BUY NOW
   - SUPER SETUP
   - WAIT BREAKOUT
   - WAIT RETEST
6. Prioritize strong RS, realistic RR, good liquidity, and valid entry timing.
7. Enrich only top candidates with News/Narrative to keep the scanner responsive.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
python tests_ticks.py
python tests_patterns.py
python tests_patterns_v57.py
python tests_entry.py
python tests_timing.py
python tests_scanner.py
python tests_tiers.py
python tests_context.py
python tests_news.py
python tests_engine.py
python tests_levels.py
```

## Important

Antolui Screener is decision-support software. Pattern detection, supply/demand zones, entries, stops, targets, timing scores, news classifications, and rankings are quantitative/heuristic outputs and are not guarantees. Historical backtesting and walk-forward validation should be completed before treating scores as a proven trading edge.
