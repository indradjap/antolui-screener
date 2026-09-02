from __future__ import annotations

import math
from typing import Dict, Any

from quality_universe import get_tier_info


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def _interp(x: float, points):
    """Simple linear interpolation; points must be sorted [(x,y), ...]."""
    x = float(x)
    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            w = (x - x0) / (x1 - x0)
            return float(y0 + w * (y1 - y0))
    return float(points[-1][1])


def liquidity_score(avg_value_20: float, median_value_20: float | None = None, active_ratio_20: float = 1.0) -> float:
    """0-100 liquidity score based mainly on 20D traded value in IDR."""
    avg_value_20 = max(float(avg_value_20 or 0.0), 0.0)
    if avg_value_20 <= 0:
        return 0.0

    logv = math.log10(max(avg_value_20, 1.0))
    base = _interp(logv, [
        (9.0, 0.0),
        (math.log10(5e9), 35.0),
        (math.log10(2e10), 65.0),
        (11.0, 100.0),
    ])

    if median_value_20 is not None and avg_value_20 > 0:
        med_ratio = max(float(median_value_20), 0.0) / avg_value_20
        if med_ratio < 0.35:
            base -= 15
        elif med_ratio < 0.55:
            base -= 7

    if active_ratio_20 < 0.90:
        base -= 20
    elif active_ratio_20 < 0.98:
        base -= 8

    return round(clamp(base), 1)


def rr_score(rr: float) -> float:
    rr = max(float(rr or 0.0), 0.0)
    return round(clamp(_interp(rr, [
        (0.0, 0.0),
        (0.75, 5.0),
        (1.0, 20.0),
        (1.5, 50.0),
        (2.0, 75.0),
        (3.0, 100.0),
    ])), 1)


def proximity_score(phase: str, price: float, plan: Dict[str, Any]) -> float:
    price = max(float(price), 1e-9)
    trigger = float(plan.get("breakout_trigger") or price)
    ag_lo = float(plan.get("aggressive_entry_low") or price)
    ag_hi = float(plan.get("aggressive_entry_high") or price)
    con_hi = float(plan.get("conservative_entry_high") or trigger)

    if phase == "Pre-Breakout":
        dist = max((trigger - price) / price, 0.0)
        return round(_interp(dist, [
            (0.00, 100), (0.01, 98), (0.03, 88), (0.05, 70), (0.08, 45), (0.15, 15)
        ]), 1)

    if phase == "Pullback in Uptrend":
        if ag_lo <= price <= ag_hi:
            return 100.0
        zone_mid = (ag_lo + ag_hi) / 2.0
        dist = abs(price - zone_mid) / price
        return round(_interp(dist, [
            (0.00, 100), (0.015, 92), (0.03, 75), (0.06, 48), (0.10, 20)
        ]), 1)

    if phase == "Confirmed Breakout":
        if trigger <= price <= con_hi:
            return 100.0
        dist = max((price - trigger) / trigger, 0.0)
        return round(_interp(dist, [
            (0.00, 100), (0.02, 92), (0.05, 70), (0.08, 40), (0.12, 10)
        ]), 1)

    if phase == "Trend Continuation":
        return 68.0
    if phase == "Consolidation":
        return 35.0
    if phase == "Overextended":
        return 0.0
    return 45.0


def top_candidate_eligibility(
    ticker: str,
    scanner_score: float,
    avg_value_20: float,
    rr2: float,
    structure: str,
    momentum: str,
) -> Dict[str, Any]:
    """Apply tier-dependent trust/quality guardrails.

    Tier C is intentionally strict: score >= 85, >= Rp10B/day, RR2 >= 2,
    bullish structure, and non-bearish momentum. Unclassified names are also
    held to stricter rules so unknown tickers cannot jump to the top too easily.
    """
    info = get_tier_info(ticker)
    tier = info["tier"]
    min_score = float(info["top_min_score"])
    min_liq = float(info["min_liquidity_rpb"]) * 1e9
    min_rr = float(info["min_rr2"])

    reasons = []
    if scanner_score < min_score:
        reasons.append(f"score < {min_score:.0f}")
    if avg_value_20 < min_liq:
        reasons.append(f"liquidity < Rp{min_liq/1e9:.0f}B/day")
    if rr2 < min_rr:
        reasons.append(f"RR2 < {min_rr:.1f}")

    if tier in {"C", "U"}:
        if structure != "Bullish":
            reasons.append("needs Bullish structure")
        if momentum == "Bearish":
            reasons.append("bearish momentum")

    eligible = len(reasons) == 0
    return {
        "eligible": eligible,
        "tier": tier,
        "profile": info["profile"],
        "rule": "PASS" if eligible else "; ".join(reasons),
        "min_score": min_score,
        "min_liquidity_rpb": float(info["min_liquidity_rpb"]),
        "min_rr2": min_rr,
    }


def rank_candidate(
    technical: Dict[str, Any],
    context: Dict[str, Any],
    decision: Dict[str, Any],
    plan: Dict[str, Any],
    liquidity: Dict[str, Any],
    ticker: str = "UNKNOWN",
    pattern: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    tech = float(technical.get("trade_quality", 0))
    ctx = float(context.get("score", 0))
    liq = float(liquidity.get("score", 0))
    rr2 = float(plan.get("rr_tp2", 0) or 0)
    rr = rr_score(rr2)
    prox = proximity_score(technical["phase"]["label"], technical["price"], plan)

    pattern = pattern or {"label": "None", "score": 50.0, "status": "NONE", "priority_candidate": False}
    pat = float(pattern.get("score", 50.0) or 50.0)
    rs_score = float(context.get("combined_relative_strength", context.get("relative_strength", {})).get("score", 50.0) or 50.0)

    # V5.3: pattern-aware scoring. Pattern gets meaningful weight without
    # allowing a pretty chart pattern to override weak liquidity/context/RR.
    # Total = 100%.
    base_raw = (
        0.35 * tech +
        0.15 * ctx +
        0.20 * pat +
        0.10 * rs_score +
        0.10 * liq +
        0.07 * rr +
        0.03 * prox
    )

    penalty = 0.0
    if context.get("label") == "Headwind":
        penalty += 8
    if context.get("relative_strength", {}).get("label") == "Underperforming":
        penalty += 6
    if context.get("sector_relative_strength") and context.get("sector_relative_strength", {}).get("label") == "Underperforming":
        penalty += 3
    if technical.get("momentum", {}).get("label") == "Bearish":
        penalty += 15
    elif technical.get("momentum", {}).get("label") == "Weakening":
        penalty += 3
    if technical.get("phase", {}).get("label") == "Overextended":
        penalty += 20
    if technical.get("structure", {}).get("label") == "Bearish":
        penalty += 30

    # Pattern-specific risk guardrails.
    if pattern.get("label") == "High Tight Flag":
        penalty += 5
    if pattern.get("label") == "Volatility Squeeze" and technical.get("structure", {}).get("label") != "Bullish":
        penalty += 4

    # False-breakout guardrail: a breakout pattern without enough volume should
    # not receive full pattern credit in ranking.
    if pattern.get("status") == "BREAKOUT" and float(liquidity.get("score", 0) or 0) < 35:
        penalty += 5

    bonus = 3.0 if decision.get("final_action") == "BUY CANDIDATE" else 0.0
    base_score = clamp(base_raw - penalty + bonus)

    tier_info = get_tier_info(ticker)
    tier_adjustment = float(tier_info["adjustment"])
    score = clamp(base_score + tier_adjustment)

    if score >= 85:
        grade = "A+"
    elif score >= 78:
        grade = "A"
    elif score >= 70:
        grade = "B+"
    elif score >= 62:
        grade = "B"
    elif score >= 55:
        grade = "C"
    else:
        grade = "D"

    phase = technical.get("phase", {}).get("label", "")
    action = decision.get("final_action", "WAIT")
    super_setup = bool(pattern.get("super_setup", False))
    priority_setup = bool(
        pattern.get("priority_candidate", False) and
        score >= 82 and
        technical.get("structure", {}).get("label") == "Bullish" and
        technical.get("momentum", {}).get("label") != "Bearish" and
        context.get("relative_strength", {}).get("label") != "Underperforming" and
        rr2 >= 2.0
    )

    if super_setup and priority_setup:
        setup_status = "SUPER SETUP"
    elif priority_setup:
        setup_status = "PRIORITY SETUP"
    elif action == "BUY CANDIDATE":
        setup_status = "ACTIONABLE"
    elif pattern.get("status") == "BREAKOUT":
        setup_status = "PATTERN BREAKOUT"
    elif pattern.get("label") in {"VCP", "Early VCP", "Flat Base", "Cup & Handle", "Darvas Box", "Bull Flag", "High Tight Flag", "Volatility Squeeze", "Ascending Triangle"}:
        setup_status = "WATCH PATTERN"
    elif pattern.get("label") in {"EMA20/50 Golden Cross", "EMA50/200 Golden Cross"}:
        setup_status = "GOLDEN CROSS"
    elif pattern.get("label") == "Pre-Golden Cross":
        setup_status = "PRE-GOLDEN CROSS"
    elif phase == "Pre-Breakout":
        setup_status = "WATCH BREAKOUT"
    elif phase == "Pullback in Uptrend":
        setup_status = "WATCH PULLBACK"
    elif phase == "Confirmed Breakout":
        setup_status = "RECHECK BREAKOUT"
    elif phase == "Trend Continuation":
        setup_status = "TREND WATCH"
    else:
        setup_status = "WATCH"

    eligibility = top_candidate_eligibility(
        ticker=ticker,
        scanner_score=score,
        avg_value_20=float(liquidity.get("avg_value_20", 0) or 0),
        rr2=rr2,
        structure=technical.get("structure", {}).get("label", "Neutral"),
        momentum=technical.get("momentum", {}).get("label", "Healthy"),
    )

    return {
        "scanner_score": round(score, 1),
        "base_scanner_score": round(base_score, 1),
        "grade": grade,
        "setup_status": setup_status,
        "priority_setup": priority_setup,
        "super_setup": super_setup,
        "pattern_score": round(pat, 1),
        "rs_score_component": round(rs_score, 1),
        "liquidity_score": round(liq, 1),
        "rr_score": round(rr, 1),
        "proximity_score": round(prox, 1),
        "penalty": round(penalty, 1),
        "tier": tier_info["tier"],
        "tier_profile": tier_info["profile"],
        "tier_adjustment": tier_adjustment,
        "top_eligible": eligibility["eligible"],
        "tier_rule": eligibility["rule"],
        "tier_min_score": eligibility["min_score"],
        "tier_min_liquidity_rpb": eligibility["min_liquidity_rpb"],
        "tier_min_rr2": eligibility["min_rr2"],
    }
