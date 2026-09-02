import pandas as pd
from engine import run_engine
from strategy import build_trade_plan


def frame(prev, cur):
    return pd.DataFrame([prev] * 60 + [cur])


def base_row():
    return dict(
        Close=100, MA20=98, MA50=95, MA200=90,
        MA50_slope=0.02, MA200_slope=0.01,
        DI_plus=30, DI_minus=15,
        MACD=2.0, MACD_signal=1.5, MACD_hist=0.5,
        MACD_hist_change=0.1,
        ADX14=25, Volume_ratio=1.2, RSI14=58,
        drawdown_high20=0.05, dist_MA20=0.02,
        PrevHigh20=105, High20=105, High60=110,
        Low20=92, Low60=85,
        close_location=0.8, BB_width=0.10, BB_upper=110,
        ATR14=3, ATR_pct=0.03,
    )


def run_tests():
    tests = []

    # Healthy pullback
    cur = base_row()
    cur.update(Close=97, MA20=99, MA50=94, MA200=88,
               dist_MA20=-0.0202, drawdown_high20=0.10,
               RSI14=52, MACD=1.2, MACD_signal=1.0,
               MACD_hist=0.2, MACD_hist_change=0.1,
               Volume_ratio=0.9, close_location=0.65,
               PrevHigh20=108, High20=108, High60=112,
               Low20=93, Low60=86)
    prev = cur.copy(); prev.update(MACD_hist=0.1, RSI14=50, ADX14=24)
    r = run_engine(frame(prev, cur))
    assert r["phase"]["label"] == "Pullback in Uptrend"
    assert r["action"] == "BUY CANDIDATE"
    tests.append("healthy pullback")

    # Pre-breakout
    cur = base_row()
    cur.update(Close=103, PrevHigh20=105, High20=105,
               High60=110, MA20=99, MA50=94, MA200=88,
               RSI14=60, MACD_hist=0.4, MACD_hist_change=0.1,
               Volume_ratio=1.2, close_location=0.75,
               drawdown_high20=0.02, dist_MA20=0.04,
               Low20=95, Low60=87)
    prev = cur.copy(); prev.update(MACD_hist=0.3, RSI14=58, ADX14=24)
    r = run_engine(frame(prev, cur))
    assert r["phase"]["label"] == "Pre-Breakout"
    assert r["action"] == "WAIT"
    tests.append("pre-breakout")

    # Confirmed breakout
    cur = base_row()
    cur.update(Close=108, PrevHigh20=105, High20=108,
               High60=112, MA20=100, MA50=95, MA200=88,
               RSI14=67, MACD_hist=0.8, MACD_hist_change=0.3,
               Volume_ratio=2.0, close_location=0.9,
               drawdown_high20=0.0, dist_MA20=0.08,
               Low20=96, Low60=88)
    prev = cur.copy(); prev.update(MACD_hist=0.5, RSI14=62, ADX14=23)
    df = frame(prev, cur)
    r = run_engine(df)
    plan = build_trade_plan(df, r["phase"]["label"])
    assert r["phase"]["label"] == "Confirmed Breakout"
    assert r["action"] == "BUY CANDIDATE"
    assert plan["breakout_trigger"] == 105.0
    tests.append("confirmed breakout")

    # Overextended should override trend-continuation score ties
    cur = base_row()
    cur.update(Close=125, PrevHigh20=120, High20=125, High60=125,
               MA20=100, MA50=95, MA200=88, RSI14=78,
               MACD_hist=1.0, MACD_hist_change=0.2,
               Volume_ratio=1.5, close_location=0.9,
               drawdown_high20=0.0, dist_MA20=0.25,
               BB_upper=118, ATR14=5, ATR_pct=0.04,
               Low20=98, Low60=88)
    prev = cur.copy(); prev.update(MACD_hist=0.8, RSI14=75, ADX14=24)
    r = run_engine(frame(prev, cur))
    assert r["phase"]["label"] == "Overextended"
    assert r["action"] == "WAIT"
    tests.append("overextended override")

    # Bearish structure
    cur = base_row()
    cur.update(Close=80, MA20=85, MA50=90, MA200=100,
               MA50_slope=-0.02, MA200_slope=-0.01,
               DI_plus=12, DI_minus=32,
               MACD=-2, MACD_signal=-1, MACD_hist=-1,
               MACD_hist_change=-0.2, RSI14=35, ADX14=28,
               Volume_ratio=1.3, drawdown_high20=0.20,
               dist_MA20=-0.0588, PrevHigh20=100,
               High20=100, High60=110, Low20=78, Low60=70,
               close_location=0.25, BB_upper=95, ATR14=3,
               ATR_pct=0.0375)
    prev = cur.copy(); prev.update(MACD_hist=-0.8, RSI14=38, ADX14=27)
    r = run_engine(frame(prev, cur))
    assert r["structure"]["label"] == "Bearish"
    assert r["action"] == "AVOID"
    tests.append("bearish avoid")

    # Consolidation
    cur = base_row()
    cur.update(Close=100, MA20=100, MA50=100, MA200=98,
               MA50_slope=0.001, MA200_slope=0.001,
               DI_plus=18, DI_minus=17, MACD=0.1,
               MACD_signal=0.1, MACD_hist=0,
               MACD_hist_change=-0.02, RSI14=50, ADX14=14,
               Volume_ratio=0.8, drawdown_high20=0.04,
               dist_MA20=0, PrevHigh20=104, High20=104,
               High60=105, Low20=96, Low60=94,
               close_location=0.5, BB_width=0.04,
               BB_upper=104, ATR14=1.5, ATR_pct=0.015)
    prev = cur.copy(); prev.update(MACD_hist=0.02, RSI14=51, ADX14=15)
    r = run_engine(frame(prev, cur))
    assert r["phase"]["label"] == "Consolidation"
    assert r["action"] == "WAIT"
    tests.append("consolidation")

    # VKTR screenshot-like state
    prev = dict(
        Close=950, MA20=905, MA50=715, MA200=750,
        MA50_slope=0.025, MA200_slope=0.012,
        DI_plus=28, DI_minus=19,
        MACD=51, MACD_signal=49, MACD_hist=2,
        MACD_hist_change=0.5,
        ADX14=35, Volume_ratio=1.2, RSI14=61,
        drawdown_high20=0.09, dist_MA20=0.05,
        PrevHigh20=995, High20=1060, High60=1340,
        Low20=835, Low60=500,
        close_location=0.55, BB_width=0.25,
        BB_upper=1100, ATR14=35, ATR_pct=0.037,
    )
    cur = prev.copy()
    cur.update(Close=965, MA20=915, MA50=720, MA200=760,
               MACD=49, MACD_signal=50, MACD_hist=-1,
               MACD_hist_change=-3, ADX14=33,
               Volume_ratio=2.7, RSI14=58,
               dist_MA20=(965 / 915 - 1), close_location=0.70)
    df = frame(prev, cur)
    r = run_engine(df)
    plan = build_trade_plan(df, r["phase"]["label"])
    assert r["structure"]["label"] == "Bullish"
    assert r["phase"]["label"] == "Pullback in Uptrend"
    assert r["momentum"]["label"] == "Weakening"
    assert r["action"] == "WAIT"
    assert plan["breakout_trigger"] == 995.0
    tests.append("VKTR screenshot-like")

    print(f"PASS: {len(tests)}/{len(tests)}")
    for t in tests:
        print(" -", t)


if __name__ == "__main__":
    run_tests()
