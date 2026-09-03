from __future__ import annotations

from typing import Any, Dict, List
import math
import numpy as np
import pandas as pd

from idx_ticks import ceil_to_tick, floor_to_tick, nearest_to_tick, conservative_floor_to_tick, previous_tick_below
from analyst_learning import setup_calibration


def _num(v, default=0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _clamp(v, lo=0.0, hi=100.0) -> float:
    return max(lo, min(hi, float(v)))


def _rr(entry, stop, target) -> float:
    entry, stop, target = _num(entry), _num(stop), _num(target)
    risk = entry - stop
    return max(0.0, (target - entry) / risk) if risk > 0 else 0.0


def _rr_score(rr: float) -> float:
    rr = max(_num(rr), 0.0)
    if rr >= 4.0:
        return 100.0
    if rr >= 3.0:
        return 88.0 + 12.0 * min(rr - 3.0, 1.0)
    if rr >= 2.0:
        return 70.0 + 18.0 * (rr - 2.0)
    if rr >= 1.5:
        return 48.0 + 44.0 * (rr - 1.5)
    return _clamp(rr / 1.5 * 48.0)


def _macd_state(df: pd.DataFrame) -> Dict[str, Any]:
    x = df.iloc[-1]
    p = df.iloc[-2] if len(df) > 1 else x
    macd = _num(x.get("MACD"))
    sig = _num(x.get("MACD_signal"))
    pm = _num(p.get("MACD"), macd)
    ps = _num(p.get("MACD_signal"), sig)
    cross_up = pm <= ps and macd > sig
    cross_down = pm >= ps and macd < sig
    positive = macd > 0
    hist_rising = _num(x.get("MACD_hist")) > _num(p.get("MACD_hist"))
    if cross_up:
        label, score = "GOLDEN CROSS", 96.0
    elif positive and macd >= sig:
        label, score = "POSITIVE + BULLISH", 88.0
    elif positive:
        label, score = "POSITIVE AREA", 76.0
    elif macd >= sig and hist_rising:
        label, score = "IMPROVING", 68.0
    elif cross_down:
        label, score = "BEARISH CROSS", 25.0
    else:
        label, score = "WEAK", 40.0
    return {
        "label": label, "score": score, "positive": positive, "cross_up": cross_up,
        "cross_down": cross_down, "hist_rising": hist_rising,
    }


def _stoch_state(df: pd.DataFrame) -> Dict[str, Any]:
    x = df.iloc[-1]
    p = df.iloc[-2] if len(df) > 1 else x
    k = _num(x.get("StochRSI_K"), 50.0)
    d = _num(x.get("StochRSI_D"), 50.0)
    pk = _num(p.get("StochRSI_K"), k)
    pd_ = _num(p.get("StochRSI_D"), d)
    cross_up = pk <= pd_ and k > d
    oversold = k <= 25 or d <= 25
    overbought = k >= 85 and d >= 80
    if cross_up and oversold:
        label, score = "OVERSOLD BULL CROSS", 100.0
    elif cross_up:
        label, score = "BULLISH CROSS", 92.0
    elif oversold:
        label, score = "OVERSOLD", 82.0
    elif k > d and not overbought:
        label, score = "BULLISH", 74.0
    elif overbought:
        label, score = "OVERBOUGHT", 48.0
    else:
        label, score = "NEUTRAL", 55.0
    return {"label": label, "score": score, "oversold": oversold, "cross_up": cross_up, "k": round(k, 1), "d": round(d, 1)}


def _candle_rejection_score(df: pd.DataFrame) -> float:
    x = df.iloc[-1]
    hi, lo, close = _num(x.get("High")), _num(x.get("Low")), _num(x.get("Close"))
    opn = _num(x.get("Open"), close)
    rng = max(hi - lo, 1e-9)
    close_loc = (close - lo) / rng
    lower_wick = (min(opn, close) - lo) / rng
    bullish_body = max(close - opn, 0.0) / rng
    return round(_clamp(45.0 * close_loc + 35.0 * lower_wick + 20.0 * bullish_body), 1)


def _volume_character(df: pd.DataFrame, mode: str) -> Dict[str, Any]:
    x = df.iloc[-1]
    vr = max(_num(x.get("Volume_ratio"), 1.0), 0.0)
    flow5 = _num(x.get("VolumeFlow5"), 0.0)
    close_loc = _num(x.get("close_location"), 0.5)
    if mode == "breakout":
        score = _clamp(32 + min(vr, 2.5) / 2.0 * 50 + max(flow5, 0) * 10 + max(close_loc - 0.5, 0) * 16)
    else:
        # Healthy pullbacks frequently contract in volume; penalize only obvious distribution.
        contraction = 90.0 if 0.55 <= vr <= 1.15 else (72.0 if vr <= 1.45 else 52.0)
        score = _clamp(0.75 * contraction + 15 * max(flow5, -0.3) + 10 * close_loc)
    label = "STRONG" if score >= 85 else "GOOD" if score >= 70 else "NORMAL" if score >= 55 else "WEAK"
    return {"score": round(score, 1), "label": label, "ratio": round(vr, 2)}


def _find_local_lows(df: pd.DataFrame, lookback: int = 70, order: int = 2) -> List[tuple[int, float]]:
    lows = df["Low"].astype(float).tail(lookback).reset_index(drop=True)
    out: List[tuple[int, float]] = []
    for i in range(order, len(lows) - order):
        v = float(lows.iloc[i])
        if v <= float(lows.iloc[i-order:i].min()) and v <= float(lows.iloc[i+1:i+order+1].min()):
            out.append((i, v))
    # Reduce near-duplicate consecutive pivots.
    dedup: List[tuple[int, float]] = []
    for p in out:
        if not dedup or p[0] - dedup[-1][0] >= 3:
            dedup.append(p)
        elif p[1] < dedup[-1][1]:
            dedup[-1] = p
    return dedup[-6:]


def _trendline_support(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df) < 35 or "Low" not in df:
        return {"valid": False, "score": 0.0, "support": None}
    work = df.tail(70).reset_index(drop=True)
    pivots = _find_local_lows(work, lookback=min(70, len(work)), order=2)
    if len(pivots) < 3:
        return {"valid": False, "score": 0.0, "support": None, "touches": len(pivots)}
    xs = np.array([p[0] for p in pivots], dtype=float)
    ys = np.array([p[1] for p in pivots], dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    pred = slope * xs + intercept
    ss_res = float(np.sum((ys - pred) ** 2))
    ss_tot = float(np.sum((ys - ys.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.5
    support_now = float(slope * (len(work) - 1) + intercept)
    price = _num(work.iloc[-1].get("Close"))
    atr = max(_num(work.iloc[-1].get("ATR14"), price * 0.03), price * 0.005)
    distance_atr = (price - support_now) / atr if atr > 0 else 99.0
    # Rising or almost-flat support; strongly falling lines are not bullish continuation support.
    slope_pct_20 = slope * 20 / max(support_now, 1e-9)
    slope_score = _clamp((slope_pct_20 + 0.01) / 0.08 * 100.0)
    fit_score = _clamp(r2 * 100.0)
    touch_score = _clamp(45 + 12 * len(pivots))
    proximity_score = _clamp(100 - abs(distance_atr) * 35)
    score = 0.30 * fit_score + 0.20 * slope_score + 0.20 * touch_score + 0.30 * proximity_score
    valid = bool(score >= 58 and support_now > 0 and -0.6 <= distance_atr <= 1.4 and slope_pct_20 >= -0.01)
    return {
        "valid": valid, "score": round(score, 1), "support": round(support_now, 2),
        "touches": len(pivots), "r2": round(r2, 3), "slope_20d_pct": round(slope_pct_20 * 100, 2),
        "distance_atr": round(distance_atr, 2),
    }


def _nearest_overhead_level(trade_plan: dict, floor_price: float, min_gap_pct: float = 0.012) -> float | None:
    levels = trade_plan.get("level_engine", {}).get("all_levels", []) or []
    candidates = []
    for lvl in levels:
        center = _num(lvl.get("center"))
        if center <= floor_price * (1 + min_gap_pct):
            continue
        touches = max(int(lvl.get("touches", 1) or 1), 1)
        high_ratio = _num(lvl.get("high_touches"), 0) / touches
        score = _num(lvl.get("score"), 0)
        if score >= 27 and high_ratio >= 0.30:
            candidates.append((center, score))
    if candidates:
        candidates.sort(key=lambda z: (z[0], -z[1]))
        return candidates[0][0]
    r1 = _num(trade_plan.get("resistance1"))
    return r1 if r1 > floor_price else None


def _next_targets(trade_plan: dict, entry: float, stop: float, confirmation: float | None, atr: float) -> tuple[int, int, int]:
    levels = trade_plan.get("level_engine", {}).get("all_levels", []) or []
    floor_px = max(entry, confirmation or entry)
    rs = []
    for lvl in levels:
        c = _num(lvl.get("center"))
        touches = max(int(lvl.get("touches", 1) or 1), 1)
        hr = _num(lvl.get("high_touches"), 0) / touches
        if c > floor_px + max(0.25 * atr, floor_px * 0.005) and _num(lvl.get("score")) >= 24 and hr >= 0.25:
            rs.append(c)
    rs = sorted(set(round(x, 4) for x in rs))
    risk = max(entry - stop, atr * 0.7, entry * 0.012)
    fallback = [entry + 1.5 * risk, entry + 3.0 * risk, entry + 4.0 * risk]
    vals: List[float] = []
    for c in rs:
        if c > entry and (not vals or c > vals[-1] + 0.2 * atr):
            vals.append(c)
        if len(vals) >= 3:
            break
    while len(vals) < 3:
        candidate = fallback[len(vals)]
        if vals and candidate <= vals[-1]:
            candidate = vals[-1] + max(atr, risk)
        vals.append(candidate)
    return tuple(int(floor_to_tick(v)) for v in vals[:3])


def _normal_pullback_score(df: pd.DataFrame) -> float:
    x = df.iloc[-1]
    price = _num(x.get("Close"))
    high20 = _num(x.get("High20"), price)
    dd = (high20 - price) / max(high20, 1e-9)
    # Best zone roughly 3-12%; too shallow is not a pullback, too deep risks structural damage.
    if 0.03 <= dd <= 0.12:
        dd_score = 100.0
    elif 0.015 <= dd < 0.03 or 0.12 < dd <= 0.18:
        dd_score = 72.0
    else:
        dd_score = 35.0
    ma50 = _num(x.get("MA50"))
    structure_score = 100.0 if price > ma50 > 0 else 55.0
    return round(0.72 * dd_score + 0.28 * structure_score, 1)


def _entry_location_score(price: float, low: float, high: float) -> tuple[float, float]:
    low, high = sorted((_num(low), _num(high)))
    price = max(_num(price), 1e-9)
    if low <= price <= high:
        return 100.0, 0.0
    if price < low:
        dist = -(low / price - 1.0) * 100
    else:
        dist = (price / high - 1.0) * 100
    return round(_clamp(100 - abs(dist) * 20), 1), round(dist, 2)


def _adaptive_analyst_score(setup: str, setup_quality: float, location: float, volume: Dict[str, Any],
                            macd: Dict[str, Any], stoch: Dict[str, Any], rejection: float,
                            pullback: float, trendline: Dict[str, Any], rr: float) -> tuple[float, Dict[str, float]]:
    # Each setup asks different questions—the core lesson from analyst calls.
    if setup in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"}:
        weights = {"setup": .25, "location": .18, "volume": .25, "macd": .10, "stoch": .04, "rejection": .08, "pullback": .00, "trendline": .00, "rr": .10}
    elif setup == "MA20 RECLAIM":
        weights = {"setup": .24, "location": .20, "volume": .08, "macd": .17, "stoch": .16, "rejection": .05, "pullback": .00, "trendline": .00, "rr": .10}
    elif setup in {"SUPPORT HOLD REBOUND", "PULLBACK PIVOT HOLD"}:
        weights = {"setup": .21, "location": .23, "volume": .07, "macd": .17, "stoch": .10, "rejection": .09, "pullback": .08, "trendline": .00, "rr": .05}
    elif setup == "TRENDLINE SUPPORT REBOUND":
        weights = {"setup": .17, "location": .20, "volume": .05, "macd": .17, "stoch": .15, "rejection": .08, "pullback": .05, "trendline": .10, "rr": .03}
    elif setup == "BASE RETEST":
        weights = {"setup": .24, "location": .23, "volume": .12, "macd": .10, "stoch": .06, "rejection": .10, "pullback": .08, "trendline": .00, "rr": .07}
    else:
        weights = {"setup": .24, "location": .22, "volume": .12, "macd": .12, "stoch": .08, "rejection": .08, "pullback": .05, "trendline": .00, "rr": .09}
    values = {
        "setup": setup_quality, "location": location, "volume": volume["score"], "macd": macd["score"],
        "stoch": stoch["score"], "rejection": rejection, "pullback": pullback,
        "trendline": _num(trendline.get("score"), 50.0), "rr": _rr_score(rr),
    }
    score = sum(weights[k] * values[k] for k in weights)
    calib = setup_calibration(setup)
    score = _clamp(score + _num(calib.get("score_adjustment")))
    components = {k.title(): round(values[k], 1) for k in weights if weights[k] > 0}
    components["Learning Adj"] = round(_num(calib.get("score_adjustment")), 1)
    return round(score, 1), components


def _independent_edge_score(technical: dict, context: dict, timing_plan: dict, entry_plan: dict,
                            rr: float, location: float, supply_headroom: float | None) -> tuple[float, Dict[str, float]]:
    rs_obj = context.get("combined_relative_strength") or context.get("relative_strength") or {}
    rs = _num(rs_obj.get("score"), 50.0)
    market = _num(context.get("score"), 50.0)
    sector = _num((context.get("sector") or {}).get("score"), 50.0)
    trend = _num(technical.get("trade_quality"), 50.0)
    timing = _num(timing_plan.get("score"), 50.0)
    if supply_headroom is None:
        supply = 65.0
    elif supply_headroom >= 8:
        supply = 100.0
    elif supply_headroom >= 4:
        supply = 85.0
    elif supply_headroom >= 2:
        supply = 68.0
    elif supply_headroom >= 1:
        supply = 48.0
    else:
        supply = 25.0
    values = {
        "RS": rs, "Market": market, "Sector": sector, "Trend": trend,
        "Timing": timing, "RR": _rr_score(rr), "Location": location, "Supply": supply,
    }
    score = (
        .19 * rs + .12 * market + .08 * sector + .16 * trend + .13 * timing +
        .13 * values["RR"] + .11 * location + .08 * supply
    )
    return round(_clamp(score), 1), {k: round(v, 1) for k, v in values.items()}


def _trade_status(price: float, low: float, high: float, score: float, conviction: float,
                  setup: str, stop: float, phase: str) -> str:
    if stop > 0 and price <= stop:
        return "INVALIDATED"
    if phase == "Overextended" or price > high * 1.055:
        return "TOO EXTENDED"
    if low <= price <= high:
        return "READY" if score >= 72 and conviction >= 68 else "NEAR ENTRY"
    if price < low:
        if setup in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"}:
            return "WAIT BREAKOUT"
        if setup == "MA20 RECLAIM":
            return "WAIT RECLAIM"
        return "WAIT SUPPORT"
    dist = (price / max(high, 1e-9) - 1) * 100
    if dist <= 2.0 and conviction >= 74:
        return "READY"
    return "WAIT RETEST"


def build_analyst_intelligence(
    df: pd.DataFrame,
    technical: Dict[str, Any],
    context: Dict[str, Any],
    pattern: Dict[str, Any],
    trade_plan: Dict[str, Any],
    entry_plan: Dict[str, Any],
    timing_plan: Dict[str, Any],
    quick_pick: Dict[str, Any],
) -> Dict[str, Any]:
    """Setup-adaptive analyst reasoning plus an independent Antolui edge layer.

    Layer A emulates the *decision hierarchy* visible in discretionary analyst
    stock picks: price structure -> actionable level -> setup-specific confirmation
    -> invalidation -> trade path. Layer B deliberately does not imitate that
    process and adds machine-scale checks (RS, market/sector context, timing, RR,
    nearby supply). Final conviction requires both layers to agree.
    """
    if df is None or len(df) < 2:
        return {"eligible": False, "conviction": 0.0, "setup": "NONE", "status": "NO SETUP"}

    x = df.iloc[-1]
    price = _num(x.get("Close"))
    atr = max(_num(x.get("ATR14"), price * .03), price * .005)
    phase = technical.get("phase", {}).get("label", "")
    structure = technical.get("structure", {}).get("label", "Neutral")
    macd = _macd_state(df)
    stoch = _stoch_state(df)
    rejection = _candle_rejection_score(df)
    pullback = _normal_pullback_score(df)
    trendline = _trendline_support(df)

    supply = entry_plan.get("nearest_supply")
    supply_low = _num((supply or {}).get("zone_low_exec"))
    supply_headroom = round((supply_low / price - 1) * 100, 2) if supply_low > price > 0 else None

    candidates: List[Dict[str, Any]] = []

    def add(setup: str, low_raw: float, high_raw: float, trigger_raw: float | None, confirmation_raw: float | None,
            stop_raw: float, setup_quality: float, entry_style: str, note: str, volume_mode: str = "pullback"):
        low = int(ceil_to_tick(max(low_raw, 1)))
        high = int(floor_to_tick(max(high_raw, low_raw)))
        if high < low:
            high = low
        trigger = int(ceil_to_tick(trigger_raw)) if trigger_raw and trigger_raw > 0 else None
        confirm = int(ceil_to_tick(confirmation_raw)) if confirmation_raw and confirmation_raw > max(high, price) else None
        stop = int(conservative_floor_to_tick(max(stop_raw, 1)))
        if stop >= low:
            stop = int(previous_tick_below(low))
        entry = int(nearest_to_tick((low + high) / 2))
        targets = _next_targets(trade_plan, entry, stop, confirm, atr)
        # Respect existing structural targets when they are sensible and higher.
        base_tps = [_num(trade_plan.get("tp1")), _num(trade_plan.get("tp2"))]
        merged = sorted(set([t for t in targets if t > entry] + [int(floor_to_tick(t)) for t in base_tps if t > entry]))
        tp1, tp2, tp3 = (merged + list(targets))[:3]
        if tp2 <= tp1:
            tp2 = targets[1]
        if tp3 <= tp2:
            tp3 = targets[2]
        rr2 = _rr(entry, stop, tp2)
        location, dist = _entry_location_score(price, low, high)
        volume = _volume_character(df, volume_mode)
        analyst_score, analyst_components = _adaptive_analyst_score(
            setup, setup_quality, location, volume, macd, stoch, rejection, pullback, trendline, rr2
        )
        edge_score, edge_components = _independent_edge_score(
            technical, context, timing_plan, entry_plan, rr2, location, supply_headroom
        )
        # Human-style reasoning is primary, but the independent layer can veto a beautiful chart
        # that has poor context/RS/RR or is already too far from entry.
        conviction = _clamp(0.62 * analyst_score + 0.38 * edge_score)
        penalties = []
        if structure == "Bearish":
            conviction = min(conviction, 42.0); penalties.append("bearish structure")
        if rr2 < 1.5:
            conviction = min(conviction, 58.0); penalties.append("RR < 1.5")
        if phase == "Overextended":
            conviction = min(conviction, 48.0); penalties.append("overextended")
        if supply_headroom is not None and supply_headroom < 1.0 and setup not in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"}:
            conviction = min(conviction, 62.0); penalties.append("supply too close")
        conviction = round(conviction, 1)
        status = _trade_status(price, low, high, analyst_score, conviction, setup, stop, phase)
        candidates.append({
            "setup": setup, "analyst_score": analyst_score, "edge_score": edge_score, "conviction": conviction,
            "status": status, "entry_style": entry_style, "entry": entry, "entry_low": low, "entry_high": high,
            "trigger": trigger, "major_confirmation": confirm, "stop": stop, "tp1": int(tp1), "tp2": int(tp2), "tp3": int(tp3),
            "rr_tp2": round(rr2, 2), "distance_pct": dist, "volume": volume, "macd": macd, "stoch": stoch,
            "rejection_score": rejection, "pullback_score": pullback, "trendline": trendline,
            "analyst_components": analyst_components, "edge_components": edge_components,
            "supply_headroom_pct": supply_headroom, "penalties": penalties, "note": note,
        })

    # Import existing Quick Pick candidates and rescore them adaptively.
    for q in quick_pick.get("candidates", []) or []:
        setup = str(q.get("setup", "NONE"))
        if setup == "PULLBACK REBOUND":
            # The dedicated support/pivot logic below is more informative.
            continue
        setup_q = _num((q.get("components") or {}).get("Setup"), q.get("score", 60))
        confirmation = q.get("major_confirmation")
        if confirmation is None and setup in {"BASE RETEST", "MA20 RECLAIM"}:
            confirmation = _nearest_overhead_level(trade_plan, price)
        add(
            setup,
            _num(q.get("entry_low"), price), _num(q.get("entry_high"), price), q.get("trigger"), confirmation,
            _num(q.get("stop"), trade_plan.get("stop_loss", price - 2*atr)), setup_q,
            "TRIGGER" if setup in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT", "MA20 RECLAIM"} else "RETEST",
            str(q.get("setup_note", "Existing Quick Pick setup.")),
            "breakout" if setup in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"} else "pullback",
        )

    # Dedicated support-hold / normal-pullback setup (AMMN-like logic).
    support = _num(trade_plan.get("support1"))
    support_low = _num(trade_plan.get("support1_zone_low"), support - .25 * atr)
    resistance = _nearest_overhead_level(trade_plan, price)
    support_dist = (price / support - 1) if support > 0 else 99
    if support > 0 and -0.008 <= support_dist <= 0.04 and structure != "Bearish" and pullback >= 58:
        setup_q = _clamp(0.35 * _num(technical.get("trade_quality"), 50) + 0.25 * pullback + 0.20 * rejection + 0.20 * macd["score"])
        add(
            "SUPPORT HOLD REBOUND", support, support + max(.45 * atr, support * .012), None, resistance,
            min(_num(trade_plan.get("stop_loss"), support_low - .4*atr), support_low - .25*atr), setup_q,
            "EARLY", "Normal pullback held near structural support; momentum is confirmation, not the trigger.", "pullback"
        )

    # Pullback pivot-hold after a recent resistance test (BUVA-like logic).
    recent_high = _num(df["High"].tail(10).max(), price) if "High" in df else price
    if support > 0 and recent_high >= price * 1.035 and -0.008 <= support_dist <= 0.035 and pullback >= 65:
        confirmation = max(resistance or 0, recent_high)
        setup_q = _clamp(0.30 * pullback + 0.25 * rejection + 0.25 * macd["score"] + 0.20 * _num(technical.get("trade_quality"), 50))
        add(
            "PULLBACK PIVOT HOLD", support, support + max(.35*atr, support*.01), None, confirmation,
            min(_num(trade_plan.get("stop_loss"), support - atr), support_low - .25*atr), setup_q,
            "EARLY", "Price pulled back after testing resistance and is holding the pivot/support area.", "pullback"
        )

    # Rising trendline support rebound (MBMA-like logic).
    if trendline.get("valid"):
        tl = _num(trendline.get("support"))
        setup_q = _clamp(0.38 * _num(trendline.get("score")) + 0.20 * pullback + 0.22 * macd["score"] + 0.20 * stoch["score"])
        confirmation = resistance or recent_high
        add(
            "TRENDLINE SUPPORT REBOUND", tl, tl + max(.45*atr, tl*.012), None, confirmation,
            tl - max(.45*atr, tl*.008), setup_q, "EARLY",
            "Price is testing a fitted multi-touch trendline support while short-term momentum is washed out/turning and medium-term momentum remains constructive.", "pullback"
        )

    if not candidates:
        return {
            "eligible": False, "conviction": 0.0, "analyst_score": 0.0, "edge_score": 0.0,
            "setup": "NONE", "status": "NO SETUP", "reason": "No setup-adaptive analyst thesis close enough to current price.",
            "candidates": [], "macd": macd, "stoch": stoch, "trendline": trendline,
        }

    status_rank = {"READY": 7, "NEAR ENTRY": 6, "WAIT BREAKOUT": 5, "WAIT RECLAIM": 5, "WAIT SUPPORT": 4, "WAIT RETEST": 3, "TOO EXTENDED": 1, "INVALIDATED": 0}
    candidates.sort(key=lambda z: (status_rank.get(z["status"], 0), z["conviction"], z["analyst_score"], z["rr_tp2"]), reverse=True)
    best = candidates[0]
    eligible = bool(best["conviction"] >= 62 and best["rr_tp2"] >= 1.5 and best["status"] not in {"TOO EXTENDED", "INVALIDATED"} and structure != "Bearish")

    if best["status"] == "READY":
        reason = f'{best["setup"]}: actionable now near the intended entry area.'
    elif best["status"] == "NEAR ENTRY":
        reason = f'{best["setup"]}: location is attractive but confirmation is not yet strong enough for READY.'
    else:
        reason = f'{best["setup"]}: {best["status"].replace("_", " ").title()} before execution.'
    if best["penalties"]:
        reason += " Caution: " + ", ".join(best["penalties"]) + "."

    return {
        "eligible": eligible,
        "conviction": best["conviction"], "analyst_score": best["analyst_score"], "edge_score": best["edge_score"],
        "setup": best["setup"], "status": best["status"], "entry_style": best["entry_style"],
        "entry": best["entry"], "entry_low": best["entry_low"], "entry_high": best["entry_high"],
        "trigger": best["trigger"], "major_confirmation": best["major_confirmation"], "stop": best["stop"],
        "tp1": best["tp1"], "tp2": best["tp2"], "tp3": best["tp3"], "rr_tp2": best["rr_tp2"],
        "distance_pct": best["distance_pct"], "volume": best["volume"], "macd": best["macd"], "stoch": best["stoch"],
        "trendline": best["trendline"], "rejection_score": best["rejection_score"], "pullback_score": best["pullback_score"],
        "analyst_components": best["analyst_components"], "edge_components": best["edge_components"],
        "supply_headroom_pct": best["supply_headroom_pct"], "penalties": best["penalties"], "note": best["note"],
        "reason": reason, "candidates": candidates,
    }
