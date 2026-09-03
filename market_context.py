from __future__ import annotations

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd


def _safe(v, default=0.0):
    try:
        v = float(v)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def _ret(series: pd.Series, n: int) -> float:
    if len(series) <= n:
        return np.nan
    a = _safe(series.iloc[-n-1], np.nan)
    b = _safe(series.iloc[-1], np.nan)
    if not np.isfinite(a) or not np.isfinite(b) or a == 0:
        return np.nan
    return b / a - 1.0


def _daily_close(df: pd.DataFrame, column_name: str) -> pd.Series:
    """Return a date-normalized Close series for IDX daily-bar alignment.

    Yahoo/yfinance versions can return daily indexes with different timezone
    representations for .JK equities and ^JKSE. Exact timestamp joins can then
    produce a tiny/empty overlap even when the trading dates are the same.
    Normalize both to Jakarta calendar dates before relative-strength math.
    """
    if df is None or df.empty or "Close" not in df.columns:
        return pd.Series(dtype="float64", name=column_name)

    s = pd.to_numeric(df["Close"], errors="coerce").dropna().copy()
    idx = pd.to_datetime(s.index, errors="coerce")
    valid = ~pd.isna(idx)
    s = s.loc[valid]
    idx = pd.DatetimeIndex(idx[valid])

    # Daily IDX bars should be compared by local trading date, not by the exact
    # timezone-aware timestamp returned by a particular yfinance build.
    try:
        if idx.tz is not None:
            idx = idx.tz_convert("Asia/Jakarta").tz_localize(None)
    except Exception:
        try:
            idx = idx.tz_localize(None)
        except Exception:
            pass
    idx = idx.normalize()
    s.index = idx
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.name = column_name
    return s


def _neutral_rs(reason: str, aligned: pd.DataFrame | None = None) -> Dict[str, Any]:
    ratio = pd.Series(dtype="float64", name="rs_ratio")
    overlap = 0
    if aligned is not None and not aligned.empty:
        overlap = int(len(aligned))
        try:
            ratio = (aligned["stock"] / aligned["benchmark"]).replace([np.inf, -np.inf], np.nan).dropna()
            if not ratio.empty:
                ratio = ratio / ratio.iloc[0] * 100.0
        except Exception:
            ratio = pd.Series(dtype="float64", name="rs_ratio")
    return {
        "score": 50.0,
        "label": "N/A",
        "metrics": {
            "stock_return_20d": None, "benchmark_return_20d": None, "excess_return_20d": None,
            "stock_return_60d": None, "benchmark_return_60d": None, "excess_return_60d": None,
            "stock_return_120d": None, "benchmark_return_120d": None, "excess_return_120d": None,
            "rs_ratio": None if ratio.empty else round(float(ratio.iloc[-1]), 6),
            "rs_ma20": None, "rs_ma50": None, "rs_slope_10d": None,
        },
        "series": ratio,
        "degraded": True,
        "degraded_reason": reason,
        "overlap_bars": overlap,
        "available_horizons": [],
    }


def relative_strength_metrics(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> Dict[str, Any]:
    stock_close = _daily_close(stock_df, "stock")
    benchmark_close = _daily_close(benchmark_df, "benchmark")
    aligned = pd.concat([stock_close, benchmark_close], axis=1, join="inner").dropna()

    # RS is context, not a reason to kill the entire stock analysis. With fewer
    # than 21 common sessions there is not enough information for 20D RS, so use
    # a neutral degraded state and let structure/entry analysis continue.
    if len(aligned) < 21:
        return _neutral_rs(f"Only {len(aligned)} common trading bars for relative strength", aligned)

    metrics = {}
    available_horizons = []
    for n in (20, 60, 120):
        if len(aligned) > n:
            sr = _ret(aligned["stock"], n)
            br = _ret(aligned["benchmark"], n)
            metrics[f"stock_return_{n}d"] = sr
            metrics[f"benchmark_return_{n}d"] = br
            metrics[f"excess_return_{n}d"] = sr - br
            available_horizons.append(n)
        else:
            metrics[f"stock_return_{n}d"] = np.nan
            metrics[f"benchmark_return_{n}d"] = np.nan
            metrics[f"excess_return_{n}d"] = np.nan

    ratio = (aligned["stock"] / aligned["benchmark"]).replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return _neutral_rs("Relative-strength ratio could not be constructed", aligned)
    ratio = ratio / ratio.iloc[0] * 100.0
    rs_ma20 = ratio.rolling(20).mean()
    rs_ma50 = ratio.rolling(50).mean()
    metrics["rs_ratio"] = _safe(ratio.iloc[-1], 100.0)
    metrics["rs_ma20"] = _safe(rs_ma20.iloc[-1], metrics["rs_ratio"]) if len(ratio) >= 20 else np.nan
    metrics["rs_ma50"] = _safe(rs_ma50.iloc[-1], metrics["rs_ratio"]) if len(ratio) >= 50 else np.nan

    if len(ratio) >= 11 and _safe(ratio.iloc[-11], 0) != 0:
        metrics["rs_slope_10d"] = _safe(ratio.iloc[-1] / ratio.iloc[-11] - 1.0)
    else:
        metrics["rs_slope_10d"] = np.nan

    # Preserve the original 100-point scoring when all horizons exist. Missing
    # horizons are neutral (half of their weight) instead of silently penalizing
    # newer listings or temporary benchmark gaps.
    score = 0.0
    ex20 = metrics.get("excess_return_20d", np.nan)
    ex60 = metrics.get("excess_return_60d", np.nan)
    ex120 = metrics.get("excess_return_120d", np.nan)

    if np.isfinite(ex20):
        score += 15 if ex20 > 0 else 0
        score += 10 if ex20 > 0.05 else 0
    else:
        score += 12.5

    if np.isfinite(ex60):
        score += 20 if ex60 > 0 else 0
        score += 10 if ex60 > 0.10 else 0
    else:
        score += 15.0

    if np.isfinite(ex120):
        score += 10 if ex120 > 0 else 0
    else:
        score += 5.0

    if np.isfinite(metrics.get("rs_ma20", np.nan)):
        score += 15 if metrics["rs_ratio"] > metrics["rs_ma20"] else 0
    else:
        score += 7.5

    if np.isfinite(metrics.get("rs_ma20", np.nan)) and np.isfinite(metrics.get("rs_ma50", np.nan)):
        score += 10 if metrics["rs_ma20"] > metrics["rs_ma50"] else 0
    else:
        score += 5.0

    if np.isfinite(metrics.get("rs_slope_10d", np.nan)):
        score += 10 if metrics["rs_slope_10d"] > 0 else 0
    else:
        score += 5.0

    score = _clamp(score)
    label = "Outperforming" if score >= 70 else "Neutral" if score >= 45 else "Underperforming"
    degraded = len(available_horizons) < 3
    reason = None if not degraded else f"RS calculated from {len(aligned)} common bars; available horizons: {available_horizons}"

    return {
        "score": round(score, 1),
        "label": label,
        "metrics": {k: (round(float(v), 6) if np.isfinite(v) else None) for k, v in metrics.items()},
        "series": ratio,
        "degraded": degraded,
        "degraded_reason": reason,
        "overlap_bars": int(len(aligned)),
        "available_horizons": available_horizons,
    }


def trend_health(df: pd.DataFrame, name: str = "Benchmark") -> Dict[str, Any]:
    x = df.iloc[-1]
    required = ["Close", "MA20", "MA50", "MA200", "MA50_slope", "RSI14", "MACD", "MACD_signal"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: indikator kurang: {missing}")

    score = 0.0
    score += 20 if x["Close"] > x["MA20"] else 0
    score += 20 if x["MA20"] > x["MA50"] else 0
    score += 20 if x["MA50"] > x["MA200"] else 0
    score += 15 if x["MA50_slope"] > 0 else 0
    score += 10 if x["RSI14"] >= 50 else 0
    score += 10 if x["MACD"] > x["MACD_signal"] else 0
    score += 5 if x.get("ADX14", 0) >= 18 else 0
    score = _clamp(score)

    if score >= 70:
        label = "Bullish"
    elif score >= 45:
        label = "Neutral"
    else:
        label = "Bearish"

    return {
        "name": name,
        "score": round(score, 1),
        "label": label,
        "close": round(_safe(x["Close"]), 4),
        "rsi": round(_safe(x["RSI14"]), 2),
    }


def volume_flow(stock_df: pd.DataFrame) -> Dict[str, Any]:
    x = stock_df.iloc[-1]
    flow20 = _safe(x.get("VolumeFlow20", 0.0))
    flow5 = _safe(x.get("VolumeFlow5", 0.0))
    vr = _safe(x.get("Volume_ratio", 1.0), 1.0)

    # Translate roughly -1..+1 flow into a 0..100 score, then reward active volume.
    base = 50.0 + 35.0 * flow20 + 15.0 * flow5
    if vr >= 1.5 and flow20 > 0:
        base += 10
    elif vr >= 1.5 and flow20 < 0:
        base -= 10
    score = _clamp(base)

    label = "Accumulation" if score >= 65 else "Balanced" if score >= 40 else "Distribution"
    return {
        "score": round(score, 1),
        "label": label,
        "flow20": round(flow20, 4),
        "flow5": round(flow5, 4),
        "volume_ratio": round(vr, 2),
    }


def build_market_context(
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    sector_df: Optional[pd.DataFrame] = None,
    benchmark_name: str = "IHSG",
    sector_name: Optional[str] = None,
) -> Dict[str, Any]:
    # RS against IHSG remains the canonical "Market RS" so older execution
    # logic keeps the same semantics. When a sector series is available we also
    # calculate stock-vs-sector RS and a combined RS used by ranking.
    market_rs = relative_strength_metrics(stock_df, benchmark_df)
    benchmark = trend_health(benchmark_df, benchmark_name)
    flow = volume_flow(stock_df)

    sector = None
    stock_sector_rs = None
    combined_rs_score = market_rs["score"]

    if sector_df is not None:
        try:
            sector_trend = trend_health(sector_df, sector_name or "Sector")
            sector_market_rs = relative_strength_metrics(sector_df, benchmark_df)
            stock_sector_rs = relative_strength_metrics(stock_df, sector_df)

            sector_score = _clamp(0.60 * sector_trend["score"] + 0.40 * sector_market_rs["score"])
            sector_label = "Bullish" if sector_score >= 70 else "Neutral" if sector_score >= 45 else "Bearish"
            sector = {
                **sector_trend,
                "score": round(sector_score, 1),
                "label": sector_label,
                "relative_strength_vs_market": {k: v for k, v in sector_market_rs.items() if k != "series"},
            }
            combined_rs_score = _clamp(0.60 * market_rs["score"] + 0.40 * stock_sector_rs["score"])
        except Exception:
            # Sector context is additive. It must never break a stock analysis if
            # the sector proxy/index has insufficient overlap or missing bars.
            sector = None
            stock_sector_rs = None
            combined_rs_score = market_rs["score"]

    combined_rs_label = (
        "Outperforming" if combined_rs_score >= 70
        else "Neutral" if combined_rs_score >= 45
        else "Underperforming"
    )
    combined_rs = {
        "score": round(combined_rs_score, 1),
        "label": combined_rs_label,
        "market_weight": 0.60 if stock_sector_rs is not None else 1.0,
        "sector_weight": 0.40 if stock_sector_rs is not None else 0.0,
    }

    components = [
        ("Market Relative Strength", market_rs["score"], 0.30 if sector is not None else 0.50),
        ("Market Regime", benchmark["score"], 0.25 if sector is not None else 0.35),
        ("Volume Flow", flow["score"], 0.15),
    ]
    if sector is not None and stock_sector_rs is not None:
        components.append(("Stock vs Sector RS", stock_sector_rs["score"], 0.15))
        components.append(("Sector Strength", sector["score"], 0.15))

    total_w = sum(w for _, _, w in components)
    context_score = sum(score * w for _, score, w in components) / total_w
    context_score = _clamp(context_score)

    if context_score >= 70:
        label = "Supportive"
    elif context_score >= 45:
        label = "Mixed"
    else:
        label = "Headwind"

    market_headwind = benchmark["label"] == "Bearish"
    sector_headwind = sector is not None and sector["label"] == "Bearish"

    return {
        "score": round(context_score, 1),
        "label": label,
        # Backward compatible: relative_strength = stock vs IHSG.
        "relative_strength": {k: v for k, v in market_rs.items() if k != "series"},
        "market_relative_strength": {k: v for k, v in market_rs.items() if k != "series"},
        "sector_relative_strength": None if stock_sector_rs is None else {k: v for k, v in stock_sector_rs.items() if k != "series"},
        "combined_relative_strength": combined_rs,
        "benchmark": benchmark,
        "sector": sector,
        "volume_flow": flow,
        "component_weights": {name: round(w / total_w, 4) for name, _, w in components},
        "market_headwind": bool(market_headwind),
        "sector_headwind": bool(sector_headwind),
        "rs_series": market_rs["series"],
        "degraded": bool(market_rs.get("degraded", False)),
        "degraded_reason": market_rs.get("degraded_reason"),
    }
