from __future__ import annotations

import numpy as np
import pandas as pd
from levels import discover_levels, select_level
from idx_ticks import tick_size, floor_to_tick, ceil_to_tick, nearest_to_tick, conservative_floor_to_tick, previous_tick_below


def _fallback_below(price, candidates):
    vals = [float(v) for v in candidates if v is not None and pd.notna(v) and float(v) < price]
    return sorted(vals, reverse=True)


def _fallback_above(price, candidates):
    vals = [float(v) for v in candidates if v is not None and pd.notna(v) and float(v) > price]
    return sorted(vals)


def _find_broken_resistance(level_result, price, atr):
    """Best resistance just below current price for a confirmed breakout."""
    below = []
    for lvl in level_result.get("all_levels", []):
        center = float(lvl["center"])
        if center <= price and (price - center) <= max(2.0 * atr, price * 0.06):
            # Prefer historical high-heavy clusters and stronger scores.
            high_ratio = lvl.get("high_touches", 0) / max(lvl.get("touches", 1), 1)
            if high_ratio >= 0.45:
                below.append(lvl)
    below.sort(key=lambda l: (price - float(l["center"]), -float(l["score"])))
    return below[0] if below else None


def _round_px(v):
    return round(float(v), 2) if v is not None and np.isfinite(float(v)) else None



def _tradable_zone(low, high, reference_price=None):
    """Convert analytical range into level-aware executable IDX tick boundaries."""
    lo = ceil_to_tick(low)
    hi = floor_to_tick(high)
    if lo is None or hi is None:
        return lo, hi
    if hi < lo:
        mid = nearest_to_tick((float(low) + float(high)) / 2.0)
        return mid, mid
    return int(lo), int(hi)


def _recalculate_rr(entry, stop, tp):
    if entry is None or stop is None or tp is None:
        return 0.0
    risk = float(entry) - float(stop)
    if risk <= 0:
        return 0.0
    return max(0.0, (float(tp) - float(entry)) / risk)

def build_trade_plan(df, phase_label):
    x = df.iloc[-1]
    price = float(x["Close"])
    atr = float(x["ATR14"])
    if not np.isfinite(atr) or atr <= 0:
        atr = max(price * 0.03, 1e-6)

    if {"High", "Low", "Close"}.issubset(df.columns):
        level_result = discover_levels(df)
    else:
        # Compatibility fallback for minimal/unit-test frames that only contain
        # derived indicators. Real app data always contains OHLCV.
        level_result = {
            "price": round(price, 2), "atr": round(atr, 2),
            "supports": [], "resistances": [], "all_levels": [],
            "pivot_count": 0, "cluster_count": 0,
        }
    supports = level_result["supports"]
    resistances = level_result["resistances"]

    support1_obj = select_level(supports, min_score=28)
    support2_obj = None
    if support1_obj:
        s1_center = float(support1_obj["center"])
        # S2 is intended as the next *major* structural floor, not a tiny nearby
        # micro-level. Require meaningful separation and prefer strength.
        min_separation = max(1.0 * atr, price * 0.03)
        deeper = [s for s in supports if float(s["center"]) < s1_center - min_separation]
        strong_deeper = [s for s in deeper if float(s.get("score", 0)) >= 30]
        pool = strong_deeper or deeper
        if pool:
            support2_obj = sorted(
                pool,
                key=lambda s: (-float(s.get("score", 0)), s1_center - float(s["center"]))
            )[0]

    resistance1_obj = select_level(resistances, min_score=28)
    resistance2_obj = None
    if resistance1_obj:
        r1_center = float(resistance1_obj["center"])
        remaining = [r for r in resistances if float(r["center"]) > r1_center + 0.25 * atr]
        resistance2_obj = select_level(remaining, min_score=25)

    # Fallbacks preserve functionality when a new IPO / sparse chart has few pivots.
    fallback_supports = _fallback_below(
        price,
        [x.get("MA20"), x.get("MA50"), x.get("Low20"), x.get("Low60")],
    )
    fallback_res = _fallback_above(
        price,
        [x.get("PrevHigh20"), x.get("High20"), x.get("High60")],
    )

    if support1_obj:
        support1 = float(support1_obj["center"])
        support1_low = float(support1_obj["zone_low"])
    else:
        support1 = fallback_supports[0] if fallback_supports else price - 1.5 * atr
        support1_low = support1 - 0.25 * atr

    if support2_obj:
        support2 = float(support2_obj["center"])
    else:
        support2 = fallback_supports[1] if len(fallback_supports) > 1 else price - 2.5 * atr

    if resistance1_obj:
        resistance1 = float(resistance1_obj["center"])
    else:
        resistance1 = fallback_res[0] if fallback_res else price + 1.5 * atr

    if resistance2_obj:
        resistance2 = float(resistance2_obj["center"])
    else:
        resistance2 = fallback_res[1] if len(fallback_res) > 1 else resistance1 + 2.0 * atr

    prev_high20 = float(x.get("PrevHigh20", resistance1)) if pd.notna(x.get("PrevHigh20", np.nan)) else resistance1

    if phase_label == "Pre-Breakout":
        # Use the nearest resistance zone, but keep PrevHigh20 as a sanity anchor.
        breakout_trigger = resistance1
        if abs(prev_high20 - price) < abs(resistance1 - price) and prev_high20 > price:
            breakout_trigger = prev_high20
        entry_reference = breakout_trigger
    elif phase_label == "Confirmed Breakout":
        broken = _find_broken_resistance(level_result, price, atr)
        breakout_trigger = float(broken["center"]) if broken else prev_high20
        entry_reference = price
    else:
        breakout_trigger = resistance1
        entry_reference = price

    # Structural invalidation: below the support zone, not at its center.
    # 0.45 ATR approximates the buffer needed to avoid normal intraday noise.
    stop_buffer = max(0.45 * atr, price * 0.006)
    structural_stop = support1_low - stop_buffer

    # Prevent a nonsensically wide stop. If support is too far, use ATR risk cap.
    max_stop_distance = 2.5 * atr
    stop_floor = price - max_stop_distance
    stop_loss = max(structural_stop, stop_floor, 0.0)

    risk = entry_reference - stop_loss
    if risk <= 0:
        risk = max(atr, price * 0.02)
        stop_loss = max(entry_reference - risk, 0.0)

    # Target logic: resistance being tested is the *trigger*, not TP1.
    # For pullbacks / pre-breakouts, targets start at the next structural level
    # above the trigger. For confirmed breakouts, targets start above current price.
    if phase_label in ("Pullback in Uptrend", "Pre-Breakout"):
        primary_entry = breakout_trigger
        target_floor = breakout_trigger + 0.25 * atr
    elif phase_label == "Confirmed Breakout":
        primary_entry = price
        target_floor = price + 0.25 * atr
    else:
        primary_entry = price
        target_floor = price + 0.25 * atr

    target_levels = [r for r in resistances if float(r["center"]) > target_floor]
    tp1_obj = target_levels[0] if target_levels else None
    tp2_obj = target_levels[1] if len(target_levels) > 1 else None

    primary_risk = primary_entry - stop_loss
    if primary_risk <= 0:
        primary_risk = max(atr, primary_entry * 0.02)

    rr_target_2r = primary_entry + 2.0 * primary_risk
    rr_target_3r = primary_entry + 3.0 * primary_risk

    tp1 = float(tp1_obj["center"]) if tp1_obj else rr_target_2r
    if tp1 <= primary_entry:
        tp1 = rr_target_2r

    tp2 = float(tp2_obj["center"]) if tp2_obj else max(rr_target_3r, tp1 + atr)
    if tp2 <= tp1:
        tp2 = max(rr_target_3r, tp1 + atr)

    rr1 = (tp1 - primary_entry) / primary_risk if primary_risk > 0 else 0.0
    rr2 = (tp2 - primary_entry) / primary_risk if primary_risk > 0 else 0.0

    # Also show aggressive support-retest RR separately.
    aggressive_entry_ref = support1
    aggressive_risk = aggressive_entry_ref - stop_loss
    aggressive_rr1 = (tp1 - aggressive_entry_ref) / aggressive_risk if aggressive_risk > 0 else 0.0
    aggressive_rr2 = (tp2 - aggressive_entry_ref) / aggressive_risk if aggressive_risk > 0 else 0.0

    # Entry zones: aggressive on support retest vs conservative breakout confirmation.
    aggressive_low = max(support1_low, support1 - 0.25 * atr)
    aggressive_high = min(price, support1 + 0.35 * atr)
    if aggressive_high < aggressive_low:
        aggressive_high = aggressive_low

    conservative_low = breakout_trigger
    conservative_high = breakout_trigger + 0.35 * atr

    # --- V5.6: level-aware IDX executable price fraction layer ------------
    # Each forward-looking level uses the price band of the level itself.
    # This prevents invalid multi-session scanner levels such as 506 when
    # the level is already inside the Rp500-Rp1,999 (Rp5 tick) band.
    idx_tick = tick_size(price)

    # Analytical levels remain untouched in level_engine. Only executable
    # outputs are converted to valid order prices.
    px_exec = nearest_to_tick(price)
    support1_exec = nearest_to_tick(support1)
    support1_low_exec = floor_to_tick(support1_low)
    support2_exec = nearest_to_tick(support2)
    resistance1_exec = nearest_to_tick(resistance1)
    resistance2_exec = nearest_to_tick(resistance2)

    # Trigger is rounded UP so the displayed breakout threshold never sits
    # below the analytical resistance. The rule remains "breakout > trigger".
    trigger_exec = ceil_to_tick(breakout_trigger)

    # Stop is rounded DOWN to avoid making the invalidation tighter merely
    # because of tick conversion. Targets round DOWN for more conservative fills.
    stop_exec = conservative_floor_to_tick(stop_loss)
    tp1_exec = floor_to_tick(tp1)
    tp2_exec = floor_to_tick(tp2)

    agg_low_exec, agg_high_exec = _tradable_zone(aggressive_low, aggressive_high, price)
    cons_low_exec, cons_high_exec = _tradable_zone(conservative_low, conservative_high, price)

    # Conservative entry cannot start below the executable breakout trigger.
    if cons_low_exec is None or cons_low_exec < trigger_exec:
        cons_low_exec = trigger_exec
    if cons_high_exec is None or cons_high_exec < cons_low_exec:
        cons_high_exec = cons_low_exec

    # Guard against rounding collapsing targets onto/below the entry.
    primary_entry_exec = trigger_exec if phase_label in ("Pullback in Uptrend", "Pre-Breakout") else px_exec
    if tp1_exec is None or tp1_exec <= primary_entry_exec:
        tp1_exec = ceil_to_tick(primary_entry_exec + tick_size(primary_entry_exec))
    if tp2_exec is None or tp2_exec <= tp1_exec:
        tp2_exec = ceil_to_tick(tp1_exec + tick_size(tp1_exec))

    if stop_exec is None or stop_exec >= primary_entry_exec:
        stop_exec = max(previous_tick_below(primary_entry_exec), 1)

    rr1_exec = _recalculate_rr(primary_entry_exec, stop_exec, tp1_exec)
    rr2_exec = _recalculate_rr(primary_entry_exec, stop_exec, tp2_exec)
    aggressive_rr1_exec = _recalculate_rr(support1_exec, stop_exec, tp1_exec)
    aggressive_rr2_exec = _recalculate_rr(support1_exec, stop_exec, tp2_exec)

    return {
        "price": int(px_exec),
        "idx_tick_size": int(idx_tick),
        "trigger_tick_size": int(tick_size(trigger_exec)),
        "stop_tick_size": int(tick_size(stop_exec)),
        "tp1_tick_size": int(tick_size(tp1_exec)),
        "tp2_tick_size": int(tick_size(tp2_exec)),
        "tick_reference_price": int(px_exec),
        "aggressive_entry_low": int(agg_low_exec),
        "aggressive_entry_high": int(agg_high_exec),
        "breakout_trigger": int(trigger_exec),
        "conservative_entry_low": int(cons_low_exec),
        "conservative_entry_high": int(cons_high_exec),
        "support1": int(support1_exec),
        "support1_zone_low": int(support1_low_exec),
        "support2": int(support2_exec),
        "resistance1": int(resistance1_exec),
        "resistance2": int(resistance2_exec),
        "stop_loss": int(stop_exec),
        "tp1": int(tp1_exec),
        "tp2": int(tp2_exec),
        "primary_entry_reference": int(primary_entry_exec),
        "rr_tp1": round(float(rr1_exec), 2),
        "rr_tp2": round(float(rr2_exec), 2),
        "aggressive_rr_tp1": round(float(aggressive_rr1_exec), 2),
        "aggressive_rr_tp2": round(float(aggressive_rr2_exec), 2),
        "level_engine": level_result,
        # Keep raw theoretical levels for debugging/backtests, not order entry.
        "raw_levels": {
            "breakout_trigger": _round_px(breakout_trigger),
            "support1": _round_px(support1),
            "support2": _round_px(support2),
            "stop_loss": _round_px(stop_loss),
            "tp1": _round_px(tp1),
            "tp2": _round_px(tp2),
        },
    }
