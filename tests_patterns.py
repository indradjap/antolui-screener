import numpy as np
import pandas as pd

from patterns import ema_pattern, vcp_pattern, triangle_pattern, detect_patterns


def ema_frame(kind="fresh2050"):
    n = 70
    df = pd.DataFrame(index=range(n))
    df["Close"] = 102.0
    df["EMA20"] = 98.0
    df["EMA50"] = 100.0
    df["EMA200"] = 90.0
    df["EMA20_slope"] = 0.01
    df["EMA50_slope"] = 0.005
    df["EMA200_slope"] = 0.002

    if kind == "fresh2050":
        df.loc[n-2, "EMA20"] = 99.5
        df.loc[n-1, "EMA20"] = 101.0
    elif kind == "fresh50200":
        df["EMA20"] = 103.0
        df["EMA50"] = 98.0
        df["EMA200"] = 100.0
        df.loc[n-2, "EMA50"] = 99.5
        df.loc[n-1, "EMA50"] = 101.0
    elif kind == "pre":
        df.loc[n-2, "EMA20"] = 98.5
        df.loc[n-1, "EMA20"] = 99.2
        df.loc[n-2, "EMA50"] = 99.9
        df.loc[n-1, "EMA50"] = 100.0
        df["Close"] = 100.0
    return df


def make_vcp():
    n = 100
    close = np.zeros(n)
    for i in range(n):
        if i < 40:
            amp = 14
        elif i < 70:
            amp = 10
        elif i < 85:
            amp = 5
        else:
            amp = 2
        close[i] = 100 + amp * np.sin(2*np.pi*i/8)
    high = close + np.where(np.arange(n) < 70, 1.5, 0.6)
    low = close - np.where(np.arange(n) < 70, 1.5, 0.6)
    volume = np.concatenate([np.full(50, 2_000_000), np.full(30, 1_500_000), np.full(20, 900_000)])
    atrp = np.concatenate([np.full(40, 0.06), np.full(40, 0.035), np.full(20, 0.018)])
    df = pd.DataFrame({"Open":close, "High":high, "Low":low, "Close":close, "Volume":volume})
    df["ATR_pct"] = atrp
    df["Volume_ratio"] = df["Volume"] / pd.Series(volume).rolling(20).mean().bfill()
    df["close_location"] = 0.75
    df["MA50"] = 95.0
    df["MA200"] = 90.0
    # EMA fields needed by detect_patterns
    df["EMA20"] = pd.Series(close).ewm(span=20, adjust=False).mean()
    df["EMA50"] = pd.Series(close).ewm(span=50, adjust=False).mean()
    df["EMA200"] = pd.Series(close).ewm(span=200, adjust=False).mean()
    df["EMA20_slope"] = df["EMA20"].pct_change(5).fillna(0)
    df["EMA50_slope"] = df["EMA50"].pct_change(10).fillna(0)
    df["EMA200_slope"] = df["EMA200"].pct_change(20).fillna(0)
    return df


def make_triangle():
    n = 90
    i = np.arange(n)
    upper = 122 - 0.20*i
    lower = 78 + 0.22*i
    mid = (upper + lower)/2
    amp = (upper - lower)/2 * 0.90
    wave = np.sin(2*np.pi*i/8)
    close = mid + amp*wave
    high = close + 0.5
    low = close - 0.5
    volume = np.linspace(2_000_000, 800_000, n)
    df = pd.DataFrame({"Open":close, "High":high, "Low":low, "Close":close, "Volume":volume})
    df["ATR_pct"] = np.linspace(0.05, 0.015, n)
    df["Volume_ratio"] = df["Volume"] / pd.Series(volume).rolling(20).mean().bfill()
    df["close_location"] = 0.7
    df["MA50"] = 90.0
    df["MA200"] = 85.0
    df["EMA20"] = pd.Series(close).ewm(span=20, adjust=False).mean()
    df["EMA50"] = pd.Series(close).ewm(span=50, adjust=False).mean()
    df["EMA200"] = pd.Series(close).ewm(span=200, adjust=False).mean()
    df["EMA20_slope"] = df["EMA20"].pct_change(5).fillna(0)
    df["EMA50_slope"] = df["EMA50"].pct_change(10).fillna(0)
    df["EMA200_slope"] = df["EMA200"].pct_change(20).fillna(0)
    return df


def run():
    passed=[]

    e = ema_pattern(ema_frame("fresh2050"))
    assert e["label"] == "EMA20/50 Golden Cross", e
    assert e["status"] == "FRESH", e
    assert e["days_since_cross"] == 0, e
    passed.append("fresh EMA20/50 golden cross")

    e = ema_pattern(ema_frame("fresh50200"))
    assert e["label"] == "EMA50/200 Golden Cross", e
    assert e["status"] == "FRESH", e
    passed.append("fresh EMA50/200 major golden cross")

    e = ema_pattern(ema_frame("pre"))
    assert e["label"] == "Pre-Golden Cross", e
    assert e["status"] == "FORMING", e
    passed.append("pre-golden-cross")

    v = vcp_pattern(make_vcp())
    assert v["label"] in {"VCP", "Early VCP"}, v
    assert len(v["contractions"]) == 3, v
    assert v["contractions"][0] > v["contractions"][1] > v["contractions"][2], v
    assert v["volume_dry_up"], v
    assert v["atr_contraction"], v
    passed.append("VCP contraction + dry-up")

    t = triangle_pattern(make_triangle())
    assert t["label"] == "Symmetrical Triangle", t
    assert t["score"] >= 55, t
    passed.append("symmetrical triangle")

    d = detect_patterns(make_vcp())
    assert d["label"] != "None", d
    assert d["score"] >= 50, d
    passed.append("combined pattern engine")

    print(f"PASS: {len(passed)}/{len(passed)}")
    for x in passed:
        print(" -", x)


if __name__ == "__main__":
    run()
