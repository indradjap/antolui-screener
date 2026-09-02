from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
import pandas as pd

from idx_ticks import ceil_to_tick, floor_to_tick, nearest_to_tick, previous_tick_below
from supply_demand import discover_supply_demand


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def _rr(entry, stop, target):
    if None in (entry, stop, target):
        return 0.0
    risk = float(entry) - float(stop)
    if risk <= 0:
        return 0.0
    return max(0.0, (float(target) - float(entry)) / risk)


def _candidate_score(kind: str, entry: float, low: float, high: float, stop: float, tp2: float,
                     price: float, technical: dict, context: dict, pattern: dict,
                     zone_score: float = 0.0) -> tuple[float, Dict[str, float]]:
    tech = float(technical.get("trade_quality", 50))
    pat = float(pattern.get("score", 0))
    rs = float(context.get("relative_strength", {}).get("score", 50))
    ctx = float(context.get("score", 50))
    rr = _rr(entry, stop, tp2)
    rr_score = clamp((rr / 3.0) * 100)

    dist = abs(entry / price - 1.0) * 100 if price > 0 else 99
    proximity = clamp(100 - dist * 13)

    # Supply/demand quality matters most for retest entries; pattern quality matters
    # most for breakout/pivot entries. This avoids one-size-fits-all scoring.
    if kind == "DEMAND RETEST":
        score = 0.24*tech + 0.24*zone_score + 0.15*rs + 0.12*ctx + 0.10*pat + 0.10*rr_score + 0.05*proximity
    elif kind in ("PATTERN PIVOT", "BREAKOUT CONFIRMATION"):
        score = 0.23*tech + 0.23*pat + 0.16*rs + 0.12*ctx + 0.08*zone_score + 0.13*rr_score + 0.05*proximity
    else:
        score = 0.28*tech + 0.16*pat + 0.15*rs + 0.12*ctx + 0.14*zone_score + 0.10*rr_score + 0.05*proximity

    # Guardrails.
    if technical.get("structure", {}).get("label") == "Bearish":
        score -= 30
    if technical.get("momentum", {}).get("label") == "Bearish":
        score -= 15
    if technical.get("phase", {}).get("label") == "Overextended" and kind != "DEMAND RETEST":
        score -= 18
    if rr < 1.5:
        score -= 12
    if dist > 8:
        score -= min(15, (dist - 8) * 1.5)

    components = {
        "Technical": round(tech,1), "Pattern": round(pat,1), "RS": round(rs,1),
        "Context": round(ctx,1), "Zone": round(zone_score,1), "RR": round(rr,2),
        "Proximity": round(proximity,1)
    }
    return round(clamp(score), 1), components


def build_entry_plan(df: pd.DataFrame, technical: dict, context: dict, pattern: dict, trade_plan: dict) -> Dict[str, Any]:
    x = df.iloc[-1]
    price = float(x["Close"])
    atr = float(x.get("ATR14", price*0.03))
    if not np.isfinite(atr) or atr <= 0:
        atr = price*0.03

    sd = discover_supply_demand(df)
    demand = sd.get("nearest_demand")
    supply = sd.get("nearest_supply")
    tp2 = int(trade_plan["tp2"])
    candidates: List[Dict[str, Any]] = []

    # 1) Demand retest candidate.
    if demand:
        low = int(demand["zone_low_exec"])
        high = int(demand["zone_high_exec"])
        # Prefer proximal half of a strong demand zone instead of blindly using midpoint.
        ideal_raw = 0.65*float(demand["proximal"]) + 0.35*float(demand["distal"])
        ideal = int(nearest_to_tick(ideal_raw))
        ideal = max(low, min(high, ideal))
        stop = int(floor_to_tick(float(demand["distal"]) - max(0.35*atr, price*0.005)))
        if stop >= ideal:
            stop = max(previous_tick_below(ideal), 1)
        score, comps = _candidate_score(
            "DEMAND RETEST", ideal, low, high, stop, tp2, price,
            technical, context, pattern, float(demand.get("score",0))
        )
        candidates.append({
            "type":"DEMAND RETEST", "entry":ideal, "entry_low":low, "entry_high":high,
            "stop":stop, "score":score, "rr_tp2":round(_rr(ideal,stop,tp2),2),
            "components":comps,
            "reason":f'Demand zone score {demand.get("score",0):.0f}, departure {demand.get("departure_atr",0):.1f} ATR, retest {demand.get("retests",0)}x.'
        })

    # 2) Existing support/MA pullback candidate.
    low = int(trade_plan["aggressive_entry_low"])
    high = int(trade_plan["aggressive_entry_high"])
    ideal = int(nearest_to_tick((low + high)/2))
    stop = int(trade_plan["stop_loss"])
    zone_score = float(demand.get("score",0)) if demand and not (high < demand["zone_low_exec"] or low > demand["zone_high_exec"]) else 45.0
    score, comps = _candidate_score("PULLBACK CONFLUENCE", ideal, low, high, stop, tp2, price, technical, context, pattern, zone_score)
    candidates.append({
        "type":"PULLBACK CONFLUENCE", "entry":ideal, "entry_low":low, "entry_high":high,
        "stop":stop, "score":score, "rr_tp2":round(_rr(ideal,stop,tp2),2), "components":comps,
        "reason":"Support/MA/ATR pullback zone from the technical level engine."
    })

    # 3) Pattern pivot candidate when a valid pattern exists.
    pivot = pattern.get("pivot")
    if pivot is not None and float(pivot) > 0:
        trigger = int(ceil_to_tick(float(pivot)))
        low = trigger
        high = int(ceil_to_tick(trigger + 0.30*atr))
        stop = int(trade_plan["stop_loss"])
        supply_score = float(supply.get("score",0)) if supply and supply["zone_low_exec"] <= trigger <= supply["zone_high_exec"] else 50.0
        # Supply at the pivot is not a positive zone score; a strong overhead supply
        # requires stronger breakout confirmation, so invert it modestly.
        zone_quality = max(0.0, 70.0 - 0.45*supply_score) if supply_score > 50 else 55.0
        score, comps = _candidate_score("PATTERN PIVOT", trigger, low, high, stop, tp2, price, technical, context, pattern, zone_quality)
        candidates.append({
            "type":"PATTERN PIVOT", "entry":trigger, "entry_low":low, "entry_high":high,
            "stop":stop, "score":score, "rr_tp2":round(_rr(trigger,stop,tp2),2), "components":comps,
            "reason":f'{pattern.get("label","Pattern")} pivot with pattern score {pattern.get("score",0):.0f}.'
        })

    # 4) Generic confirmed breakout candidate.
    low = int(trade_plan["conservative_entry_low"])
    high = int(trade_plan["conservative_entry_high"])
    ideal = low
    stop = int(trade_plan["stop_loss"])
    overhead_penalty_score = 55.0
    if supply and supply["zone_low_exec"] <= low <= supply["zone_high_exec"]:
        overhead_penalty_score = max(10.0, 65.0 - 0.55*float(supply.get("score",0)))
    score, comps = _candidate_score("BREAKOUT CONFIRMATION", ideal, low, high, stop, tp2, price, technical, context, pattern, overhead_penalty_score)
    candidates.append({
        "type":"BREAKOUT CONFIRMATION", "entry":ideal, "entry_low":low, "entry_high":high,
        "stop":stop, "score":score, "rr_tp2":round(_rr(ideal,stop,tp2),2), "components":comps,
        "reason":"Breakout above intelligent resistance/trigger; volume confirmation remains required."
    })

    # Remove nonsensical candidates and rank by confluence score.
    candidates = [c for c in candidates if c["entry"] > c["stop"] and c["entry_low"] <= c["entry_high"]]
    candidates.sort(key=lambda c: (c["score"], c["rr_tp2"]), reverse=True)

    best = candidates[0] if candidates else None
    if best:
        conf = "HIGH" if best["score"] >= 80 else ("MEDIUM" if best["score"] >= 68 else "LOW")
        # If best entry is already significantly below current price, this is a wait-for-retest plan.
        dist = (best["entry"] / price - 1.0) * 100 if price else 0
        if dist < -1.5:
            status = "WAIT RETEST"
        elif dist > 1.5:
            status = "WAIT TRIGGER"
        else:
            status = "IN/NEAR ENTRY"
    else:
        conf, status = "LOW", "NO ENTRY"

    return {
        "best": best,
        "candidates": candidates,
        "confidence": conf,
        "status": status,
        "supply_demand": sd,
        "nearest_demand": demand,
        "nearest_supply": supply,
    }
