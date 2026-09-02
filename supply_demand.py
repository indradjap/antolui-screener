from __future__ import annotations

from typing import Any, Dict, List
import math
import numpy as np
import pandas as pd

from idx_ticks import floor_to_tick, ceil_to_tick, nearest_to_tick


def _f(v, default=0.0):
    try:
        v = float(v)
        return v if np.isfinite(v) else float(default)
    except Exception:
        return float(default)


def _atr(df: pd.DataFrame) -> pd.Series:
    if "ATR14" in df.columns and df["ATR14"].notna().any():
        return df["ATR14"].astype(float)
    pc = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - pc).abs(),
        (df["Low"] - pc).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=3).mean()


def _volume_ratio(df: pd.DataFrame) -> pd.Series:
    if "Volume_ratio" in df.columns:
        return df["Volume_ratio"].astype(float).fillna(1.0)
    avg = df["Volume"].rolling(20, min_periods=5).mean()
    return (df["Volume"] / avg.replace(0, np.nan)).fillna(1.0)


def _zone_retests(df: pd.DataFrame, start_i: int, low: float, high: float) -> tuple[int, int | None, bool]:
    """Count later zone revisits. A close through the distal edge invalidates the zone."""
    retests = 0
    last = None
    broken = False
    for j in range(start_i + 1, len(df)):
        r = df.iloc[j]
        overlaps = float(r["Low"]) <= high and float(r["High"]) >= low
        if overlaps:
            retests += 1
            last = len(df) - 1 - j
    return retests, last, broken


def _score_zone(kind: str, impulse_atr: float, vol_ratio: float, age: int, retests: int,
                confluence: int, price: float, low: float, high: float) -> float:
    departure = min(35.0, max(0.0, impulse_atr) / 3.0 * 35.0)
    volume = min(15.0, max(0.0, vol_ratio) / 2.0 * 15.0)
    freshness = 22.0 * math.exp(-age / 95.0)
    # First retest can still be valid, repeated retests weaken a zone.
    retest_score = 18.0 if retests == 0 else (12.0 if retests == 1 else max(0.0, 9.0 - 3.0 * (retests - 1)))
    conf = min(10.0, confluence * 3.5)
    score = departure + volume + freshness + retest_score + conf
    return round(max(0.0, min(100.0, score)), 1)


def _confluence_count(df: pd.DataFrame, low: float, high: float) -> tuple[int, List[str]]:
    x = df.iloc[-1]
    atr = _f(x.get("ATR14"), max(_f(x.get("Close")) * 0.02, 1.0))
    tol = max(0.35 * atr, _f(x.get("Close")) * 0.007)
    names = []
    for name in ("EMA20", "EMA50", "MA20", "MA50", "MA200"):
        v = _f(x.get(name), np.nan)
        if np.isfinite(v) and (low - tol) <= v <= (high + tol):
            names.append(name)
    return len(names), names


def discover_supply_demand(df: pd.DataFrame, lookback: int = 180) -> Dict[str, Any]:
    """Heuristic institutional-style supply/demand zone detector.

    A zone is a compact 1-3 bar base followed by a strong directional departure.
    Demand = bullish departure; Supply = bearish departure. It is deliberately
    conservative and intended as decision support, not proof of institutional orders.
    """
    if len(df) < 35:
        return {"demand": [], "supply": [], "nearest_demand": None, "nearest_supply": None}

    frame = df.tail(min(lookback, len(df))).copy()
    atrs = _atr(frame).to_numpy(dtype=float)
    vr = _volume_ratio(frame).to_numpy(dtype=float)
    price = float(frame.iloc[-1]["Close"])
    zones: List[Dict[str, Any]] = []

    # Base windows of 1-3 candles. Departures are measured over next 3 bars.
    for end in range(5, len(frame) - 4):
        for base_len in (1, 2, 3):
            start = end - base_len + 1
            if start < 2:
                continue
            base = frame.iloc[start:end + 1]
            a = np.nanmedian(atrs[max(0, start-2):end+1])
            if not np.isfinite(a) or a <= 0:
                continue

            base_high = float(base["High"].max())
            base_low = float(base["Low"].min())
            base_range = base_high - base_low
            # A true base should be relatively compact.
            if base_range > 1.35 * a:
                continue

            future = frame.iloc[end + 1:min(len(frame), end + 4)]
            if future.empty:
                continue
            bull_move = float(future["High"].max()) - base_high
            bear_move = base_low - float(future["Low"].min())
            impulse_thr = max(1.15 * a, price * 0.012)

            body_high = float(pd.concat([base["Open"], base["Close"]], axis=1).max(axis=1).max())
            body_low = float(pd.concat([base["Open"], base["Close"]], axis=1).min(axis=1).min())
            age = len(frame) - 1 - end
            volume_depart = float(np.nanmax(vr[end + 1:min(len(frame), end + 4)])) if end + 1 < len(frame) else 1.0

            if bull_move >= impulse_thr and bull_move >= bear_move * 1.15:
                # Demand: distal line at base low, proximal line around top of base body.
                low = base_low
                high = min(base_high, max(body_high, base_low + 0.35 * base_range))
                if high <= low:
                    high = base_high
                retests, last_retest, _ = _zone_retests(frame, end, low, high)
                # Broken if a later close decisively below distal line.
                later = frame.iloc[end+1:]
                broken = bool((later["Close"].astype(float) < low - 0.15 * a).any())
                conf_n, conf = _confluence_count(frame, low, high)
                score = _score_zone("demand", bull_move / a, volume_depart, age, retests, conf_n, price, low, high)
                if not broken and score >= 42:
                    zones.append({
                        "type": "Demand", "zone_low": low, "zone_high": high,
                        "proximal": high, "distal": low, "score": score,
                        "age_bars": age, "retests": retests,
                        "last_retest_bars_ago": last_retest,
                        "departure_atr": round(bull_move / a, 2),
                        "volume_ratio_departure": round(volume_depart, 2),
                        "confluence": conf,
                    })

            if bear_move >= impulse_thr and bear_move >= bull_move * 1.15:
                # Supply: proximal line around bottom of base body, distal line at base high.
                low = max(base_low, min(body_low, base_high - 0.35 * base_range))
                high = base_high
                if high <= low:
                    low = base_low
                retests, last_retest, _ = _zone_retests(frame, end, low, high)
                later = frame.iloc[end+1:]
                broken = bool((later["Close"].astype(float) > high + 0.15 * a).any())
                conf_n, conf = _confluence_count(frame, low, high)
                score = _score_zone("supply", bear_move / a, volume_depart, age, retests, conf_n, price, low, high)
                if not broken and score >= 42:
                    zones.append({
                        "type": "Supply", "zone_low": low, "zone_high": high,
                        "proximal": low, "distal": high, "score": score,
                        "age_bars": age, "retests": retests,
                        "last_retest_bars_ago": last_retest,
                        "departure_atr": round(bear_move / a, 2),
                        "volume_ratio_departure": round(volume_depart, 2),
                        "confluence": conf,
                    })

    # Deduplicate overlapping zones; keep stronger/newer one.
    def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items = sorted(items, key=lambda z: (-z["score"], z["age_bars"]))
        kept = []
        for z in items:
            center = (z["zone_low"] + z["zone_high"]) / 2
            overlaps = False
            for k in kept:
                kc = (k["zone_low"] + k["zone_high"]) / 2
                width = max(z["zone_high"] - z["zone_low"], k["zone_high"] - k["zone_low"], price * 0.008)
                if abs(center - kc) <= 0.65 * width:
                    overlaps = True
                    break
            if not overlaps:
                kept.append(z)
        return kept[:8]

    demand = dedupe([z for z in zones if z["type"] == "Demand"])
    supply = dedupe([z for z in zones if z["type"] == "Supply"])

    # Prefer zones below/around price for demand and above/around price for supply.
    demand_valid = [z for z in demand if z["zone_low"] <= price * 1.015]
    supply_valid = [z for z in supply if z["zone_high"] >= price * 0.985]

    demand_valid.sort(key=lambda z: (max(0.0, price - z["zone_high"]), -z["score"]))
    supply_valid.sort(key=lambda z: (max(0.0, z["zone_low"] - price), -z["score"]))

    # Convert display/order boundaries to valid IDX levels.
    def executable(z):
        if z is None:
            return None
        out = dict(z)
        out["zone_low_exec"] = int(floor_to_tick(z["zone_low"]))
        out["zone_high_exec"] = int(ceil_to_tick(z["zone_high"]))
        out["proximal_exec"] = int(nearest_to_tick(z["proximal"]))
        out["distal_exec"] = int(nearest_to_tick(z["distal"]))
        return out

    demand_exec = [executable(z) for z in demand_valid]
    supply_exec = [executable(z) for z in supply_valid]
    return {
        "demand": demand_exec,
        "supply": supply_exec,
        "nearest_demand": demand_exec[0] if demand_exec else None,
        "nearest_supply": supply_exec[0] if supply_exec else None,
    }
