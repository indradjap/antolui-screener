from __future__ import annotations

import math
from typing import Optional


# Antolui Screener V5.6 — level-aware IDX price fractions
# ----------------------------------------------------
# Scanner levels (trigger, support, SL, TP, pattern pivot) are forward-looking
# prices that can be reached on a later session. Therefore each executable
# level is normalized using the price band of THAT LEVEL itself:
#   < 200       -> Rp1
#   200-<500    -> Rp2
#   500-<2,000  -> Rp5
#   2,000-<5,000-> Rp10
#   >=5,000     -> Rp25
#
# This avoids outputs such as 506 for a forward trigger: 506 lies in the
# Rp500-Rp1,999 band, so the executable trigger must be 510 when rounded up.
#
# Note: IDX also states that the trading-day fraction is fixed for the full
# session based on the applicable reference band and adjusted the following
# day if the close moves bands. Antolui Screener's scanner uses level-aware rounding
# because its targets/triggers are multi-session decision-support levels.


def tick_size(price: float) -> int:
    p = float(price)
    if not math.isfinite(p) or p <= 0:
        raise ValueError("price must be positive and finite")
    if p < 200:
        return 1
    if p < 500:
        return 2
    if p < 2000:
        return 5
    if p < 5000:
        return 10
    return 25


def _clean(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    v = float(value)
    return v if math.isfinite(v) and v > 0 else None


def _level_tick(value: float) -> int:
    """Tick determined from the executable level itself."""
    return tick_size(value)


def floor_to_tick(value: Optional[float], reference_price: Optional[float] = None) -> Optional[int]:
    """
    Round DOWN to a valid forward-looking IDX price level.

    `reference_price` is kept only for backward API compatibility and is
    intentionally ignored in V5.6; the level's own band controls the tick.
    """
    v = _clean(value)
    if v is None:
        return None
    tick = _level_tick(v)
    return int(math.floor((v + 1e-10) / tick) * tick)


def ceil_to_tick(value: Optional[float], reference_price: Optional[float] = None) -> Optional[int]:
    """Round UP to a valid forward-looking IDX price level."""
    v = _clean(value)
    if v is None:
        return None
    tick = _level_tick(v)
    return int(math.ceil((v - 1e-10) / tick) * tick)


def nearest_to_tick(value: Optional[float], reference_price: Optional[float] = None) -> Optional[int]:
    """Round to the nearest valid forward-looking IDX price level."""
    v = _clean(value)
    if v is None:
        return None
    lower = floor_to_tick(v)
    upper = ceil_to_tick(v)
    if lower is None or upper is None:
        return None
    # At an exact half-tick prefer the lower level (conservative output).
    return int(lower if abs(v - lower) <= abs(upper - v) else upper)


def conservative_floor_to_tick(
    value: Optional[float],
    reference_price: Optional[float] = None,
    snap_fraction: float = 0.05,
) -> Optional[int]:
    """
    Directional floor with a tiny numerical-noise snap.

    Example: 914.95 in the Rp5 band -> 915 (noise snap), while 913.10 -> 910.
    """
    v = _clean(value)
    if v is None:
        return None
    tick = _level_tick(v)
    nearest = nearest_to_tick(v)
    if nearest is not None and abs(v - nearest) <= tick * float(snap_fraction):
        return int(nearest)
    return floor_to_tick(v)


def next_tick_above(value: float, reference_price: Optional[float] = None) -> int:
    """First valid forward-looking IDX price strictly above value."""
    v = _clean(value)
    if v is None:
        raise ValueError("value must be positive and finite")
    rounded = ceil_to_tick(v)
    if rounded is None:
        raise ValueError("value must be finite")
    if rounded <= v + 1e-10:
        # Use the band at the already-valid level, then re-normalize because
        # stepping can cross a band boundary.
        candidate = rounded + tick_size(rounded)
        rounded = ceil_to_tick(candidate)
    return int(rounded)


def previous_tick_below(value: float, reference_price: Optional[float] = None) -> int:
    """First valid forward-looking IDX price strictly below value."""
    v = _clean(value)
    if v is None:
        raise ValueError("value must be positive and finite")
    rounded = floor_to_tick(v)
    if rounded is None:
        raise ValueError("value must be finite")
    if rounded >= v - 1e-10:
        candidate = rounded - max(1, tick_size(max(rounded - 1e-9, 1)))
        rounded = floor_to_tick(candidate)
    return int(max(rounded, 1))
