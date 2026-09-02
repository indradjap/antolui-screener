from __future__ import annotations

from typing import Any, Dict, List, Tuple
import math
import numpy as np
import pandas as pd

from idx_ticks import ceil_to_tick, nearest_to_tick


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def _safe_float(v, default=0.0) -> float:
    try:
        if pd.isna(v):
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _days_since_cross(fast: pd.Series, slow: pd.Series, lookback: int = 40) -> int | None:
    cross = (fast > slow) & (fast.shift(1) <= slow.shift(1))
    tail = cross.tail(lookback)
    hits = np.flatnonzero(tail.fillna(False).to_numpy())
    if len(hits) == 0:
        return None
    return int(len(tail) - 1 - hits[-1])


def ema_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """EMA signal engine.

    Detects fresh 20/50 cross, fresh 50/200 major cross, pre-cross setup,
    and full bullish EMA stack. The strongest applicable state becomes primary.
    """
    if len(df) < 5:
        return {
            "label": "None", "score": 0.0, "status": "NONE", "signal": "None",
            "days_since_cross": None, "details": {},
        }

    x = df.iloc[-1]
    p = df.iloc[-2]
    price = _safe_float(x.get("Close"))
    e20 = _safe_float(x.get("EMA20"))
    e50 = _safe_float(x.get("EMA50"))
    e200 = _safe_float(x.get("EMA200"))
    p20 = _safe_float(p.get("EMA20"))
    p50 = _safe_float(p.get("EMA50"))
    p200 = _safe_float(p.get("EMA200"))

    d2050 = _days_since_cross(df["EMA20"], df["EMA50"], 40)
    d50200 = _days_since_cross(df["EMA50"], df["EMA200"], 60)

    slope20 = _safe_float(x.get("EMA20_slope"))
    slope50 = _safe_float(x.get("EMA50_slope"))
    slope200 = _safe_float(x.get("EMA200_slope"))

    gap2050 = (e50 - e20) / e50 if e50 > 0 else 0.0

    fresh_2050 = d2050 is not None and d2050 <= 5 and e20 > e50
    fresh_50200 = d50200 is not None and d50200 <= 10 and e50 > e200
    pre_cross = (
        e20 < e50 and 0 <= gap2050 <= 0.02 and slope20 > 0 and
        price >= e20 and (e20 - p20) > (e50 - p50)
    )
    bull_stack = price > e20 > e50 > e200 and slope20 > 0 and slope50 > 0

    scores: Dict[str, float] = {}

    s = 0.0
    s += 45 if fresh_2050 else 0
    s += 15 if slope20 > 0 else 0
    s += 15 if slope50 > 0 else 0
    s += 10 if price > e20 else 0
    s += 10 if e50 > e200 else 0
    s += 5 if slope200 >= 0 else 0
    scores["EMA20/50 Golden Cross"] = clamp(s)

    s = 0.0
    s += 50 if fresh_50200 else 0
    s += 15 if slope50 > 0 else 0
    s += 15 if slope200 > 0 else 0
    s += 10 if price > e50 else 0
    s += 10 if e20 > e50 else 0
    scores["EMA50/200 Golden Cross"] = clamp(s)

    s = 0.0
    s += 40 if pre_cross else 0
    s += 20 if 0 <= gap2050 <= 0.01 else (10 if 0 <= gap2050 <= 0.02 else 0)
    s += 15 if slope20 > 0 else 0
    s += 10 if slope50 >= 0 else 0
    s += 10 if price >= e20 else 0
    s += 5 if e50 > e200 else 0
    scores["Pre-Golden Cross"] = clamp(s)

    s = 0.0
    s += 50 if bull_stack else 0
    s += 15 if slope20 > 0 else 0
    s += 15 if slope50 > 0 else 0
    s += 10 if slope200 >= 0 else 0
    s += 10 if price > e20 else 0
    scores["Bullish EMA Stack"] = clamp(s)

    # Prefer actual cross signals over a generic stack when scores are similar.
    priority = {
        "EMA50/200 Golden Cross": 4,
        "EMA20/50 Golden Cross": 3,
        "Pre-Golden Cross": 2,
        "Bullish EMA Stack": 1,
    }
    label, score = max(scores.items(), key=lambda kv: (kv[1], priority[kv[0]]))

    if score < 55:
        label = "None"
        status = "NONE"
        signal = "None"
        days = None
    else:
        signal = label
        if label == "EMA20/50 Golden Cross":
            days = d2050
            status = "FRESH" if d2050 is not None and d2050 <= 5 else "MATURE"
        elif label == "EMA50/200 Golden Cross":
            days = d50200
            status = "FRESH" if d50200 is not None and d50200 <= 10 else "MATURE"
        elif label == "Pre-Golden Cross":
            days = None
            status = "FORMING"
        else:
            days = d2050
            status = "ACTIVE"

    return {
        "label": label,
        "score": round(float(score if label != "None" else 0.0), 1),
        "status": status,
        "signal": signal,
        "days_since_cross": days,
        "gap_ema20_50_pct": round(gap2050 * 100, 2),
        "details": {k: round(v, 1) for k, v in scores.items()},
    }


def _linear_fit(xs: np.ndarray, ys: np.ndarray) -> Tuple[float, float, float]:
    if len(xs) < 2:
        return 0.0, float(ys[-1]) if len(ys) else 0.0, 0.0
    slope, intercept = np.polyfit(xs, ys, 1)
    pred = slope * xs + intercept
    ss_res = float(np.sum((ys - pred) ** 2))
    ss_tot = float(np.sum((ys - np.mean(ys)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return float(slope), float(intercept), clamp(r2, 0.0, 1.0)


def _pivot_points(frame: pd.DataFrame, order: int = 3) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Centered rolling extrema, excluding the latest bar from pivot creation."""
    w = order * 2 + 1
    highs = frame["High"].astype(float)
    lows = frame["Low"].astype(float)
    hi_roll = highs.rolling(w, center=True).max()
    lo_roll = lows.rolling(w, center=True).min()
    hi_mask = highs.eq(hi_roll)
    lo_mask = lows.eq(lo_roll)

    hp = pd.DataFrame({"i": np.arange(len(frame)), "price": highs}).loc[hi_mask.fillna(False)]
    lp = pd.DataFrame({"i": np.arange(len(frame)), "price": lows}).loc[lo_mask.fillna(False)]
    return hp, lp


def triangle_pattern(df: pd.DataFrame, lookback: int = 70) -> Dict[str, Any]:
    """Heuristic triangle detector using regression through swing highs/lows."""
    if len(df) < max(lookback, 30):
        return {"label": "None", "score": 0.0, "status": "NONE", "pivot": None, "distance_to_pivot_pct": None, "details": {}}

    # Exclude the latest bar when fitting boundaries so breakout bars do not move the pivot.
    base = df.iloc[-(lookback + 1):-1].copy().reset_index(drop=True)
    hp, lp = _pivot_points(base, order=3)
    hp = hp.tail(6)
    lp = lp.tail(6)

    if len(hp) < 3 or len(lp) < 3:
        return {"label": "None", "score": 0.0, "status": "NONE", "pivot": None, "distance_to_pivot_pct": None, "details": {"high_pivots": len(hp), "low_pivots": len(lp)}}

    hs, hi, hr2 = _linear_fit(hp["i"].to_numpy(float), hp["price"].to_numpy(float))
    ls, li, lr2 = _linear_fit(lp["i"].to_numpy(float), lp["price"].to_numpy(float))

    last_i = float(len(base))
    first_i = max(0.0, float(min(hp["i"].min(), lp["i"].min())))
    upper_now = hs * last_i + hi
    lower_now = ls * last_i + li
    upper_then = hs * first_i + hi
    lower_then = ls * first_i + li

    price = _safe_float(df.iloc[-1]["Close"])
    scale = max(price, 1e-9)
    hsn = hs / scale
    lsn = ls / scale
    width_now = (upper_now - lower_now) / scale
    width_then = (upper_then - lower_then) / scale
    converging = width_now > 0 and width_then > 0 and width_now < width_then * 0.78

    flat_tol = 0.00045
    slope_min = 0.00035

    if abs(hsn) <= flat_tol and lsn >= slope_min:
        label = "Ascending Triangle"
    elif hsn <= -slope_min and lsn >= slope_min:
        label = "Symmetrical Triangle"
    elif hsn <= -slope_min and abs(lsn) <= flat_tol:
        label = "Descending Triangle"
    else:
        label = "None"

    if label == "None" or not converging:
        return {
            "label": "None", "score": 0.0, "status": "NONE", "pivot": None,
            "distance_to_pivot_pct": None,
            "details": {
                "high_slope_norm": round(hsn, 6), "low_slope_norm": round(lsn, 6),
                "converging": bool(converging), "high_r2": round(hr2, 3), "low_r2": round(lr2, 3),
            }
        }

    vol20 = _safe_float(df["Volume"].tail(20).mean(), 0)
    vol50 = _safe_float(df["Volume"].tail(50).mean(), vol20)
    volume_dry = vol50 > 0 and vol20 <= vol50 * 0.85
    atr20 = _safe_float(df["ATR_pct"].tail(20).mean(), 0)
    atr50 = _safe_float(df["ATR_pct"].tail(50).mean(), atr20)
    atr_contract = atr50 > 0 and atr20 <= atr50 * 0.85

    score = 0.0
    score += 20 if converging else 0
    score += 15 * hr2
    score += 15 * lr2
    score += 10 if len(hp) >= 4 else 5
    score += 10 if len(lp) >= 4 else 5
    score += 10 if volume_dry else 0
    score += 10 if atr_contract else 0
    score += 10 if _safe_float(df.iloc[-1].get("Close")) > _safe_float(df.iloc[-1].get("MA50")) else 0
    if label == "Ascending Triangle":
        score += 5
    if label == "Descending Triangle":
        score -= 15
    score = clamp(score)

    pivot_raw = max(upper_now, 0.0)
    pivot = ceil_to_tick(pivot_raw) if pivot_raw > 0 else None
    dist = ((pivot / price) - 1.0) * 100 if pivot and price > 0 else None

    x = df.iloc[-1]
    breakout = bool(
        pivot is not None and price > pivot and
        _safe_float(x.get("Volume_ratio")) >= 1.5 and
        _safe_float(x.get("close_location")) >= 0.65
    )

    if breakout:
        status = "BREAKOUT"
        score = clamp(score + 8)
    elif dist is not None and -1.0 <= dist <= 5.0:
        status = "FORMING"
    elif dist is not None and 5.0 < dist <= 10.0:
        status = "EARLY"
    else:
        status = "DEVELOPING"

    return {
        "label": label,
        "score": round(score, 1),
        "status": status,
        "pivot": None if pivot is None else int(pivot),
        "distance_to_pivot_pct": None if dist is None else round(dist, 2),
        "volume_dry_up": bool(volume_dry),
        "atr_contraction": bool(atr_contract),
        "details": {
            "high_slope_norm": round(hsn, 6),
            "low_slope_norm": round(lsn, 6),
            "high_r2": round(hr2, 3),
            "low_r2": round(lr2, 3),
            "width_start_pct": round(width_then * 100, 2),
            "width_now_pct": round(width_now * 100, 2),
            "high_pivots": int(len(hp)),
            "low_pivots": int(len(lp)),
        },
    }


def vcp_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """Early VCP heuristic based on nested range, ATR and volume contraction.

    C1/C2/C3 are nested 60/30/15-day range contractions. This is intentionally
    deterministic and conservative rather than trying to mimic discretionary chart reading.
    """
    if len(df) < 80:
        return {"label": "None", "score": 0.0, "status": "NONE", "pivot": None, "distance_to_pivot_pct": None, "contractions": [], "details": {}}

    def contraction(n: int) -> float:
        w = df.tail(n)
        hi = _safe_float(w["High"].max())
        lo = _safe_float(w["Low"].min())
        return (hi - lo) / hi if hi > 0 else 0.0

    c1, c2, c3 = contraction(60), contraction(30), contraction(15)
    sequence = c1 > c2 * 1.08 and c2 > c3 * 1.08
    meaningful = c1 >= 0.10 and c3 <= 0.12

    atr20 = _safe_float(df["ATR_pct"].tail(20).mean())
    atr60 = _safe_float(df["ATR_pct"].tail(60).mean())
    atr_contract = atr60 > 0 and atr20 <= atr60 * 0.82

    vol20 = _safe_float(df["Volume"].tail(20).mean())
    vol50 = _safe_float(df["Volume"].tail(50).mean())
    volume_dry = vol50 > 0 and vol20 <= vol50 * 0.82

    lows15 = _safe_float(df["Low"].tail(15).min())
    lows30 = _safe_float(df["Low"].tail(30).min())
    higher_low = lows15 >= lows30 * 0.98

    x = df.iloc[-1]
    price = _safe_float(x.get("Close"))
    ma50 = _safe_float(x.get("MA50"))
    ma200 = _safe_float(x.get("MA200"))

    pivot_raw = _safe_float(df["High"].iloc[-21:-1].max())
    pivot = ceil_to_tick(pivot_raw) if pivot_raw > 0 else None
    dist = ((pivot / price) - 1) * 100 if pivot and price > 0 else None

    score = 0.0
    score += 30 if sequence else 0
    score += 10 if meaningful else 0
    score += 15 if c3 <= c1 * 0.60 else (8 if c3 <= c1 * 0.72 else 0)
    score += 15 if atr_contract else 0
    score += 15 if volume_dry else 0
    score += 5 if higher_low else 0
    score += 5 if price > ma50 else 0
    score += 5 if ma50 > ma200 else 0
    score = clamp(score)

    breakout = bool(
        pivot is not None and price > pivot and
        _safe_float(x.get("Volume_ratio")) >= 1.5 and
        _safe_float(x.get("close_location")) >= 0.65
    )

    if score >= 65:
        label = "VCP"
    elif score >= 52 and sequence:
        label = "Early VCP"
    else:
        label = "None"

    if label == "None":
        status = "NONE"
    elif breakout:
        status = "BREAKOUT"
        score = clamp(score + 8)
    elif dist is not None and -1.0 <= dist <= 5.0:
        status = "FORMING"
    elif dist is not None and 5.0 < dist <= 10.0:
        status = "EARLY"
    else:
        status = "DEVELOPING"

    return {
        "label": label,
        "score": round(float(score if label != "None" else 0.0), 1),
        "status": status,
        "pivot": None if pivot is None else int(pivot),
        "distance_to_pivot_pct": None if dist is None else round(dist, 2),
        "contractions": [round(c1 * 100, 1), round(c2 * 100, 1), round(c3 * 100, 1)],
        "volume_dry_up": bool(volume_dry),
        "atr_contraction": bool(atr_contract),
        "details": {
            "sequence": bool(sequence),
            "higher_low": bool(higher_low),
            "c1_pct": round(c1 * 100, 2),
            "c2_pct": round(c2 * 100, 2),
            "c3_pct": round(c3 * 100, 2),
            "atr20_pct": round(atr20 * 100, 2),
            "atr60_pct": round(atr60 * 100, 2),
            "volume20_vs_50": round(vol20 / vol50, 2) if vol50 > 0 else None,
        },
    }



def _base_metrics(df: pd.DataFrame, n: int) -> Dict[str, float]:
    w = df.tail(n)
    hi = _safe_float(w["High"].max())
    lo = _safe_float(w["Low"].min())
    depth = (hi - lo) / hi if hi > 0 else 0.0
    return {"high": hi, "low": lo, "depth": depth}


def flat_base_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """Detect a relatively tight 15-40 day base near highs."""
    if len(df) < 80:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    x = df.iloc[-1]
    price = _safe_float(x.get("Close"))
    b20, b30, b40 = _base_metrics(df.iloc[:-1],20), _base_metrics(df.iloc[:-1],30), _base_metrics(df.iloc[:-1],40)
    # Select the tightest sensible base, preferring 20-30 day structures.
    opts=[(20,b20),(30,b30),(40,b40)]
    n,b=min(opts, key=lambda z: (abs(z[1]["depth"]-0.08), z[0]))
    depth=b["depth"]
    pivot_raw=b["high"]
    pivot=ceil_to_tick(pivot_raw) if pivot_raw>0 else None
    dist=((pivot/price)-1)*100 if pivot and price>0 else None
    vol10=_safe_float(df["Volume"].tail(10).mean())
    vol40=_safe_float(df["Volume"].tail(40).mean())
    dry=vol40>0 and vol10 <= vol40*0.82
    atr10=_safe_float(df["ATR_pct"].tail(10).mean())
    atr40=_safe_float(df["ATR_pct"].tail(40).mean())
    atr_contract=atr40>0 and atr10 <= atr40*0.82
    ma50=_safe_float(x.get("MA50")); ma200=_safe_float(x.get("MA200"))
    score=0.0
    score += 30 if 0.03 <= depth <= 0.12 else (18 if depth <= 0.15 else 0)
    score += 15 if dry else 0
    score += 15 if atr_contract else 0
    score += 15 if price > ma50 else 0
    score += 10 if ma50 > ma200 else 0
    score += 10 if dist is not None and -1 <= dist <= 5 else (5 if dist is not None and dist <= 10 else 0)
    score += 5 if _safe_float(x.get("MA50_slope")) > 0 else 0
    score=clamp(score)
    breakout=bool(pivot and price>pivot and _safe_float(x.get("Volume_ratio"))>=1.5 and _safe_float(x.get("close_location"))>=0.65)
    label="Flat Base" if score>=62 else "None"
    status="BREAKOUT" if label!="None" and breakout else ("FORMING" if label!="None" and dist is not None and dist<=5 else "DEVELOPING" if label!="None" else "NONE")
    return {"label":label,"score":round(score if label!="None" else 0.0,1),"status":status,"pivot":None if pivot is None else int(pivot),"distance_to_pivot_pct":None if dist is None else round(dist,2),"volume_dry_up":bool(dry),"atr_contraction":bool(atr_contract),"base_depth_pct":round(depth*100,2),"base_days":n,"details":{"depth_pct":round(depth*100,2),"base_days":n,"volume_dry_up":dry,"atr_contraction":atr_contract}}


def cup_handle_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """Conservative cup-and-handle heuristic; requires two rims and a shallow handle."""
    if len(df) < 140:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    base=df.iloc[-130:-15].copy()
    handle=df.iloc[-15:].copy()
    if len(base)<80:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    n=len(base)
    left=base.iloc[:max(20,n//3)]
    mid=base.iloc[n//4:3*n//4]
    right=base.iloc[-max(20,n//3):]
    left_rim=_safe_float(left["High"].max()); right_rim=_safe_float(right["High"].max())
    bottom=_safe_float(mid["Low"].min())
    rim=max(left_rim,right_rim)
    depth=(rim-bottom)/rim if rim>0 else 0
    symmetry=abs(left_rim-right_rim)/rim if rim>0 else 1
    handle_hi=_safe_float(handle["High"].max()); handle_lo=_safe_float(handle["Low"].min())
    handle_depth=(handle_hi-handle_lo)/handle_hi if handle_hi>0 else 1
    handle_above_mid=handle_lo >= bottom + 0.50*(rim-bottom)
    vol_handle=_safe_float(handle["Volume"].mean()); vol_base=_safe_float(base.tail(50)["Volume"].mean())
    dry=vol_base>0 and vol_handle <= vol_base*0.88
    x=df.iloc[-1]; price=_safe_float(x.get("Close")); ma50=_safe_float(x.get("MA50")); ma200=_safe_float(x.get("MA200"))
    pivot=ceil_to_tick(max(left_rim,right_rim)) if rim>0 else None
    dist=((pivot/price)-1)*100 if pivot and price>0 else None
    score=0.0
    score += 28 if 0.12 <= depth <= 0.35 else (14 if 0.08 <= depth <= 0.42 else 0)
    score += 18 if symmetry <= 0.08 else (8 if symmetry <= 0.12 else 0)
    score += 18 if handle_depth <= 0.12 else (8 if handle_depth <= 0.18 else 0)
    score += 10 if handle_above_mid else 0
    score += 10 if dry else 0
    score += 8 if price > ma50 else 0
    score += 5 if ma50 > ma200 else 0
    score += 3 if dist is not None and -1 <= dist <= 6 else 0
    score=clamp(score)
    breakout=bool(pivot and price>pivot and _safe_float(x.get("Volume_ratio"))>=1.5 and _safe_float(x.get("close_location"))>=0.65)
    label="Cup & Handle" if score>=68 else "None"
    status="BREAKOUT" if label!="None" and breakout else ("FORMING" if label!="None" and dist is not None and dist<=6 else "DEVELOPING" if label!="None" else "NONE")
    return {"label":label,"score":round(score if label!="None" else 0.0,1),"status":status,"pivot":None if pivot is None else int(pivot),"distance_to_pivot_pct":None if dist is None else round(dist,2),"volume_dry_up":bool(dry),"cup_depth_pct":round(depth*100,2),"handle_depth_pct":round(handle_depth*100,2),"details":{"cup_depth_pct":round(depth*100,2),"rim_symmetry_pct":round(symmetry*100,2),"handle_depth_pct":round(handle_depth*100,2),"handle_above_mid":bool(handle_above_mid),"volume_dry_up":bool(dry)}}


def darvas_box_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df)<70:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    base=df.iloc[-31:-1].copy(); x=df.iloc[-1]
    top=_safe_float(base["High"].quantile(.90)); bottom=_safe_float(base["Low"].quantile(.10))
    width=(top-bottom)/top if top>0 else 1
    atr_abs = _safe_float(base["ATR14"].tail(10).mean(),0) if "ATR14" in base.columns else _safe_float((base["High"]-base["Low"]).tail(10).mean(),0)
    tol=max(top*0.015, atr_abs*0.6)
    top_touches=int((base["High"]>=top-tol).sum()); bottom_touches=int((base["Low"]<=bottom+tol).sum())
    price=_safe_float(x.get("Close")); pivot=ceil_to_tick(top) if top>0 else None
    dist=((pivot/price)-1)*100 if pivot and price>0 else None
    vol10=_safe_float(df["Volume"].tail(10).mean()); vol40=_safe_float(df["Volume"].tail(40).mean()); dry=vol40>0 and vol10<=vol40*.90
    score=0.0
    score += 28 if width<=.12 else (15 if width<=.18 else 0)
    score += min(top_touches,4)*6
    score += min(bottom_touches,4)*4
    score += 12 if dry else 0
    score += 10 if price>_safe_float(x.get("MA50")) else 0
    score += 6 if _safe_float(x.get("MA50_slope"))>0 else 0
    score += 4 if dist is not None and -1<=dist<=5 else 0
    score=clamp(score)
    breakout=bool(pivot and price>pivot and _safe_float(x.get("Volume_ratio"))>=1.5 and _safe_float(x.get("close_location"))>=0.65)
    label="Darvas Box" if score>=64 and top_touches>=2 and bottom_touches>=2 else "None"
    status="BREAKOUT" if label!="None" and breakout else ("FORMING" if label!="None" and dist is not None and dist<=5 else "DEVELOPING" if label!="None" else "NONE")
    return {"label":label,"score":round(score if label!="None" else 0,1),"status":status,"pivot":None if pivot is None else int(pivot),"distance_to_pivot_pct":None if dist is None else round(dist,2),"volume_dry_up":bool(dry),"box_width_pct":round(width*100,2),"details":{"box_width_pct":round(width*100,2),"top_touches":top_touches,"bottom_touches":bottom_touches}}


def bull_flag_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df)<80:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    x=df.iloc[-1]; flag=df.iloc[-12:]; pre=df.iloc[-32:-12]
    pole_start=_safe_float(pre["Low"].iloc[:5].min()); pole_top=_safe_float(pre["High"].max())
    pole_gain=(pole_top/pole_start-1) if pole_start>0 else 0
    flag_low=_safe_float(flag["Low"].min()); retr=(pole_top-flag_low)/(pole_top-pole_start) if pole_top>pole_start else 1
    xs=np.arange(len(flag),dtype=float); slope,_,r2=_linear_fit(xs,flag["Close"].astype(float).to_numpy())
    slope_norm=slope/max(_safe_float(flag["Close"].mean()),1e-9)
    vol_flag=_safe_float(flag["Volume"].mean()); vol_pole=_safe_float(pre.tail(10)["Volume"].mean()); dry=vol_pole>0 and vol_flag<=vol_pole*.85
    price=_safe_float(x.get("Close")); pivot=ceil_to_tick(_safe_float(flag["High"].iloc[:-1].max()))
    dist=((pivot/price)-1)*100 if pivot and price>0 else None
    score=0.0
    score += 30 if pole_gain>=.15 else (18 if pole_gain>=.10 else 0)
    score += 25 if 0<=retr<=.38 else (12 if retr<=.50 else 0)
    score += 12 if -0.004<=slope_norm<=0.0015 else 0
    score += 12 if dry else 0
    score += 12 if price>_safe_float(x.get("MA50")) else 0
    score += 5 if _safe_float(x.get("MA50_slope"))>0 else 0
    score += 4 if dist is not None and -1<=dist<=5 else 0
    score=clamp(score)
    breakout=bool(price>pivot and _safe_float(x.get("Volume_ratio"))>=1.5 and _safe_float(x.get("close_location"))>=.65)
    label="Bull Flag" if score>=66 else "None"
    status="BREAKOUT" if label!="None" and breakout else ("FORMING" if label!="None" and dist is not None and dist<=5 else "DEVELOPING" if label!="None" else "NONE")
    return {"label":label,"score":round(score if label!="None" else 0,1),"status":status,"pivot":int(pivot) if pivot else None,"distance_to_pivot_pct":None if dist is None else round(dist,2),"volume_dry_up":bool(dry),"pole_gain_pct":round(pole_gain*100,2),"flag_retrace_pct":round(retr*100,2),"details":{"pole_gain_pct":round(pole_gain*100,2),"flag_retrace_pct":round(retr*100,2),"flag_slope_norm":round(slope_norm,6),"volume_dry_up":bool(dry)}}


def high_tight_flag_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df)<100:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    x=df.iloc[-1]; run=df.iloc[-60:-15]; flag=df.iloc[-15:]
    start=_safe_float(run["Low"].iloc[:8].min()); top=_safe_float(run["High"].max()); gain=top/start-1 if start>0 else 0
    flag_low=_safe_float(flag["Low"].min()); correction=(top-flag_low)/top if top>0 else 1
    vol_flag=_safe_float(flag["Volume"].mean()); vol_run=_safe_float(run.tail(15)["Volume"].mean()); dry=vol_run>0 and vol_flag<=vol_run*.85
    price=_safe_float(x.get("Close")); pivot=ceil_to_tick(_safe_float(flag["High"].iloc[:-1].max())); dist=((pivot/price)-1)*100 if pivot and price>0 else None
    score=0.0
    score += 45 if gain>=.50 else (25 if gain>=.35 else 0)
    score += 25 if correction<=.20 else (12 if correction<=.25 else 0)
    score += 15 if dry else 0
    score += 10 if price>_safe_float(x.get("MA50")) else 0
    score += 5 if dist is not None and -1<=dist<=6 else 0
    score=clamp(score)
    breakout=bool(price>pivot and _safe_float(x.get("Volume_ratio"))>=1.6 and _safe_float(x.get("close_location"))>=.65)
    label="High Tight Flag" if score>=72 else "None"
    status="BREAKOUT" if label!="None" and breakout else ("FORMING" if label!="None" and dist is not None and dist<=6 else "DEVELOPING" if label!="None" else "NONE")
    return {"label":label,"score":round(score if label!="None" else 0,1),"status":status,"pivot":int(pivot) if pivot else None,"distance_to_pivot_pct":None if dist is None else round(dist,2),"volume_dry_up":bool(dry),"run_gain_pct":round(gain*100,2),"flag_correction_pct":round(correction*100,2),"risk":"HIGH","details":{"run_gain_pct":round(gain*100,2),"flag_correction_pct":round(correction*100,2),"volume_dry_up":bool(dry)}}


def volatility_squeeze_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df)<80:
        return {"label":"None","score":0.0,"status":"NONE","pivot":None,"distance_to_pivot_pct":None,"details":{}}
    x=df.iloc[-1]
    ranges=(df["High"]-df["Low"]).astype(float)
    nr7=bool(ranges.iloc[-1] <= ranges.tail(7).min()+1e-12)
    if "BB_width" in df.columns:
        bbw_series = df["BB_width"].astype(float)
    else:
        mid = df["Close"].rolling(20).mean()
        std = df["Close"].rolling(20).std()
        bbw_series = (4.0 * std) / mid.replace(0, np.nan)
    bbw=_safe_float(bbw_series.iloc[-1]); bbw60=bbw_series.tail(60).dropna(); bb_pct=float((bbw60<=bbw).mean()) if len(bbw60) else 1
    atr10=_safe_float(df["ATR_pct"].tail(10).mean()); atr50=_safe_float(df["ATR_pct"].tail(50).mean()); atr_contract=atr50>0 and atr10<=atr50*.75
    vol10=_safe_float(df["Volume"].tail(10).mean()); vol50=_safe_float(df["Volume"].tail(50).mean()); dry=vol50>0 and vol10<=vol50*.78
    price=_safe_float(x.get("Close")); pivot_raw=_safe_float(df["High"].iloc[-21:-1].max()); pivot=ceil_to_tick(pivot_raw) if pivot_raw>0 else None; dist=((pivot/price)-1)*100 if pivot and price>0 else None
    score=0.0
    score += 25 if nr7 else 0
    score += 25 if bb_pct<=.20 else (12 if bb_pct<=.35 else 0)
    score += 20 if atr_contract else 0
    score += 15 if dry else 0
    score += 10 if price>_safe_float(x.get("MA50")) else 0
    score += 5 if dist is not None and -1<=dist<=6 else 0
    score=clamp(score)
    label="Volatility Squeeze" if score>=62 else "None"
    status="NR7" if label!="None" and nr7 else ("FORMING" if label!="None" else "NONE")
    return {"label":label,"score":round(score if label!="None" else 0,1),"status":status,"pivot":None if pivot is None else int(pivot),"distance_to_pivot_pct":None if dist is None else round(dist,2),"nr7":nr7,"volume_dry_up":bool(dry),"atr_contraction":bool(atr_contract),"details":{"nr7":nr7,"bb_width_percentile":round(bb_pct*100,1),"atr_contraction":atr_contract,"volume_dry_up":dry}}


def minervini_trend_template(df: pd.DataFrame) -> Dict[str, Any]:
    """Trend Template inspired by common Minervini-style leader filters.

    This is a quantitative trend-quality filter, not an endorsement or a complete
    implementation of any proprietary methodology.
    """
    if len(df)<220:
        return {"label":"Trend","score":0.0,"passed":False,"conditions":{},"high52":None,"low52":None,"distance_high52_pct":None}
    x=df.iloc[-1]; price=_safe_float(x.get("Close"))
    ma50=_safe_float(x.get("MA50")); ma200=_safe_float(x.get("MA200")); ma150=_safe_float(df["Close"].rolling(150).mean().iloc[-1])
    ma200_prev=_safe_float(df["Close"].rolling(200).mean().iloc[-21])
    high52=_safe_float(df["High"].tail(min(252,len(df))).max()); low52=_safe_float(df["Low"].tail(min(252,len(df))).min())
    cond={
        "price_above_ma50": price>ma50,
        "price_above_ma150": price>ma150,
        "price_above_ma200": price>ma200,
        "ma50_above_ma150": ma50>ma150,
        "ma150_above_ma200": ma150>ma200,
        "ma200_rising": ma200>ma200_prev,
        "30pct_above_52w_low": price>=low52*1.30 if low52>0 else False,
        "within_25pct_52w_high": price>=high52*.75 if high52>0 else False,
    }
    count=sum(bool(v) for v in cond.values()); score=count/len(cond)*100
    return {"label":"Trend","score":round(score,1),"passed":count>=7,"conditions":cond,"conditions_met":count,"conditions_total":len(cond),"high52":round(high52,2),"low52":round(low52,2),"distance_high52_pct":round((price/high52-1)*100,2) if high52>0 else None}


def leader_52w(df: pd.DataFrame, template: Dict[str, Any]) -> Dict[str, Any]:
    if len(df)<220:
        return {"label":"52W Leader","score":0.0,"passed":False,"distance_high52_pct":None}
    price=_safe_float(df.iloc[-1].get("Close")); high52=_safe_float(template.get("high52")); dist=(price/high52-1)*100 if high52>0 else None
    score=0.0
    score += 55 if dist is not None and dist>=-5 else (35 if dist is not None and dist>=-10 else 0)
    score += 30 if template.get("passed") else 15 if template.get("score",0)>=75 else 0
    score += 15 if _safe_float(df.iloc[-1].get("MA50_slope"))>0 else 0
    return {"label":"52W Leader","score":round(clamp(score),1),"passed":bool(score>=75),"distance_high52_pct":None if dist is None else round(dist,2)}


def detect_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    ema = ema_pattern(df)
    tri = triangle_pattern(df)
    vcp = vcp_pattern(df)
    flat = flat_base_pattern(df)
    cup = cup_handle_pattern(df)
    darvas = darvas_box_pattern(df)
    flag = bull_flag_pattern(df)
    htf = high_tight_flag_pattern(df)
    squeeze = volatility_squeeze_pattern(df)
    template = minervini_trend_template(df)
    leader = leader_52w(df, template)

    # Primary long-only patterns. Less useful/noisy signals are kept only as
    # diagnostics: descending/symmetrical triangles, generic EMA stack and
    # mature 50/200 crosses no longer occupy the main screener.
    candidates: List[Tuple[str, float, str, Dict[str, Any]]] = []
    core_objs = [vcp, flat, cup, darvas, flag, htf, squeeze]
    if tri.get("label") == "Ascending Triangle":
        core_objs.append(tri)
    for obj in core_objs:
        if obj.get("label") not in {None,"None"}:
            boost=5 if obj.get("status")=="BREAKOUT" else 0
            candidates.append((obj["label"],clamp(float(obj.get("score",0))+boost),obj.get("status","NONE"),obj))

    if ema.get("label") in {"EMA20/50 Golden Cross","Pre-Golden Cross"}:
        candidates.append((ema["label"],float(ema["score"]),ema["status"],ema))

    if candidates:
        status_priority={"BREAKOUT":5,"FRESH":4,"FORMING":3,"NR7":3,"ACTIVE":2,"EARLY":1,"DEVELOPING":0,"MATURE":0}
        label,score,status,source=max(candidates,key=lambda c:(c[1],status_priority.get(c[2],0)))
    else:
        label,score,status,source="None",50.0,"NONE",{}

    pattern_score=float(score if label!="None" else 50.0)
    pivot=source.get("pivot") if isinstance(source,dict) else None
    dist=source.get("distance_to_pivot_pct") if isinstance(source,dict) else None

    matches=[]
    for obj in [vcp,flat,cup,darvas,flag,htf,squeeze]:
        if obj.get("label") not in {None,"None"}:
            matches.append(f'{obj["label"]} ({obj.get("status","ACTIVE")})')
    if tri.get("label")=="Ascending Triangle":
        matches.append(f'Ascending Triangle ({tri.get("status")})')
    if ema.get("label") in {"EMA20/50 Golden Cross","Pre-Golden Cross"}:
        matches.append(f'{ema["label"]} ({ema.get("status")})')
    if template.get("passed"):
        matches.append("UPTREND")
    if leader.get("passed"):
        matches.append("52W Leader (PASS)")

    dry_any=any(bool(o.get("volume_dry_up")) for o in [vcp,flat,cup,darvas,flag,htf,squeeze,tri])
    near_pivot=dist is not None and -1.0<=dist<=5.0
    independent_core=sum(1 for o in [vcp,flat,cup,darvas,flag,htf,squeeze,tri] if o.get("label") not in {None,"None","Symmetrical Triangle","Descending Triangle"} and float(o.get("score",0))>=65)
    super_setup=bool(
        pattern_score>=80 and template.get("passed") and
        (leader.get("passed") or independent_core>=2) and
        (dry_any or squeeze.get("nr7")) and near_pivot
    )
    if super_setup:
        pattern_score=clamp(pattern_score+4)

    return {
        "label":label,
        "score":round(pattern_score,1),
        "status":status,
        "pivot":pivot,
        "distance_to_pivot_pct":dist,
        "matches":matches,
        "ema":ema,
        "triangle":tri,
        "vcp":vcp,
        "flat_base":flat,
        "cup_handle":cup,
        "darvas":darvas,
        "bull_flag":flag,
        "high_tight_flag":htf,
        "squeeze":squeeze,
        "trend_template":template,
        "leader_52w":leader,
        "volume_dry_up":dry_any,
        "super_setup":super_setup,
        "priority_candidate":bool(super_setup or (label in {"VCP","Flat Base","Cup & Handle","Darvas Box","Bull Flag","Ascending Triangle"} and pattern_score>=82 and status in {"FORMING","BREAKOUT"})),
    }
