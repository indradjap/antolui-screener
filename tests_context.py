import numpy as np
import pandas as pd
from market_context import relative_strength_metrics, trend_health, volume_flow, build_market_context
from decision import combine_decision


def make_frame(start=100, end=130, n=240, bullish=True, flow=0.25):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = np.linspace(start, end, n)
    ma20 = pd.Series(close).rolling(20, min_periods=1).mean().to_numpy()
    ma50 = pd.Series(close).rolling(50, min_periods=1).mean().to_numpy()
    ma200 = pd.Series(close).rolling(200, min_periods=1).mean().to_numpy()

    if not bullish:
        close = np.linspace(start, end, n)
        ma20 = pd.Series(close).rolling(20, min_periods=1).mean().to_numpy()
        ma50 = pd.Series(close).rolling(50, min_periods=1).mean().to_numpy()
        ma200 = pd.Series(close).rolling(200, min_periods=1).mean().to_numpy()

    df = pd.DataFrame(index=idx)
    df["Close"] = close
    df["MA20"] = ma20
    df["MA50"] = ma50
    df["MA200"] = ma200
    df["MA50_slope"] = pd.Series(ma50).pct_change(10).fillna(0).to_numpy()
    df["RSI14"] = 60 if end > start else 35
    df["MACD"] = 2 if end > start else -2
    df["MACD_signal"] = 1 if end > start else -1
    df["ADX14"] = 25
    df["VolumeFlow20"] = flow
    df["VolumeFlow5"] = flow
    df["Volume_ratio"] = 1.6
    return df


def run_tests():
    tests = []

    bench = make_frame(100, 115)
    stock = make_frame(100, 155, flow=0.35)
    rs = relative_strength_metrics(stock, bench)
    assert rs["label"] == "Outperforming"
    assert rs["score"] >= 70
    tests.append("outperforming relative strength")

    weak_stock = make_frame(100, 60, bullish=False, flow=-0.35)
    bear_bench = make_frame(100, 80, bullish=False, flow=-0.2)
    ctx = build_market_context(weak_stock, bear_bench, benchmark_name="IHSG")
    assert ctx["label"] == "Headwind"
    assert ctx["benchmark"]["label"] == "Bearish"
    assert ctx["volume_flow"]["label"] == "Distribution"
    tests.append("headwind context")

    sector = make_frame(100, 140, flow=0.2)
    ctx2 = build_market_context(stock, bench, sector_df=sector, benchmark_name="IHSG", sector_name="SECTOR")
    assert ctx2["label"] == "Supportive"
    assert ctx2["sector"]["label"] == "Bullish"
    tests.append("supportive sector context")

    technical_buy = {
        "trade_quality": 82,
        "action": "BUY CANDIDATE",
        "action_reason": "Technical setup kuat.",
        "phase": {"label": "Confirmed Breakout"},
        "momentum": {"label": "Improving"},
    }
    d1 = combine_decision(technical_buy, ctx2)
    assert d1["final_action"] == "BUY CANDIDATE"
    tests.append("buy survives supportive context")

    d2 = combine_decision(technical_buy, ctx)
    assert d2["final_action"] == "WAIT"
    tests.append("buy downgraded by headwind")

    print(f"PASS: {len(tests)}/{len(tests)}")
    for t in tests:
        print(" -", t)


if __name__ == "__main__":
    run_tests()
