from __future__ import annotations

from typing import Any, Dict, List
import math
import pandas as pd

from idx_ticks import ceil_to_tick, floor_to_tick, nearest_to_tick, conservative_floor_to_tick


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def _num(v, default=0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _rr(entry: float, stop: float, target: float) -> float:
    risk = float(entry) - float(stop)
    if risk <= 0:
        return 0.0
    return max(0.0, (float(target) - float(entry)) / risk)


def _rr_score(rr: float) -> float:
    rr = max(_num(rr), 0.0)
    if rr >= 4.0:
        return 100.0
    if rr >= 3.0:
        return 90.0 + (rr - 3.0) * 10.0
    if rr >= 2.0:
        return 72.0 + (rr - 2.0) * 18.0
    if rr >= 1.5:
        return 50.0 + (rr - 1.5) * 44.0
    if rr >= 1.0:
        return 25.0 + (rr - 1.0) * 50.0
    return rr * 25.0


def _distance_to_zone(price: float, low: float, high: float) -> tuple[float, float]:
    """Return (proximity score, signed distance %). Positive = above zone."""
    price = max(_num(price), 1e-9)
    low, high = _num(low), _num(high)
    if low > high:
        low, high = high, low
    if low <= price <= high:
        return 100.0, 0.0
    if price < low:
        dist = (low / price - 1.0) * 100.0
        signed = -dist
    else:
        dist = (price / high - 1.0) * 100.0
        signed = dist
    return round(clamp(100.0 - dist * 18.0), 1), round(signed, 2)


def _volume_score(vr: float, close_location: float, breakout: bool) -> float:
    vr = max(_num(vr), 0.0)
    cl = clamp(_num(close_location, 0.5), 0.0, 1.0)
    if vr >= 2.0:
        vol = 100.0
    elif vr >= 1.5:
        vol = 88.0 + 24.0 * (vr - 1.5)
    elif vr >= 1.2:
        vol = 70.0 + 60.0 * (vr - 1.2)
    elif vr >= 1.0:
        vol = 58.0 + 60.0 * (vr - 1.0)
    elif vr >= 0.8:
        vol = 42.0 + 80.0 * (vr - 0.8)
    else:
        vol = max(15.0, vr / 0.8 * 42.0)

    if breakout:
        candle = clamp((cl - 0.35) / 0.45 * 100.0)
        return round(0.75 * vol + 0.25 * candle, 1)
    # Retests can be healthy on quieter volume; constructive closing location matters.
    if 0.65 <= vr <= 1.35:
        vol = max(vol, 78.0)
    candle = clamp((cl - 0.25) / 0.55 * 100.0)
    return round(0.55 * vol + 0.45 * candle, 1)


def _stoch_signal(x: pd.Series, prev: pd.Series) -> tuple[str, float]:
    k = _num(x.get("StochRSI_K"), 50.0)
    d = _num(x.get("StochRSI_D"), 50.0)
    pk = _num(prev.get("StochRSI_K"), k)
    pd_ = _num(prev.get("StochRSI_D"), d)
    cross_up = pk <= pd_ and k > d
    cross_down = pk >= pd_ and k < d
    if cross_up and k <= 80:
        return "BULLISH CROSS", 95.0
    if k > d and k < 85:
        return "BULLISH", 80.0
    if cross_down:
        return "BEARISH CROSS", 25.0
    if k >= 90:
        return "OVERBOUGHT", 55.0
    return "NEUTRAL", 55.0


def _momentum_score(df: pd.DataFrame, technical: dict) -> tuple[float, str]:
    x = df.iloc[-1]
    p = df.iloc[-2] if len(df) > 1 else x
    label = technical.get("momentum", {}).get("label", "Unknown")
    base = {"Improving": 92.0, "Healthy": 80.0, "Weakening": 45.0, "Bearish": 15.0}.get(label, 55.0)
    rsi = _num(x.get("RSI14"), 50.0)
    macd_bonus = 8.0 if _num(x.get("MACD")) > _num(x.get("MACD_signal")) else -5.0
    rsi_bonus = 7.0 if 50 <= rsi <= 70 else (2.0 if 45 <= rsi < 50 else (-6.0 if rsi < 40 else -2.0))
    stoch_label, stoch_score = _stoch_signal(x, p)
    score = clamp(0.72 * base + 0.18 * stoch_score + macd_bonus + rsi_bonus)
    return round(score, 1), stoch_label


def _days_since_ma20_reclaim(df: pd.DataFrame, lookback: int = 5) -> int | None:
    if "MA20" not in df or len(df) < 2:
        return None
    n = min(lookback, len(df) - 1)
    for days in range(0, n):
        i = len(df) - 1 - days
        if i <= 0:
            break
        cur = df.iloc[i]
        prev = df.iloc[i - 1]
        if _num(prev.get("Close")) <= _num(prev.get("MA20")) and _num(cur.get("Close")) > _num(cur.get("MA20")):
            return days
    return None


def _strong_resistances(trade_plan: dict, floor_price: float) -> List[dict]:
    levels = trade_plan.get("level_engine", {}).get("all_levels", []) or []
    out = []
    for lvl in levels:
        center = _num(lvl.get("center"))
        if center <= floor_price:
            continue
        touches = max(int(lvl.get("touches", 0) or 0), 1)
        high_ratio = _num(lvl.get("high_touches"), 0.0) / touches
        score = _num(lvl.get("score"), 0.0)
        if score >= 28 and high_ratio >= 0.35:
            out.append(lvl)
    out.sort(key=lambda z: (_num(z.get("center")), -_num(z.get("score"))))
    return out


def _major_confirmation(trade_plan: dict, trigger: float, atr: float, tp1: float, tp2: float) -> int | None:
    # A major confirmation is a stronger overhead structural barrier after the
    # initial trigger. It is not forced: some setups simply do not have one.
    min_gap = max(0.75 * atr, trigger * 0.018)
    levels = _strong_resistances(trade_plan, trigger + min_gap)
    strong = [x for x in levels if _num(x.get("score")) >= 38]
    pool = strong or levels
    # Confirmation should occur before/around TP2; a barrier far beyond the main
    # target is not useful as an in-trade continuation checkpoint.
    pool = [x for x in pool if tp2 <= 0 or _num(x.get("center")) <= tp2 * 1.02]
    if not pool:
        return None
    # Prefer a meaningful barrier around/above TP1, otherwise the nearest strong one.
    around_tp1 = [x for x in pool if _num(x.get("center")) >= tp1 * 0.985]
    chosen = around_tp1[0] if around_tp1 else pool[0]
    return int(ceil_to_tick(_num(chosen.get("center"))))


def _third_target(trade_plan: dict, entry: float, stop: float, tp2: float, atr: float) -> int:
    levels = _strong_resistances(trade_plan, tp2 + max(0.30 * atr, tp2 * 0.008))
    if levels:
        return int(floor_to_tick(_num(levels[0].get("center"))))
    risk = max(entry - stop, atr, entry * 0.02)
    fallback = max(entry + 4.0 * risk, tp2 + atr)
    return int(floor_to_tick(fallback))


def _setup_status(kind: str, price: float, low: float, high: float, quick_score: float,
                  confirmation: float, phase: str, atr: float, stop: float) -> tuple[str, str]:
    if stop > 0 and price <= stop:
        return "INVALIDATED", "Harga sudah menembus invalidation level."
    if phase == "Overextended" or price > high + max(1.2 * atr, high * 0.045):
        return "TOO EXTENDED", "Harga sudah terlalu jauh dari area entry; hindari mengejar."

    breakout = kind in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"}
    reclaim = kind == "MA20 RECLAIM"
    retest = kind in {"BASE RETEST", "PULLBACK REBOUND"}

    if low <= price <= high:
        if quick_score >= 74 and confirmation >= 64:
            return "READY", "Harga berada di area entry dan konfirmasi sudah memadai."
        return "NEAR ENTRY", "Harga sudah di area entry, tetapi konfirmasi belum cukup kuat."

    if price < low:
        if reclaim:
            return "WAIT RECLAIM", "Tunggu harga reclaim MA20/entry zone."
        if breakout:
            return "WAIT BREAKOUT", "Tunggu harga mencapai dan menembus trigger."
        return "WAIT RECLAIM", "Harga masih di bawah area setup; tunggu reclaim."

    # Slightly above a breakout trigger can still be actionable if confirmation is strong.
    dist = (price / max(high, 1e-9) - 1.0) * 100.0
    if breakout and dist <= 2.0 and quick_score >= 76 and confirmation >= 72:
        return "READY", "Breakout baru terjadi dan masih dekat trigger dengan konfirmasi kuat."
    if reclaim and dist <= 2.0 and quick_score >= 74 and confirmation >= 64:
        return "READY", "MA20 reclaim terkonfirmasi dan harga belum terlalu jauh."
    if retest:
        return "WAIT RETEST", "Harga sudah di atas area entry ideal; tunggu retest."
    return "NEAR ENTRY", "Harga sedikit di atas trigger; tunggu entry yang lebih efisien bila perlu."


def _candidate_score(kind: str, setup_quality: float, proximity: float, volume: float,
                     momentum: float, rs: float, rr: float, context_score: float,
                     phase: str, structure: str, supply_headroom: float | None) -> tuple[float, dict]:
    # Quick Pick is execution-oriented: setup + location + confirmation dominate.
    score = (
        0.28 * setup_quality +
        0.20 * proximity +
        0.16 * volume +
        0.12 * momentum +
        0.10 * rs +
        0.09 * _rr_score(rr) +
        0.05 * context_score
    )
    penalties = 0.0
    if phase == "Overextended":
        penalties += 20
    if structure == "Bearish":
        penalties += 30
    if rr < 1.5:
        penalties += 15
    if kind in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"} and volume < 55:
        penalties += 10
    if supply_headroom is not None and 0 <= supply_headroom < 1.5 and kind not in {"PIVOT BREAKOUT", "RESISTANCE BREAKOUT"}:
        penalties += 10
    out = clamp(score - penalties)
    return round(out, 1), {
        "Setup": round(setup_quality, 1), "Location": round(proximity, 1),
        "Volume": round(volume, 1), "Momentum": round(momentum, 1),
        "RS": round(rs, 1), "RR": round(rr, 2), "Context": round(context_score, 1),
        "Penalty": round(penalties, 1),
    }


def build_quick_pick(
    df: pd.DataFrame,
    technical: Dict[str, Any],
    context: Dict[str, Any],
    pattern: Dict[str, Any],
    trade_plan: Dict[str, Any],
    entry_plan: Dict[str, Any],
    timing_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an execution-first stock-pick plan from the existing Antolui engine.

    The engine deliberately treats price structure as primary. Momentum, StochRSI
    and volume confirm a setup; they do not create a trade by themselves.
    """
    if df is None or len(df) < 2:
        return {"eligible": False, "score": 0.0, "setup": "NONE", "status": "NO SETUP", "candidates": []}

    x = df.iloc[-1]
    p = df.iloc[-2]
    price = _num(x.get("Close"))
    atr = max(_num(x.get("ATR14"), price * 0.03), price * 0.005)
    ma20 = _num(x.get("MA20"))
    prev_high20 = _num(x.get("PrevHigh20"))
    volume_ratio = _num(x.get("Volume_ratio"), 1.0)
    close_location = _num(x.get("close_location"), 0.5)
    phase = technical.get("phase", {}).get("label", "")
    structure = technical.get("structure", {}).get("label", "Neutral")
    tech_quality = _num(technical.get("trade_quality"), 50.0)
    pat_score = _num(pattern.get("score"), 50.0)
    rs = _num(context.get("combined_relative_strength", context.get("relative_strength", {})).get("score"), 50.0)
    ctx = _num(context.get("score"), 50.0)
    momentum, stoch_label = _momentum_score(df, technical)
    supply = entry_plan.get("nearest_supply")
    supply_low = _num(supply.get("zone_low_exec")) if supply else 0.0
    supply_headroom = round((supply_low / price - 1.0) * 100.0, 2) if supply_low > price > 0 else None

    base_stop = int(trade_plan.get("stop_loss", 0) or 0)
    tp1 = int(trade_plan.get("tp1", 0) or 0)
    tp2 = int(trade_plan.get("tp2", 0) or 0)
    trigger = int(trade_plan.get("breakout_trigger", 0) or 0)
    pivot = _num(pattern.get("pivot"), 0.0)
    candidates: List[Dict[str, Any]] = []

    base_labels = {"Bull Flag", "Darvas Box", "Flat Base", "VCP", "Early VCP", "Ascending Triangle", "Cup & Handle"}
    pivot_trigger = pivot if pivot > 0 else (float(trigger) if trigger > 0 else 0.0)
    recent_max_15 = _num(df["High"].tail(15).max(), price) if "High" in df else price
    base_retest_active = bool(
        pattern.get("label") in base_labels and pivot_trigger > 0 and
        recent_max_15 >= pivot_trigger * 1.02 and abs(price / pivot_trigger - 1.0) <= 0.035
    )

    def add_candidate(kind: str, low_raw: float, high_raw: float, trigger_raw: float | None,
                      stop_raw: float, setup_quality: float, breakout: bool, note: str):
        low = int(ceil_to_tick(max(low_raw, 1.0)))
        high = int(floor_to_tick(max(high_raw, low_raw)))
        if high < low:
            high = low
        trig = int(ceil_to_tick(trigger_raw)) if trigger_raw and trigger_raw > 0 else None
        stop = int(conservative_floor_to_tick(max(stop_raw, 1.0)))
        if stop >= low:
            stop = int(conservative_floor_to_tick(max(low - max(0.45 * atr, low * 0.006), 1.0)))
        entry_ref = high if breakout else int(nearest_to_tick((low + high) / 2.0))
        rr2 = _rr(entry_ref, stop, tp2)
        prox, signed_dist = _distance_to_zone(price, low, high)
        vol = _volume_score(volume_ratio, close_location, breakout)
        score, comps = _candidate_score(
            kind, setup_quality, prox, vol, momentum, rs, rr2, ctx,
            phase, structure, supply_headroom,
        )
        status, reason = _setup_status(kind, price, low, high, score, vol, phase, atr, stop)
        major = _major_confirmation(trade_plan, trig or high, atr, tp1, tp2)
        tp3 = _third_target(trade_plan, entry_ref, stop, tp2, atr)
        candidates.append({
            "setup": kind, "score": score, "status": status, "entry_low": low,
            "entry_high": high, "entry": entry_ref, "trigger": trig,
            "major_confirmation": major, "stop": stop, "tp1": tp1, "tp2": tp2,
            "tp3": tp3, "rr_tp2": round(rr2, 2), "distance_pct": signed_dist,
            "volume_score": vol, "volume_ratio": round(volume_ratio, 2),
            "momentum_score": momentum, "stoch_rsi": stoch_label,
            "components": comps, "reason": reason, "setup_note": note,
        })

    # 1) Pattern / pivot breakout. Allow anticipatory entry immediately below pivot.
    # If price has already moved materially above the pivot and returned, classify it
    # as BASE RETEST instead of incorrectly calling the old pivot a fresh breakout.
    if pivot_trigger > 0 and not base_retest_active and -0.06 <= (price / pivot_trigger - 1.0) <= 0.055:
        low_raw = pivot_trigger - max(0.45 * atr, pivot_trigger * 0.008)
        setup_q = clamp(0.70 * pat_score + 0.30 * tech_quality)
        add_candidate(
            "PIVOT BREAKOUT", low_raw, pivot_trigger, pivot_trigger, base_stop,
            setup_q, True, f'{pattern.get("label","Pattern")} pivot / structural breakout.'
        )

    # 2) MA20 reclaim, useful for rebound setups. The reclaim must be recent or price
    # still very close to MA20; momentum indicators are confirmation only.
    reclaim_days = _days_since_ma20_reclaim(df, 6)
    ma20_dist = (price / ma20 - 1.0) if ma20 > 0 else 99.0
    if ma20 > 0 and ((reclaim_days is not None and reclaim_days <= 3) or (0 <= ma20_dist <= 0.025)):
        local_low = _num(df["Low"].tail(6).min(), ma20 - atr) if "Low" in df else ma20 - atr
        stop_raw = min(ma20 - 0.45 * atr, local_low - 0.15 * atr)
        stop_raw = max(stop_raw, price - 2.5 * atr)
        low_raw = ma20
        high_raw = ma20 + max(0.35 * atr, ma20 * 0.018)
        setup_q = clamp(0.60 * tech_quality + 0.20 * momentum + 0.20 * (90 if reclaim_days is not None else 70))
        add_candidate(
            "MA20 RECLAIM", low_raw, high_raw, ma20, stop_raw, setup_q, False,
            f'MA20 reclaim {"today" if reclaim_days == 0 else str(reclaim_days)+"d ago" if reclaim_days is not None else "nearby"}; momentum confirmation {stoch_label}.'
        )

    # 3) Base / pennant retest. Detect return to a still-valid pivot after trading above it.
    if base_retest_active:
        low_raw = pivot_trigger - max(0.55 * atr, pivot_trigger * 0.012)
        high_raw = pivot_trigger + max(0.20 * atr, pivot_trigger * 0.006)
        setup_q = clamp(0.75 * pat_score + 0.25 * tech_quality)
        add_candidate(
            "BASE RETEST", low_raw, high_raw, pivot_trigger, base_stop,
            setup_q, False, f'Retest of existing {pattern.get("label")} base/pivot after a prior move above it.'
        )

    # 4) Generic 20D resistance breakout when no named pattern is required.
    duplicate_named_pivot = bool(pivot > 0 and prev_high20 > 0 and abs(prev_high20 / pivot - 1.0) <= 0.015)
    if prev_high20 > 0 and not base_retest_active and not duplicate_named_pivot:
        dist_prev = price / prev_high20 - 1.0
        crossed_recently = _num(p.get("Close")) <= _num(p.get("PrevHigh20"), prev_high20) and price > prev_high20
        if -0.025 <= dist_prev <= 0.035 or crossed_recently:
            low_raw = prev_high20 - max(0.35 * atr, prev_high20 * 0.006)
            setup_q = clamp(0.60 * tech_quality + 0.20 * pat_score + 20.0)
            add_candidate(
                "RESISTANCE BREAKOUT", low_raw, prev_high20, prev_high20, base_stop,
                setup_q, True, "Break/retest of prior 20D structural resistance."
            )

    # 5) Pullback rebound around MA20/MA50 or demand. It is intentionally last
    # priority because Quick Pick should prefer clear trigger-style setups.
    demand = entry_plan.get("nearest_demand")
    demand_low = _num(demand.get("zone_low_exec")) if demand else 0.0
    demand_high = _num(demand.get("zone_high_exec")) if demand else 0.0
    near_ma20 = ma20 > 0 and abs(price / ma20 - 1.0) <= 0.025
    in_demand = demand_low > 0 and demand_low * 0.99 <= price <= demand_high * 1.02
    if (near_ma20 or in_demand) and structure != "Bearish" and technical.get("momentum", {}).get("label") in {"Improving", "Healthy"}:
        if in_demand:
            low_raw, high_raw = demand_low, demand_high
            zone_q = _num(demand.get("score"), 60.0)
            note = "Rebound/retest inside detected demand zone."
        else:
            low_raw = ma20 - 0.35 * atr
            high_raw = ma20 + 0.35 * atr
            zone_q = 60.0
            note = "Pullback rebound around MA20 confluence."
        setup_q = clamp(0.55 * tech_quality + 0.20 * pat_score + 0.25 * zone_q)
        add_candidate("PULLBACK REBOUND", low_raw, high_raw, None, base_stop, setup_q, False, note)

    if not candidates:
        return {
            "eligible": False, "score": 0.0, "setup": "NONE", "status": "NO SETUP",
            "entry": None, "entry_low": None, "entry_high": None, "trigger": None,
            "major_confirmation": None, "stop": None, "tp1": tp1, "tp2": tp2, "tp3": None,
            "rr_tp2": 0.0, "volume_ratio": round(volume_ratio, 2), "volume_label": "N/A",
            "stoch_rsi": stoch_label, "reason": "Tidak ada actionable trigger/retest setup yang dekat harga saat ini.",
            "candidates": [],
        }

    status_priority = {"READY": 6, "NEAR ENTRY": 5, "WAIT BREAKOUT": 4, "WAIT RECLAIM": 3, "WAIT RETEST": 2, "TOO EXTENDED": 1, "INVALIDATED": 0}
    setup_priority = {"PIVOT BREAKOUT": 5, "MA20 RECLAIM": 4, "BASE RETEST": 4, "RESISTANCE BREAKOUT": 3, "PULLBACK REBOUND": 2}
    candidates.sort(key=lambda c: (status_priority.get(c["status"], 0), c["score"], setup_priority.get(c["setup"], 0), c["rr_tp2"]), reverse=True)
    best = candidates[0]

    vr = best["volume_ratio"]
    if vr >= 2.0:
        volume_label = "STRONG"
    elif vr >= 1.5:
        volume_label = "GOOD"
    elif vr >= 1.0:
        volume_label = "NORMAL"
    else:
        volume_label = "WEAK"

    eligible = bool(
        best["score"] >= 60 and best["rr_tp2"] >= 1.25 and
        best["status"] not in {"TOO EXTENDED", "INVALIDATED"} and structure != "Bearish"
    )

    return {
        "eligible": eligible,
        "score": best["score"],
        "setup": best["setup"],
        "status": best["status"],
        "entry": best["entry"],
        "entry_low": best["entry_low"],
        "entry_high": best["entry_high"],
        "trigger": best["trigger"],
        "major_confirmation": best["major_confirmation"],
        "stop": best["stop"],
        "tp1": best["tp1"],
        "tp2": best["tp2"],
        "tp3": best["tp3"],
        "rr_tp2": best["rr_tp2"],
        "distance_pct": best["distance_pct"],
        "volume_ratio": best["volume_ratio"],
        "volume_score": best["volume_score"],
        "volume_label": volume_label,
        "momentum_score": best["momentum_score"],
        "stoch_rsi": best["stoch_rsi"],
        "reason": best["reason"],
        "setup_note": best["setup_note"],
        "components": best["components"],
        "candidates": candidates,
    }
