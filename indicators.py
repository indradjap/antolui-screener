import pandas as pd
from ta.trend import MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange

def add_indicators(df):
    df = df.copy()

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()

    # EMA family for pattern screener / golden-cross engine
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()

    df["MA20_slope"] = df["MA20"].pct_change(5)
    df["MA50_slope"] = df["MA50"].pct_change(10)
    df["MA200_slope"] = df["MA200"].pct_change(20)
    df["EMA20_slope"] = df["EMA20"].pct_change(5)
    df["EMA50_slope"] = df["EMA50"].pct_change(10)
    df["EMA200_slope"] = df["EMA200"].pct_change(20)

    df["RSI14"] = RSIIndicator(df["Close"], 14).rsi()

    # Stochastic RSI confirmation for execution-style / Quick Pick setups.
    # Price structure remains primary; this is only a momentum confirmation.
    rsi_low = df["RSI14"].rolling(14).min()
    rsi_high = df["RSI14"].rolling(14).max()
    stoch_den = (rsi_high - rsi_low).replace(0, pd.NA)
    df["StochRSI"] = ((df["RSI14"] - rsi_low) / stoch_den) * 100.0
    df["StochRSI_K"] = df["StochRSI"].rolling(3).mean()
    df["StochRSI_D"] = df["StochRSI_K"].rolling(3).mean()

    m = MACD(df["Close"], 26, 12, 9)
    df["MACD"] = m.macd()
    df["MACD_signal"] = m.macd_signal()
    df["MACD_hist"] = m.macd_diff()
    df["MACD_hist_change"] = df["MACD_hist"].diff()

    a = ADXIndicator(df["High"], df["Low"], df["Close"], 14)
    df["ADX14"] = a.adx()
    df["DI_plus"] = a.adx_pos()
    df["DI_minus"] = a.adx_neg()

    atr = AverageTrueRange(df["High"], df["Low"], df["Close"], 14)
    df["ATR14"] = atr.average_true_range()
    df["ATR_pct"] = df["ATR14"] / df["Close"]

    bb = BollingerBands(df["Close"], 20, 2)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_mid"] = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()
    df["BB_width"] = (df["BB_upper"]-df["BB_lower"])/df["BB_mid"]

    df["Volume_MA20"] = df["Volume"].rolling(20).mean()
    df["Volume_ratio"] = df["Volume"] / df["Volume_MA20"]

    # Signed volume-flow proxy: +1 means volume concentrated on up-closes,
    # -1 means volume concentrated on down-closes.
    direction = df["Close"].diff().fillna(0)
    signed_volume = df["Volume"].where(direction > 0, -df["Volume"].where(direction < 0, 0))
    abs_volume = df["Volume"].where(direction != 0, 0)
    df["VolumeFlow5"] = signed_volume.rolling(5).sum() / abs_volume.rolling(5).sum().replace(0, pd.NA)
    df["VolumeFlow20"] = signed_volume.rolling(20).sum() / abs_volume.rolling(20).sum().replace(0, pd.NA)

    df["High20"] = df["High"].rolling(20).max()
    df["Low20"] = df["Low"].rolling(20).min()
    df["High60"] = df["High"].rolling(60).max()
    df["Low60"] = df["Low"].rolling(60).min()
    df["PrevHigh20"] = df["High"].shift(1).rolling(20).max()

    df["dist_MA20"] = df["Close"]/df["MA20"] - 1
    df["dist_MA50"] = df["Close"]/df["MA50"] - 1
    df["drawdown_high20"] = 1 - df["Close"]/df["High20"]

    rng = (df["High"]-df["Low"]).replace(0, pd.NA)
    df["close_location"] = (df["Close"]-df["Low"]) / rng

    return df
