# Antolui Screener V6.0 — Analyst Intelligence Architecture

## Goal

Replicate the *reasoning hierarchy* visible in high-quality discretionary stock picks without pretending to know any broker's proprietary formula, then add an independent machine-scale validation layer that a human analyst may not consistently apply across a large universe.

## Core principle

**Price determines the thesis and levels. Indicators confirm the relevant setup.**

V6.0 therefore does not ask every stock the same RSI/MACD/volume questions with the same weights. The setup is detected first; the confirmation model changes afterwards.

## Layer A — setup-adaptive analyst reasoning

### Pivot / resistance breakout
Primary questions: Is price near a valid pivot? Is the breakout actionable? Is volume expanding? Is the candle closing constructively? Momentum is supportive but secondary.

### MA20 reclaim
Primary questions: Did price reclaim MA20 recently? Is price still close enough to the reclaim? Is MACD improving / positive? Is Stoch RSI crossing bullishly? Volume has a smaller role than in a pure breakout.

### Support hold rebound
Primary questions: Is the correction normal rather than structural damage? Is price holding a meaningful support? Is entry close to invalidation? Is MACD still constructive? Is there bullish rejection? Stoch RSI can show short-term exhaustion.

### Pullback pivot hold
Primary questions: Did price recently test a resistance, then pull back normally into a pivot/support? Is momentum turning back up? Is the next resistance a clear continuation-confirmation level?

### Trendline support rebound
Primary questions: Is there a multi-touch rising/near-flat support line with reasonable fit? Is price close to it? Is short-term momentum oversold/turning while MACD remains constructive? Is the stop logically below the trendline?

### Base retest
Primary questions: Was there a valid base/pattern pivot that price already traded above? Has price returned to the base without invalidating it? Is pullback volume constructive? Is rejection visible near the retest?

## Entry modes

- **EARLY** — support/pivot/trendline hold before a larger confirmation breakout.
- **TRIGGER** — execute around a breakout/reclaim trigger.
- **RETEST** — execute when a previous breakout/base is being retested.

This distinction matters because an analyst can buy early near support while still naming a higher resistance as the level that confirms bullish continuation.

## Trade path

V6.0 distinguishes:

- Entry Zone
- Initial Trigger (when applicable)
- Major Confirmation (a stronger overhead barrier; not forced)
- Structural Stop / invalidation
- TP1, TP2, TP3

TP1 may occur before Major Confirmation when the existing structural plan already has a sensible partial-profit level below that barrier. Major Confirmation is not treated as a take-profit target by definition.

## Layer B — Independent Antolui Edge

After the analyst-style thesis is built, a second layer independently checks:

- combined stock-vs-IHSG / stock-vs-sector Relative Strength
- IHSG market context
- sector context
- technical trend quality
- execution-timing score
- quality-adjusted RR
- entry proximity
- nearby supply headroom

The purpose is disagreement detection. A pretty setup can be capped when RR is poor, the stock is extended, structure is bearish, or supply sits immediately overhead.

## Scores

- **Analyst Score** — setup-specific discretionary-style reasoning.
- **Edge Score** — independent Antolui validation.
- **Conviction Score** — 62% Analyst Score + 38% Edge Score, subject to veto/caps.

Current caps include bearish structure, RR below 1.5, overextension and supply too close for rebound-style entries.

## Learning loop

The file `analyst_pick_history.csv` is the research memory. New daily examples can be appended with explicit setup/entry/stop/target/indicator information. Later, outcome fields can be filled (TP1/TP2/TP3 before SL, SL before TP1).

The calibration layer uses resolved outcomes only. It does **not** infer edge from how often an analyst picks a setup. A Beta(5,5) prior is used for TP1 success; calibration remains inactive until at least 10 resolved examples exist for a setup and is capped at ±5 score points.

This means early V6 behavior is driven by transparent structural priors. As the one-month dataset matures, evidence can adjust—but not dominate—the live setup score.

## What “better than a human analyst” means here

V6.0 does not assume AI is automatically more accurate. Its potential advantages are measurable: scan far more charts consistently, apply the same risk discipline without fatigue, keep explicit research memory, compare outcomes, and combine analyst-style chart reasoning with RS/sector/market/supply/RR checks on every candidate. Superiority should be judged only after forward comparison on the same dates and universe.
