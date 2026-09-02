# Antolui Screener V5.9 — Entry Timing / Execution Engine

V5.9 separates **setup quality** from **execution timing**.

## Execution states
- `BUY NOW` — price is inside an actionable entry zone and confirmation is sufficient.
- `WAIT RETEST` — setup is good but price is above the preferred demand/pullback zone.
- `WAIT BREAKOUT` — price is below the pivot/trigger.
- `WAIT CONFIRMATION` — price is near the zone but volume/candle/momentum confirmation is incomplete.
- `WAIT RECLAIM` — price slipped below the intended entry zone but remains above invalidation.
- `TOO EXTENDED` — price is too far above the entry zone/ATR; do not chase.
- `AVOID` — long setup conflicts with bearish structure/technical action.
- `INVALIDATED` — current price is at/below the stop/invalidation level.

## Timing Score (0–100)
Approximate weighting per entry candidate:
- 38% Entry Quality from V5.8 confluence engine
- 22% Current price proximity to entry zone
- 15% Momentum state
- 15% Confirmation (volume + candle close location + volume flow)
- 10% Risk/reward quality

Penalties apply for bearish structure, bearish momentum, market headwind, RS underperformance, RR < 1.5, and nearby supply.

## Important distinction
`Ideal Entry` remains the best risk-adjusted theoretical entry from V5.8.
`Buy Entry` in V5.9 is the entry candidate that is most relevant **now** after timing/confirmation checks.
A current breakout can therefore become the active Buy Entry even when an older demand retest would have offered a better theoretical RR.
