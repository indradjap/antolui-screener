from __future__ import annotations

from typing import Any, Dict, List
import math
import pandas as pd


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def _num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _rr_score(rr: float) -> float:
    rr = max(_num(rr), 0.0)
    if rr >= 3.0:
        return 100.0
    if rr >= 2.0:
        return 75.0 + 25.0 * (rr - 2.0)
    if rr >= 1.5:
        return 50.0 + 50.0 * (rr - 1.5)
    if rr >= 1.0:
        return 20.0 + 60.0 * (rr - 1.0)
    return 20.0 * rr


def _proximity_score(price: float, low: float, high: float) -> tuple[float, float]:
    """Return (score, signed distance to zone %). Negative = below zone."""
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
    score = clamp(100.0 - dist * 14.0)
    return round(score, 1), round(signed, 2)


def _momentum_score(label: str) -> float:
    return {
        "Improving": 95.0,
        "Healthy": 82.0,
        "Weakening": 45.0,
        "Bearish": 10.0,
    }.get(str(label), 55.0)


def _volume_confirmation(kind: str, volume_ratio: float, close_location: float, flow_label: str) -> float:
    vr = max(_num(volume_ratio), 0.0)
    cl = clamp(_num(close_location, 0.5), 0.0, 1.0)
    flow = {"Accumulation": 90.0, "Neutral": 60.0, "Distribution": 20.0}.get(str(flow_label), 55.0)

    if kind in {"PATTERN PIVOT", "BREAKOUT CONFIRMATION"}:
        vol = clamp((vr / 1.5) * 100.0)
        candle = clamp((cl - 0.35) / 0.45 * 100.0)
        return round(0.50 * vol + 0.30 * candle + 0.20 * flow, 1)

    # Retest entries do not require explosive volume; they benefit from a
    # constructive close and from absence of distribution.
    if 0.55 <= vr <= 1.6:
        vol = 82.0
    elif vr < 0.55:
        vol = 68.0
    elif vr <= 2.2:
        vol = 62.0
    else:
        vol = 48.0
    candle = clamp((cl - 0.25) / 0.55 * 100.0)
    return round(0.35 * vol + 0.35 * candle + 0.30 * flow, 1)


def _supply_headroom(price: float, supply: dict | None) -> float | None:
    if not supply:
        return None
    low = _num(supply.get("zone_low_exec"))
    if low <= 0 or price <= 0:
        return None
    return round((low / price - 1.0) * 100.0, 2)


def score_candidate_timing(
    candidate: Dict[str, Any],
    df: pd.DataFrame,
    technical: Dict[str, Any],
    context: Dict[str, Any],
    phase: str,
    nearest_supply: dict | None = None,
) -> Dict[str, Any]:
    x = df.iloc[-1]
    price = _num(x.get("Close"))
    atr = _num(x.get("ATR14"), price * 0.03)
    volume_ratio = _num(x.get("Volume_ratio"), 1.0)
    close_location = _num(x.get("close_location"), 0.5)

    kind = str(candidate.get("type", "UNKNOWN"))
    low = _num(candidate.get("entry_low"))
    high = _num(candidate.get("entry_high"))
    entry = _num(candidate.get("entry"))
    stop = _num(candidate.get("stop"))
    rr = _num(candidate.get("rr_tp2"))
    entry_quality = _num(candidate.get("score"), 0.0)

    proximity, zone_dist = _proximity_score(price, low, high)
    momentum_label = technical.get("momentum", {}).get("label", "Unknown")
    momentum = _momentum_score(momentum_label)
    confirmation = _volume_confirmation(
        kind, volume_ratio, close_location,
        context.get("volume_flow", {}).get("label", "Neutral")
    )
    rrq = _rr_score(rr)

    # Current execution timing score. Entry-quality remains the anchor, but
    # current location/confirmation determines whether the setup is actionable now.
    timing = (
        0.38 * entry_quality +
        0.22 * proximity +
        0.15 * momentum +
        0.15 * confirmation +
        0.10 * rrq
    )

    structure = technical.get("structure", {}).get("label", "Neutral")
    technical_action = technical.get("action", "WAIT")
    headroom = _supply_headroom(price, nearest_supply)

    # Hard/soft penalties.
    penalties = 0.0
    reasons: List[str] = []
    if structure == "Bearish" or technical_action == "AVOID":
        penalties += 40
        reasons.append("struktur teknikal tidak mendukung long")
    if momentum_label == "Bearish":
        penalties += 20
        reasons.append("momentum bearish")
    if context.get("label") == "Headwind":
        penalties += 8
        reasons.append("market context headwind")
    if context.get("relative_strength", {}).get("label") == "Underperforming":
        penalties += 8
        reasons.append("relative strength underperform")
    if rr < 1.5:
        penalties += 15
        reasons.append("RR di bawah 1.5")
    if headroom is not None and 0 <= headroom < 1.5 and kind not in {"PATTERN PIVOT", "BREAKOUT CONFIRMATION"}:
        penalties += 8
        reasons.append("supply terlalu dekat")

    timing = clamp(timing - penalties)

    # Extension is measured against the selected entry zone and ATR, not only MA.
    above_zone = max(0.0, price - high)
    extended = (
        phase == "Overextended" or
        (high > 0 and above_zone > max(1.25 * atr, 0.045 * price))
    )
    invalidated = stop > 0 and price <= stop
    in_zone = low <= price <= high if low > 0 and high > 0 else False

    breakout_kind = kind in {"PATTERN PIVOT", "BREAKOUT CONFIRMATION"}
    breakout_confirmed = (
        breakout_kind and in_zone and
        volume_ratio >= 1.35 and close_location >= 0.60 and
        momentum_label != "Bearish"
    )
    retest_confirmed = (
        (not breakout_kind) and in_zone and
        close_location >= 0.48 and
        momentum_label in {"Improving", "Healthy"}
    )

    if invalidated:
        status = "INVALIDATED"
        timing = min(timing, 10.0)
        reason = "Harga berada di/bawah invalidation stop. Setup tidak valid."
    elif structure == "Bearish" or technical_action == "AVOID":
        status = "AVOID"
        timing = min(timing, 25.0)
        reason = "Struktur utama belum mendukung entry long."
    elif extended:
        status = "TOO EXTENDED"
        timing = min(timing, 45.0)
        reason = "Harga sudah terlalu jauh di atas area entry; jangan mengejar."
    elif breakout_kind:
        if price < low:
            status = "WAIT BREAKOUT"
            reason = "Harga belum mencapai pivot/trigger; tunggu breakout dan volume konfirmasi."
        elif breakout_confirmed and timing >= 74 and entry_quality >= 68 and rr >= 1.5:
            status = "BUY NOW"
            reason = "Harga berada di zona breakout dengan volume/candle confirmation yang memadai."
        else:
            status = "WAIT CONFIRMATION"
            reason = "Harga dekat/di trigger tetapi volume, candle, atau momentum belum cukup kuat."
    else:
        if price > high:
            status = "WAIT RETEST"
            reason = "Harga berada di atas area entry ideal; tunggu retest demand/pullback zone."
        elif price < low:
            status = "WAIT RECLAIM"
            reason = "Harga berada di bawah zona entry; tunggu reclaim sebelum entry."
        elif retest_confirmed and timing >= 74 and entry_quality >= 68 and rr >= 1.5:
            status = "BUY NOW"
            reason = "Harga berada di area demand/pullback dengan momentum dan candle yang mendukung."
        else:
            status = "WAIT CONFIRMATION"
            reason = "Harga berada dekat entry tetapi confirmation belum cukup."

    confidence = "HIGH" if timing >= 80 else ("MEDIUM" if timing >= 65 else "LOW")
    return {
        **candidate,
        "timing_score": round(timing, 1),
        "timing_status": status,
        "timing_confidence": confidence,
        "timing_reason": reason,
        "zone_distance_pct": zone_dist,
        "confirmation_score": round(confirmation, 1),
        "momentum_timing_score": round(momentum, 1),
        "proximity_timing_score": round(proximity, 1),
        "rr_timing_score": round(rrq, 1),
        "supply_headroom_pct": headroom,
        "volume_ratio": round(volume_ratio, 2),
        "close_location": round(close_location, 2),
    }


def build_timing_plan(
    df: pd.DataFrame,
    technical: Dict[str, Any],
    context: Dict[str, Any],
    pattern: Dict[str, Any],
    trade_plan: Dict[str, Any],
    entry_plan: Dict[str, Any],
) -> Dict[str, Any]:
    candidates = entry_plan.get("candidates", []) or []
    phase = technical.get("phase", {}).get("label", "")
    supply = entry_plan.get("nearest_supply")

    timed = [score_candidate_timing(c, df, technical, context, phase, supply) for c in candidates]

    # Only BUY NOW receives hard priority. For all waiting states, the highest
    # timing score wins so a nearby retest is not displaced by a distant pivot.
    timed.sort(
        key=lambda c: (1 if c["timing_status"] == "BUY NOW" else 0, c["timing_score"], c.get("score", 0)),
        reverse=True,
    )
    active = timed[0] if timed else None

    ideal = entry_plan.get("best")
    if active:
        status = active["timing_status"]
        score = active["timing_score"]
        confidence = active["timing_confidence"]
        reason = active["timing_reason"]
    else:
        status, score, confidence, reason = "NO ENTRY", 0.0, "LOW", "Tidak ada kandidat entry valid."

    return {
        "status": status,
        "score": round(score, 1),
        "confidence": confidence,
        "reason": reason,
        "active": active,
        "ideal": ideal,
        "candidates": timed,
        "buy_now": bool(status == "BUY NOW"),
    }
