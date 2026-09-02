from dataclasses import dataclass, asdict

def pts(cond, weight):
    return float(weight if bool(cond) else 0)

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, float(x)))

@dataclass
class LayerResult:
    label: str
    score: float
    details: dict

def structure_layer(df):
    x = df.iloc[-1]

    bull = (
        pts(x["Close"] > x["MA50"],20) +
        pts(x["MA20"] > x["MA50"],20) +
        pts(x["MA50"] > x["MA200"],20) +
        pts(x["MA50_slope"] > 0,15) +
        pts(x["MA200_slope"] > 0,10) +
        pts(x["DI_plus"] > x["DI_minus"],15)
    )

    bear = (
        pts(x["Close"] < x["MA50"],20) +
        pts(x["MA20"] < x["MA50"],20) +
        pts(x["MA50"] < x["MA200"],20) +
        pts(x["MA50_slope"] < 0,15) +
        pts(x["MA200_slope"] < 0,10) +
        pts(x["DI_minus"] > x["DI_plus"],15)
    )

    neutral = max(0, 100-max(bull,bear))
    details = {"Bullish":bull, "Neutral":neutral, "Bearish":bear}

    if bull >= bear and bull >= 60:
        return LayerResult("Bullish", round(bull,1), details)
    if bear > bull and bear >= 60:
        return LayerResult("Bearish", round(bear,1), details)
    return LayerResult("Neutral", round(max(neutral,50),1), details)

def phase_layer(df):
    x = df.iloc[-1]
    scores = {}

    scores["Trend Continuation"] = (
        pts(x["Close"] > x["MA20"],20) +
        pts(x["MA20"] > x["MA50"],20) +
        pts(x["MA50_slope"] > 0,15) +
        pts(x["MACD"] > x["MACD_signal"],15) +
        pts(x["ADX14"] >= 20,15) +
        pts(x["Volume_ratio"] >= 1.0,15)
    )

    scores["Pullback in Uptrend"] = (
        pts(x["MA20"] > x["MA50"],15) +
        pts(x["MA50"] > x["MA200"],15) +
        pts(x["MA50_slope"] > 0,15) +
        pts(x["Close"] > x["MA50"],15) +
        pts(0.03 <= x["drawdown_high20"] <= 0.18,15) +
        pts(-0.03 <= x["dist_MA20"] <= 0.05,10) +
        pts(40 <= x["RSI14"] <= 65,10) +
        pts(x["MACD_hist_change"] > 0,5)
    )

    d = x["Close"]/x["PrevHigh20"] - 1
    scores["Pre-Breakout"] = (
        pts(-0.03 <= d < 0,30) +
        pts(x["MA20"] > x["MA50"],15) +
        pts(x["MA50_slope"] > 0,15) +
        pts(x["RSI14"] >= 50,10) +
        pts(x["ADX14"] >= 18,10) +
        pts(x["Volume_ratio"] >= 1.0,10) +
        pts(x["MACD_hist"] >= 0,10)
    )

    scores["Confirmed Breakout"] = (
        pts(x["Close"] > x["PrevHigh20"],35) +
        pts(x["Volume_ratio"] >= 1.5,25) +
        pts(x["close_location"] >= 0.70,15) +
        pts(x["MA20"] > x["MA50"],10) +
        pts(x["ADX14"] >= 20,10) +
        pts(x["MACD_hist"] > 0,5)
    )

    bb60 = df["BB_width"].rolling(60).mean().iloc[-1]
    scores["Consolidation"] = (
        pts(abs(x["MA50_slope"]) < 0.01,25) +
        pts(x["ADX14"] < 20,25) +
        pts(x["BB_width"] < bb60,25) +
        pts(40 <= x["RSI14"] <= 60,25)
    )

    scores["Overextended"] = (
        pts(x["RSI14"] > 70,25) +
        pts(x["Close"] > x["MA20"] + 2*x["ATR14"],30) +
        pts(x["dist_MA20"] > 0.10,25) +
        pts(x["Close"] >= x["BB_upper"],20)
    )

    # Resolve phase by specificity instead of raw-score tie-breaking.
    # A stock can score highly in several phases simultaneously; the most
    # actionable/specific state should win.
    if scores["Overextended"] >= 75:
        label = "Overextended"
    elif (
        scores["Confirmed Breakout"] >= 75
        and x["Close"] > x["PrevHigh20"]
        and x["Volume_ratio"] >= 1.5
        and x["close_location"] >= 0.70
    ):
        label = "Confirmed Breakout"
    elif scores["Pre-Breakout"] >= 70 and -0.03 <= d < 0:
        label = "Pre-Breakout"
    elif (
        scores["Pullback in Uptrend"] >= 70
        and x["Close"] > x["MA50"]
        and 0.03 <= x["drawdown_high20"] <= 0.18
    ):
        label = "Pullback in Uptrend"
    elif scores["Consolidation"] >= 75 and x["ADX14"] < 20:
        label = "Consolidation"
    else:
        label = "Trend Continuation"

    return LayerResult(label, round(scores[label],1), scores)

def momentum_layer(df):
    x, p = df.iloc[-1], df.iloc[-2]
    scores = {}

    scores["Improving"] = (
        pts(x["MACD_hist"] > p["MACD_hist"],25) +
        pts(x["RSI14"] > p["RSI14"],20) +
        pts(x["MACD"] > x["MACD_signal"],20) +
        pts(x["DI_plus"] > x["DI_minus"],15) +
        pts(x["close_location"] >= 0.60,10) +
        pts(x["Volume_ratio"] >= 1.0,10)
    )

    scores["Weakening"] = (
        pts(x["MACD_hist"] < p["MACD_hist"],25) +
        pts(x["RSI14"] < p["RSI14"],20) +
        pts(x["ADX14"] < p["ADX14"],15) +
        pts(x["Close"] < x["MA20"],20) +
        pts(x["Volume_ratio"] >= 1.0,20)
    )

    scores["Bearish"] = (
        pts(x["MACD"] < x["MACD_signal"],25) +
        pts(x["MACD_hist"] < 0,20) +
        pts(x["RSI14"] < 45,20) +
        pts(x["DI_minus"] > x["DI_plus"],15) +
        pts(x["Close"] < x["MA50"],20)
    )

    scores["Healthy"] = (
        pts(45 <= x["RSI14"] <= 65,25) +
        pts(x["Close"] >= x["MA20"],20) +
        pts(x["MACD_hist"] >= 0,20) +
        pts(x["ADX14"] >= 18,15) +
        pts(0.7 <= x["Volume_ratio"] <= 2.5,20)
    )

    label, score = max(scores.items(), key=lambda z:z[1])
    return LayerResult(label, round(score,1), scores)

def trade_quality(df, structure, phase, momentum):
    x = df.iloc[-1]

    trend = structure.details.get("Bullish",0)
    mom = {"Improving":100,"Healthy":85,"Weakening":45,"Bearish":10}.get(momentum.label,50)
    volume = clamp(x["Volume_ratio"]/1.5*100)

    pos = (
        pts(x["Close"] > x["MA50"],35) +
        pts(x["MA20"] > x["MA50"],25) +
        pts(x["MA50_slope"] > 0,20) +
        pts(x["Close"] > x["MA200"],20)
    )

    penalty = 0
    penalty += 25 if phase.label == "Overextended" else 0
    penalty += 25 if momentum.label == "Bearish" else 0
    penalty += 35 if structure.label == "Bearish" else 0
    penalty += 10 if x["ATR_pct"] > 0.08 else 0

    raw = 0.25*trend + 0.20*phase.score + 0.20*mom + 0.15*volume + 0.20*pos
    total = clamp(raw-penalty)

    return round(total,1), {
        "Trend":round(trend,1),
        "Phase":round(phase.score,1),
        "Momentum":round(mom,1),
        "Volume":round(volume,1),
        "Structure Position":round(pos,1),
        "Penalty":round(penalty,1),
        "Trade Quality":round(total,1),
    }

def action_engine(df, structure, phase, momentum, quality):
    x = df.iloc[-1]

    if structure.label == "Bearish":
        return "AVOID", "Struktur utama bearish."
    if phase.label == "Overextended":
        return "WAIT", "Harga terlalu jauh dari mean."
    if phase.label == "Confirmed Breakout":
        if x["Volume_ratio"] >= 1.5 and quality >= 70 and momentum.label != "Bearish":
            return "BUY CANDIDATE", "Breakout terkonfirmasi dengan volume."
        return "WAIT", "Breakout ada, konfirmasi belum cukup."
    if phase.label == "Pre-Breakout":
        return "WAIT", "Tunggu breakout resistance dengan volume."
    if phase.label == "Pullback in Uptrend":
        if momentum.label in ("Improving","Healthy") and quality >= 70:
            return "BUY CANDIDATE", "Pullback sehat dalam struktur bullish."
        return "WAIT", "Struktur bullish, momentum perlu konfirmasi."
    if phase.label == "Trend Continuation" and quality >= 75:
        return "BUY CANDIDATE", "Trend continuation berkualitas."

    return "WAIT", "Belum ada setup dengan edge yang cukup."

def run_engine(df):
    s = structure_layer(df)
    p = phase_layer(df)
    m = momentum_layer(df)
    q, components = trade_quality(df,s,p,m)
    action, reason = action_engine(df,s,p,m,q)

    return {
        "price":round(float(df.iloc[-1]["Close"]),2),
        "structure":asdict(s),
        "phase":asdict(p),
        "momentum":asdict(m),
        "trade_quality":q,
        "components":components,
        "action":action,
        "action_reason":reason,
    }
