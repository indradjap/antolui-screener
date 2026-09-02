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


def relative_strength_metrics(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> Dict[str, Any]:
    aligned = pd.concat(
        [stock_df["Close"].rename("stock"), benchmark_df["Close"].rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()

    if len(aligned) < 65:
        raise ValueError("Minimal sekitar 65 bar overlap diperlukan untuk relative strength.")

    metrics = {}
    for n in (20, 60, 120):
        if len(aligned) > n:
            sr = _ret(aligned["stock"], n)
            br = _ret(aligned["benchmark"], n)
            metrics[f"stock_return_{n}d"] = sr
            metrics[f"benchmark_return_{n}d"] = br
            metrics[f"excess_return_{n}d"] = sr - br
        else:
            metrics[f"stock_return_{n}d"] = np.nan
            metrics[f"benchmark_return_{n}d"] = np.nan
            metrics[f"excess_return_{n}d"] = np.nan

    ratio = aligned["stock"] / aligned["benchmark"]
    ratio = ratio / ratio.iloc[0] * 100.0
    rs_ma20 = ratio.rolling(20).mean()
    rs_ma50 = ratio.rolling(50).mean()
    metrics["rs_ratio"] = _safe(ratio.iloc[-1], 100.0)
    metrics["rs_ma20"] = _safe(rs_ma20.iloc[-1], metrics["rs_ratio"])
    metrics["rs_ma50"] = _safe(rs_ma50.iloc[-1], metrics["rs_ratio"])

    if len(ratio) >= 11 and _safe(ratio.iloc[-11], 0) != 0:
        metrics["rs_slope_10d"] = _safe(ratio.iloc[-1] / ratio.iloc[-11] - 1.0)
    else:
        metrics["rs_slope_10d"] = 0.0

    score = 0.0
    ex20 = metrics.get("excess_return_20d", np.nan)
    ex60 = metrics.get("excess_return_60d", np.nan)
    ex120 = metrics.get("excess_return_120d", np.nan)

    if np.isfinite(ex20):
        score += 15 if ex20 > 0 else 0
        score += 10 if ex20 > 0.05 else 0
    if np.isfinite(ex60):
        score += 20 if ex60 > 0 else 0
        score += 10 if ex60 > 0.10 else 0
    if np.isfinite(ex120):
        score += 10 if ex120 > 0 else 0
    score += 15 if metrics["rs_ratio"] > metrics["rs_ma20"] else 0
    score += 10 if metrics["rs_ma20"] > metrics["rs_ma50"] else 0
    score += 10 if metrics["rs_slope_10d"] > 0 else 0

    score = _clamp(score)
    label = "Outperforming" if score >= 70 else "Neutral" if score >= 45 else "Underperforming"

    return {
        "score": round(score, 1),
        "label": label,
        "metrics": {k: (round(float(v), 6) if np.isfinite(v) else None) for k, v in metrics.items()},
        "series": ratio,
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
    }
