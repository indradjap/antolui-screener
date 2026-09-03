# Antolui Screener V5.9 — Quick Pick

Quick Pick is an execution-first universe scan. It does **not** copy or claim to reproduce any broker's proprietary model. It converts common actionable technical-analysis principles into explicit rules so the output can be inspected and tested.

## Scanner modes

- **Antolui Ranking** — ranks overall setup quality using technical structure, patterns, RS, market/sector context, liquidity, RR and timing.
- **Quick Pick** — prioritizes stocks close to an actionable trigger/retest with a clear invalidation and usable upside targets.

## Quick Pick setup families

1. **Pivot Breakout** — named pattern pivot / structural breakout near current price.
2. **MA20 Reclaim** — recent reclaim of MA20; momentum and Stoch RSI are confirmation only.
3. **Base Retest** — price returns to a still-valid VCP/Flat Base/Darvas/Bull Flag/etc. pivot after previously moving above it.
4. **Resistance Breakout** — break/retest of prior 20-day structural resistance when no named pattern is required.
5. **Pullback Rebound** — constructive rebound around MA20 or a detected demand zone.

## Quick Score

Quick Score is intentionally different from the normal Scanner Score:

- 28% Setup quality
- 20% Entry location / proximity
- 16% Volume confirmation
- 12% Momentum confirmation
- 10% Relative Strength
- 9% Risk/Reward
- 5% Market context

Penalties apply to overextended price, bearish structure, RR below 1.5, weak breakout volume, and nearby overhead supply for non-breakout entries.

## Confirmation hierarchy

Price structure is primary:

**Setup → Entry Zone → Trigger → Confirmation → Major Confirmation → Invalidation → Targets**

Volume, MACD/RSI momentum, Stochastic RSI, RS and market context strengthen or weaken a setup; none of them creates a Quick Pick by itself.

## Output

Quick Pick table includes:

- Quick Score
- Setup
- Status
- Entry Zone
- Trigger
- Major Confirm (only when a meaningful structural barrier exists before/around TP2)
- Stop
- TP1 / TP2 / TP3
- Volume state
- Stoch RSI state
- Market RS
- RR to TP2

Statuses:

- READY
- NEAR ENTRY
- WAIT BREAKOUT
- WAIT RECLAIM
- WAIT RETEST
- TOO EXTENDED
- INVALIDATED

## Targets and stops

Quick Pick reuses Antolui's structure-first trade plan. Stops remain structural/ATR-buffered and IDX-tick valid. TP1/TP2 come from the existing intelligent resistance engine (with RR fallback). TP3 uses the next valid structural resistance if available; otherwise it falls back to an extended risk target. Forward-looking levels use the level-aware IDX tick engine.

## Validation archetypes

Synthetic regression tests cover three common actionable archetypes:

- pivot breakout + volume expansion + later major confirmation
- MA20 reclaim + bullish Stoch RSI confirmation
- bullish base/pennant retest using an existing structural plan

Additional regression checks ensure overextended setups are not eligible and forward-looking Quick Pick levels remain valid across IDX tick-band boundaries.
