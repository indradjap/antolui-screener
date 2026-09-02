import pandas as pd
from timing_engine import build_timing_plan


def frame(price=100, atr=3, vol=1.0, close_loc=.65):
    return pd.DataFrame([
        {"Close":price*0.99,"ATR14":atr,"Volume_ratio":vol,"close_location":.55},
        {"Close":price,"ATR14":atr,"Volume_ratio":vol,"close_location":close_loc},
    ])


def technical(phase="Pullback in Uptrend", momentum="Healthy", structure="Bullish", action="BUY CANDIDATE"):
    return {
        "phase":{"label":phase}, "momentum":{"label":momentum},
        "structure":{"label":structure}, "action":action,
    }


def context(label="Supportive", rs="Outperforming", flow="Accumulation"):
    return {"label":label,"relative_strength":{"label":rs},"volume_flow":{"label":flow}}


def candidate(kind, entry, low, high, stop, score=85, rr=2.5):
    return {"type":kind,"entry":entry,"entry_low":low,"entry_high":high,"stop":stop,"score":score,"rr_tp2":rr}


def plan(cands, best=None, supply=None):
    return {"candidates":cands,"best":best or cands[0],"nearest_supply":supply}


# 1 retest is actionable now
c=candidate("DEMAND RETEST",100,98,102,94,88,2.6)
r=build_timing_plan(frame(100,vol=.9),technical(),context(),{}, {},plan([c]))
assert r["status"] == "BUY NOW", r

# 2 price above demand -> wait retest
r=build_timing_plan(frame(105),technical(),context(),{}, {},plan([c]))
assert r["status"] == "WAIT RETEST", r

# 3 breakout below pivot -> wait breakout
b=candidate("PATTERN PIVOT",105,105,108,98,86,2.4)
r=build_timing_plan(frame(101,vol=1.1),technical("Pre-Breakout"),context(),{}, {},plan([b]))
assert r["status"] == "WAIT BREAKOUT", r

# 4 breakout in zone + volume -> buy now
r=build_timing_plan(frame(106,vol=1.8,close_loc=.78),technical("Confirmed Breakout","Improving"),context(),{}, {},plan([b]))
assert r["status"] == "BUY NOW", r

# 5 extended -> too extended
r=build_timing_plan(frame(120,atr=3,vol=1.2),technical("Overextended"),context(),{}, {},plan([b]))
assert r["status"] == "TOO EXTENDED", r

# 6 bearish -> avoid
r=build_timing_plan(frame(100),technical(structure="Bearish", action="AVOID"),context(),{}, {},plan([c]))
assert r["status"] == "AVOID", r

# 7 invalidated -> invalidated
r=build_timing_plan(frame(93),technical(),context(),{}, {},plan([c]))
assert r["status"] == "INVALIDATED", r

# 8 actionable candidate beats distant theoretical retest
retest=candidate("DEMAND RETEST",92,90,94,86,92,4.0)
breakout=candidate("BREAKOUT CONFIRMATION",100,99,102,95,80,2.0)
r=build_timing_plan(frame(100,vol=1.8,close_loc=.8),technical("Confirmed Breakout","Improving"),context(),{}, {},plan([retest,breakout],best=retest))
assert r["active"]["type"] == "BREAKOUT CONFIRMATION", r
assert r["status"] == "BUY NOW", r

print("TIMING ENGINE PASS 8/8")
