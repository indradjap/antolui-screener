import math
import numpy as np
import pandas as pd

from levels import discover_levels
from strategy import build_trade_plan


def synthetic_levels_frame():
    """Synthetic chart with repeated reactions around 835, 935, 995, 1090, 1160."""
    rng = np.random.default_rng(7)
    n = 180
    close = np.linspace(860, 965, n) + rng.normal(0, 7, n)

    # Create broad oscillation so local pivots exist naturally.
    close += 24 * np.sin(np.linspace(0, 12 * np.pi, n))
    high = close + rng.uniform(8, 17, n)
    low = close - rng.uniform(8, 17, n)
    volume = rng.integers(60_000_000, 130_000_000, n).astype(float)

    # Force repeated support/resistance touches with strong reactions.
    high_touch_idx = [35, 62, 88, 117, 143]
    for i, p in zip(high_touch_idx, [996, 992, 998, 994, 997]):
        high[i] = p
        close[i] = p - 18
        low[i] = p - 35
        if i + 1 < n:
            close[i+1] = p - 45
            low[i+1] = p - 60
        volume[i] = 190_000_000

    support_touch_idx = [48, 79, 105, 132, 158]
    for i, p in zip(support_touch_idx, [936, 932, 938, 934, 937]):
        low[i] = p
        close[i] = p + 17
        high[i] = p + 35
        if i + 1 < n:
            close[i+1] = p + 45
            high[i+1] = p + 60
        volume[i] = 210_000_000

    # Deeper support cluster.
    for i, p in zip([20, 96, 149], [832, 838, 835]):
        low[i] = p
        close[i] = p + 20
        high[i] = p + 42
        volume[i] = 180_000_000

    # Higher resistance clusters.
    for i, p in zip([54, 123], [1088, 1093]):
        high[i] = p
        close[i] = p - 25
        low[i] = p - 45
        volume[i] = 175_000_000

    for i, p in zip([70, 137], [1158, 1163]):
        high[i] = p
        close[i] = p - 28
        low[i] = p - 50
        volume[i] = 165_000_000

    # Current state around 965.
    close[-1] = 965
    high[-1] = 980
    low[-1] = 950
    volume[-1] = 200_000_000

    df = pd.DataFrame({
        "Open": close - rng.normal(0, 4, n),
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })

    # ATR / MA / level columns sufficient for strategy.
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.rolling(14, min_periods=3).mean().bfill()
    # Keep current ATR realistic for desired stop buffer.
    df.loc[df.index[-1], "ATR14"] = 35.0
    df["Volume_MA20"] = df["Volume"].rolling(20, min_periods=5).mean().bfill()
    df["Volume_ratio"] = df["Volume"] / df["Volume_MA20"]
    df["MA20"] = df["Close"].rolling(20, min_periods=1).mean()
    df["MA50"] = df["Close"].rolling(50, min_periods=1).mean()
    df["MA200"] = df["Close"].rolling(120, min_periods=1).mean()
    df.loc[df.index[-1], "MA20"] = 915
    df.loc[df.index[-1], "MA50"] = 720
    df.loc[df.index[-1], "MA200"] = 760
    df["Low20"] = df["Low"].rolling(20, min_periods=1).min()
    df["Low60"] = df["Low"].rolling(60, min_periods=1).min()
    df["High20"] = df["High"].rolling(20, min_periods=1).max()
    df["High60"] = df["High"].rolling(60, min_periods=1).max()
    df["PrevHigh20"] = df["High"].shift(1).rolling(20, min_periods=1).max()
    df.loc[df.index[-1], "PrevHigh20"] = 995
    return df


def nearest(levels, target):
    return min(levels, key=lambda x: abs(float(x["center"]) - target))


def run_tests():
    df = synthetic_levels_frame()
    result = discover_levels(df, pivot_order=2, min_score=18)

    assert result["pivot_count"] > 10
    assert result["cluster_count"] >= 4

    supports = result["supports"]
    resistances = result["resistances"]

    s935 = nearest(supports, 935)
    r995 = nearest(resistances, 995)

    assert abs(s935["center"] - 935) <= 15, s935
    assert s935["touches"] >= 2, s935
    assert abs(r995["center"] - 995) <= 15, r995
    assert r995["touches"] >= 2, r995

    plan = build_trade_plan(df, "Pullback in Uptrend")

    # V3 should prefer structure around 935 over MA20=915 as S1.
    assert abs(plan["support1"] - 935) <= 20, plan
    assert plan["stop_loss"] < plan["support1"], plan
    assert plan["breakout_trigger"] > df.iloc[-1]["Close"], plan
    assert plan["tp1"] > df.iloc[-1]["Close"], plan
    assert plan["rr_tp1"] > 0, plan

    print("PASS: V3 level engine")
    print("Pivots:", result["pivot_count"], "Clusters:", result["cluster_count"])
    print("Nearest S1:", s935)
    print("Nearest R1:", r995)
    print("Trade plan:", {k:v for k,v in plan.items() if k != "level_engine"})


if __name__ == "__main__":
    run_tests()
