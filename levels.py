from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import math
import numpy as np
import pandas as pd


@dataclass
class PriceLevel:
    center: float
    zone_low: float
    zone_high: float
    role: str
    score: float
    touches: int
    high_touches: int
    low_touches: int
    last_touch_bars_ago: int
    rejection_score: float
    volume_score: float
    confluence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_float(v, default=np.nan):
    try:
        v = float(v)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _atr_series(df: pd.DataFrame) -> pd.Series:
    if "ATR14" in df.columns and df["ATR14"].notna().any():
        return df["ATR14"].astype(float)

    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(14, min_periods=3).mean()


def _volume_ratio_series(df: pd.DataFrame) -> pd.Series:
    if "Volume_ratio" in df.columns and df["Volume_ratio"].notna().any():
        return df["Volume_ratio"].astype(float).fillna(1.0)
    if "Volume" not in df.columns:
        return pd.Series(1.0, index=df.index)
    avg = df["Volume"].rolling(20, min_periods=5).mean()
    return (df["Volume"] / avg.replace(0, np.nan)).fillna(1.0)


def _find_pivots(df: pd.DataFrame, order: int = 3, min_atr_move: float = 0.35):
    """Return swing candidates without look-ahead leakage outside the local window.

    This is used for *current-state* level discovery, not predictive backtests. For
    historical backtesting, recalculate levels at each historical date.
    """
    if len(df) < 2 * order + 3:
        return []

    highs = df["High"].astype(float).to_numpy()
    lows = df["Low"].astype(float).to_numpy()
    atr = _atr_series(df).astype(float).to_numpy()
    vol_ratio = _volume_ratio_series(df).astype(float).to_numpy()

    pivots = []
    n = len(df)

    for i in range(order, n - order):
        h = highs[i]
        l = lows[i]
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            a = max((h - l), abs(h) * 0.02, 1e-9)

        left_h = np.max(highs[i - order:i])
        right_h = np.max(highs[i + 1:i + order + 1])
        left_l = np.min(lows[i - order:i])
        right_l = np.min(lows[i + 1:i + order + 1])

        is_high = h >= left_h and h >= right_h
        is_low = l <= left_l and l <= right_l

        # Require some local prominence so tiny noise does not become a level.
        high_prom = h - min(np.min(lows[i - order:i + 1]), np.min(lows[i:i + order + 1]))
        low_prom = max(np.max(highs[i - order:i + 1]), np.max(highs[i:i + order + 1])) - l

        if is_high and high_prom >= min_atr_move * a:
            future_low = np.min(lows[i + 1:min(n, i + 4)]) if i + 1 < n else l
            rejection_atr = max(0.0, (h - future_low) / a)
            pivots.append({
                "price": h,
                "kind": "high",
                "bar": i,
                "bars_ago": n - 1 - i,
                "volume_ratio": float(vol_ratio[i]) if np.isfinite(vol_ratio[i]) else 1.0,
                "rejection_atr": min(rejection_atr, 4.0),
            })

        if is_low and low_prom >= min_atr_move * a:
            future_high = np.max(highs[i + 1:min(n, i + 4)]) if i + 1 < n else h
            rejection_atr = max(0.0, (future_high - l) / a)
            pivots.append({
                "price": l,
                "kind": "low",
                "bar": i,
                "bars_ago": n - 1 - i,
                "volume_ratio": float(vol_ratio[i]) if np.isfinite(vol_ratio[i]) else 1.0,
                "rejection_atr": min(rejection_atr, 4.0),
            })

    return pivots


def _cluster_pivots(pivots, current_atr: float, tolerance_pct: float = 0.015, atr_mult: float = 0.45):
    if not pivots:
        return []

    pivots = sorted(pivots, key=lambda p: p["price"])
    clusters = []

    for p in pivots:
        chosen = None
        best_dist = None
        for c in clusters:
            center = np.average(
                [x["price"] for x in c],
                weights=[1.0 + min(x["volume_ratio"], 3.0) * 0.15 for x in c],
            )
            tolerance = max(abs(center) * tolerance_pct, current_atr * atr_mult)
            dist = abs(p["price"] - center)
            if dist <= tolerance and (best_dist is None or dist < best_dist):
                chosen = c
                best_dist = dist

        if chosen is None:
            clusters.append([p])
        else:
            chosen.append(p)

    # One extra merge pass for adjacent clusters whose weighted centers converge.
    merged = []
    for c in clusters:
        center = np.mean([x["price"] for x in c])
        if not merged:
            merged.append(c)
            continue
        prev = merged[-1]
        prev_center = np.mean([x["price"] for x in prev])
        tol = max(abs((center + prev_center) / 2) * tolerance_pct, current_atr * atr_mult)
        if abs(center - prev_center) <= tol:
            prev.extend(c)
        else:
            merged.append(c)

    return merged


def _ma_confluence(df: pd.DataFrame, center: float, tolerance: float) -> List[str]:
    result = []
    if df.empty:
        return result
    x = df.iloc[-1]
    for name in ("MA20", "MA50", "MA200"):
        if name in df.columns:
            v = _safe_float(x.get(name))
            if np.isfinite(v) and abs(v - center) <= tolerance:
                result.append(name)
    return result


def _score_cluster(df: pd.DataFrame, cluster, current_price: float, current_atr: float) -> PriceLevel:
    prices = np.array([p["price"] for p in cluster], dtype=float)
    weights = np.array([
        1.0
        + 0.18 * min(p["volume_ratio"], 3.0)
        + 0.12 * min(p["rejection_atr"], 3.0)
        for p in cluster
    ])
    center = float(np.average(prices, weights=weights))

    # Zone is derived from cluster dispersion, but cannot become unrealistically tight.
    dispersion = float(np.std(prices)) if len(prices) > 1 else 0.0
    half_width = max(dispersion * 1.25, current_atr * 0.18, abs(center) * 0.0035)
    zone_low = center - half_width
    zone_high = center + half_width

    high_touches = sum(p["kind"] == "high" for p in cluster)
    low_touches = sum(p["kind"] == "low" for p in cluster)
    touches = len(cluster)
    last_touch = min(p["bars_ago"] for p in cluster)

    # Score 0-100.
    touch_score = min(35.0, 9.0 * touches)
    recency_score = 20.0 * math.exp(-last_touch / 70.0)
    rejection_raw = np.mean([min(p["rejection_atr"], 3.0) / 3.0 for p in cluster])
    rejection_score = 20.0 * rejection_raw
    volume_raw = np.mean([min(max(p["volume_ratio"], 0.0), 3.0) / 3.0 for p in cluster])
    volume_score = 15.0 * volume_raw

    confluence_tolerance = max(current_atr * 0.45, abs(center) * 0.012)
    confluence = _ma_confluence(df, center, confluence_tolerance)
    confluence_score = min(10.0, 4.0 * len(confluence))

    score = min(100.0, touch_score + recency_score + rejection_score + volume_score + confluence_score)

    if zone_high < current_price:
        role = "Support"
    elif zone_low > current_price:
        role = "Resistance"
    else:
        # Current price is inside the zone. Historical pivot composition decides.
        role = "Support" if low_touches >= high_touches else "Resistance"

    return PriceLevel(
        center=round(center, 2),
        zone_low=round(zone_low, 2),
        zone_high=round(zone_high, 2),
        role=role,
        score=float(round(float(score), 1)),
        touches=touches,
        high_touches=high_touches,
        low_touches=low_touches,
        last_touch_bars_ago=int(last_touch),
        rejection_score=float(round(float(rejection_score), 1)),
        volume_score=float(round(float(volume_score), 1)),
        confluence=confluence,
    )


def discover_levels(
    df: pd.DataFrame,
    lookback: int = 180,
    pivot_order: int = 3,
    tolerance_pct: float = 0.015,
    min_score: float = 22.0,
) -> Dict[str, Any]:
    """Discover price-action support/resistance zones.

    Returns ranked support/resistance levels plus debug metadata. The nearest level
    is not automatically the strongest level; both distance and score are preserved.
    """
    if len(df) < 20:
        raise ValueError("Minimal 20 bar diperlukan untuk level discovery.")

    work = df.tail(lookback).copy()
    current_price = float(work.iloc[-1]["Close"])
    atr_s = _atr_series(work)
    current_atr = _safe_float(atr_s.iloc[-1], default=current_price * 0.03)
    if not np.isfinite(current_atr) or current_atr <= 0:
        current_atr = max(current_price * 0.03, 1e-6)

    pivots = _find_pivots(work, order=pivot_order)
    clusters = _cluster_pivots(pivots, current_atr, tolerance_pct=tolerance_pct)
    scored = [_score_cluster(work, c, current_price, current_atr) for c in clusters]
    scored = [lvl for lvl in scored if lvl.score >= min_score]

    supports = [lvl for lvl in scored if lvl.zone_low < current_price and lvl.center < current_price]
    resistances = [lvl for lvl in scored if lvl.zone_high > current_price and lvl.center > current_price]

    # Nearest first, with score as tie breaker.
    supports.sort(key=lambda l: (current_price - l.center, -l.score))
    resistances.sort(key=lambda l: (l.center - current_price, -l.score))

    return {
        "price": round(current_price, 2),
        "atr": round(current_atr, 2),
        "supports": [x.to_dict() for x in supports],
        "resistances": [x.to_dict() for x in resistances],
        "all_levels": [x.to_dict() for x in sorted(scored, key=lambda l: l.center)],
        "pivot_count": len(pivots),
        "cluster_count": len(scored),
    }


def select_level(levels: List[Dict[str, Any]], min_score: float = 30.0, max_distance_atr: float | None = None,
                 price: float | None = None, atr: float | None = None):
    candidates = [l for l in levels if float(l.get("score", 0)) >= min_score]
    if max_distance_atr is not None and price is not None and atr is not None and atr > 0:
        candidates = [
            l for l in candidates
            if abs(float(l["center"]) - price) <= max_distance_atr * atr
        ]
    return candidates[0] if candidates else (levels[0] if levels else None)
