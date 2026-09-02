import numpy as np
import pandas as pd

from patterns import (
    flat_base_pattern, darvas_box_pattern, bull_flag_pattern, cup_handle_pattern,
    high_tight_flag_pattern, volatility_squeeze_pattern, minervini_trend_template, detect_patterns,
)


def frame_from_close(close, volume=None):
    close=np.asarray(close,dtype=float)
    n=len(close)
    if volume is None:
        volume=np.full(n,1_500_000.0)
    high=close*1.008
    low=close*0.992
    open_=close*(1+0.001*np.sin(np.arange(n)))
    df=pd.DataFrame({"Open":open_,"High":high,"Low":low,"Close":close,"Volume":np.asarray(volume,dtype=float)})
    df["MA20"]=df["Close"].rolling(20).mean()
    df["MA50"]=df["Close"].rolling(50).mean()
    df["MA200"]=df["Close"].rolling(200).mean()
    df["MA50_slope"]=df["MA50"].pct_change(10)
    df["EMA20"]=df["Close"].ewm(span=20,adjust=False).mean()
    df["EMA50"]=df["Close"].ewm(span=50,adjust=False).mean()
    df["EMA200"]=df["Close"].ewm(span=200,adjust=False).mean()
    df["EMA20_slope"]=df["EMA20"].pct_change(5)
    df["EMA50_slope"]=df["EMA50"].pct_change(10)
    df["EMA200_slope"]=df["EMA200"].pct_change(20)
    tr=(df["High"]-df["Low"]).abs()
    df["ATR14"]=tr.rolling(14).mean()
    df["ATR_pct"]=df["ATR14"]/df["Close"]
    mid=df["Close"].rolling(20).mean(); std=df["Close"].rolling(20).std()
    df["BB_width"]=(4*std)/mid
    df["Volume_ratio"]=df["Volume"]/df["Volume"].rolling(20).mean()
    rng=(df["High"]-df["Low"]).replace(0,np.nan)
    df["close_location"]=(df["Close"]-df["Low"])/rng
    return df.dropna().reset_index(drop=True)


def make_trending_base():
    # Long uptrend then 30-day tight base near highs with drying volume.
    pre=np.linspace(70,100,500)
    base=103 + 2.2*np.sin(np.linspace(0,6*np.pi,35))
    close=np.r_[pre,base]
    vol=np.r_[np.full(len(pre),2_000_000.0),np.linspace(1_400_000,700_000,len(base))]
    return frame_from_close(close,vol)


def make_bull_flag():
    pre=np.linspace(70,85,500)
    pole=np.linspace(85,108,20)
    flag=np.linspace(106,101,11) + .6*np.sin(np.arange(11))
    close=np.r_[pre,pole,flag]
    vol=np.r_[np.full(len(pre),1_500_000.),np.full(len(pole),3_000_000.),np.full(len(flag),900_000.)]
    return frame_from_close(close,vol)


def make_squeeze():
    pre=np.linspace(70,100,500)
    # progressively tight last 45 days
    tail=[]
    for i in range(45):
        amp=max(.15,2.0*(1-i/45))
        tail.append(102 + amp*np.sin(i))
    close=np.r_[pre,tail]
    vol=np.r_[np.full(len(pre),1_700_000.),np.linspace(1_200_000,500_000,len(tail))]
    df=frame_from_close(close,vol)
    # Force last bar NR7 without changing trend context materially.
    j=df.index[-1]
    c=float(df.loc[j,"Close"])
    df.loc[j,"High"]=c+0.05
    df.loc[j,"Low"]=c-0.05
    return df


def run():
    passed=[]

    base=make_trending_base()
    f=flat_base_pattern(base)
    assert f["label"] == "Flat Base", f
    assert f["score"] >= 62, f
    passed.append("flat base")

    pre=np.linspace(60,100,500)
    box=105+4*np.sin(np.linspace(0,8*np.pi,31))
    ddf=frame_from_close(np.r_[pre,box], np.r_[np.full(len(pre),1_500_000.),np.linspace(1_100_000,700_000,len(box))])
    d=darvas_box_pattern(ddf)
    assert d["label"] == "Darvas Box", d
    passed.append("darvas box")

    bf=bull_flag_pattern(make_bull_flag())
    assert bf["label"] == "Bull Flag", bf
    assert bf["pole_gain_pct"] >= 10, bf
    passed.append("bull flag")

    pre=np.linspace(60,100,450)
    t=np.linspace(-1,1,115)
    cup=110-25*(1-t**2)
    handle=np.linspace(108,102,15)+0.7*np.sin(np.arange(15))
    cdf=frame_from_close(np.r_[pre,cup,handle], np.r_[np.full(len(pre),1_600_000.),np.full(len(cup),1_400_000.),np.full(len(handle),800_000.)])
    ch=cup_handle_pattern(cdf)
    assert ch["label"] == "Cup & Handle", ch
    passed.append("cup and handle")

    pre=np.linspace(40,60,450)
    runup=np.linspace(60,105,45)
    hflag=np.linspace(103,92,15)+np.sin(np.arange(15))
    hdf=frame_from_close(np.r_[pre,runup,hflag], np.r_[np.full(len(pre),1_200_000.),np.full(len(runup),3_000_000.),np.full(len(hflag),900_000.)])
    ht=high_tight_flag_pattern(hdf)
    assert ht["label"] == "High Tight Flag", ht
    assert ht["risk"] == "HIGH", ht
    passed.append("high tight flag")

    sq=volatility_squeeze_pattern(make_squeeze())
    assert sq["nr7"], sq
    assert sq["score"] >= 50, sq
    passed.append("NR7 squeeze")

    tt=minervini_trend_template(base)
    assert tt["score"] >= 75, tt
    assert tt["conditions_met"] >= 6, tt
    passed.append("trend template")

    combo=detect_patterns(base)
    assert "trend_template" in combo and "leader_52w" in combo and "super_setup" in combo, combo.keys()
    assert isinstance(combo["matches"], list)
    passed.append("combined V5.7 pattern engine")

    print(f"PASS: {len(passed)}/{len(passed)}")
    for x in passed:
        print(" -",x)

if __name__ == "__main__":
    run()
