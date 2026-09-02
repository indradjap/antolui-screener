import numpy as np
import pandas as pd

from sector_data import (
    parse_idx_directory_payload,
    sector_code_from_name,
    sector_map_for_tickers,
    build_equal_weight_sector_proxies,
)
from market_context import build_market_context


def make_frame(seed=1, drift=0.0006, n=320):
    rng = np.random.default_rng(seed)
    ret = rng.normal(drift, 0.01, n)
    close = 100 * np.exp(np.cumsum(ret))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.01, n))
    vol = rng.integers(1_000_000, 10_000_000, n)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def enrich(df):
    x = df.copy()
    x["MA20"] = x["Close"].rolling(20).mean()
    x["MA50"] = x["Close"].rolling(50).mean()
    x["MA200"] = x["Close"].rolling(200).mean()
    x["MA50_slope"] = x["MA50"].pct_change(10)
    delta = x["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    rs = gain / loss
    x["RSI14"] = (100 - 100/(1+rs)).fillna(50)
    ema12 = x["Close"].ewm(span=12, adjust=False).mean()
    ema26 = x["Close"].ewm(span=26, adjust=False).mean()
    x["MACD"] = ema12 - ema26
    x["MACD_signal"] = x["MACD"].ewm(span=9, adjust=False).mean()
    x["ADX14"] = 20.0
    x["VolumeFlow20"] = 0.1
    x["VolumeFlow5"] = 0.1
    x["Volume_ratio"] = 1.1
    return x.dropna()


def test_parser():
    payload = {"data": [
        {"KodeEmiten": "ERAA", "NamaEmiten": "Erajaya Swasembada Tbk", "Sektor": "Barang Konsumen Non-Primer", "SubSektor": "Perdagangan Ritel"},
        {"KodeEmiten": "BBCA", "NamaEmiten": "Bank Central Asia Tbk", "Sektor": "Keuangan", "SubSektor": "Bank"},
        {"KodeEmiten": "ANTM", "NamaEmiten": "Aneka Tambang Tbk", "Sektor": "Barang Baku"},
    ]}
    df = parse_idx_directory_payload(payload)
    assert df.set_index("Ticker").loc["ERAA", "Sector Code"] == "E"
    assert df.set_index("Ticker").loc["ERAA", "Sector Index"] == "IDXCYCLIC"
    assert df.set_index("Ticker").loc["BBCA", "Sector Code"] == "G"
    assert df.set_index("Ticker").loc["ANTM", "Sector Code"] == "B"


def test_aliases():
    assert sector_code_from_name("Consumer Cyclical") == "E"
    assert sector_code_from_name("Consumer Defensive") == "D"
    assert sector_code_from_name("Financial Services") == "G"
    assert sector_code_from_name("Technology") == "I"


def test_proxy_and_context():
    directory = parse_idx_directory_payload({"data": [
        {"KodeEmiten": "AAA", "Sektor": "Energi"},
        {"KodeEmiten": "BBB", "Sektor": "Energi"},
        {"KodeEmiten": "CCC", "Sektor": "Energi"},
    ]})
    smap = sector_map_for_tickers(["AAA", "BBB", "CCC"], directory)
    frames = {"AAA.JK": make_frame(1, .0010), "BBB.JK": make_frame(2, .0007), "CCC.JK": make_frame(3, .0005)}
    proxies = build_equal_weight_sector_proxies(frames, smap, min_constituents=3)
    assert "A" in proxies and len(proxies["A"]) > 250
    stock, bench, sector = enrich(frames["AAA.JK"]), enrich(make_frame(9, .0002)), enrich(proxies["A"])
    ctx = build_market_context(stock, bench, sector_df=sector, sector_name="Energy EW Proxy")
    assert ctx["sector_relative_strength"] is not None
    assert 0 <= ctx["sector_relative_strength"]["score"] <= 100
    assert 0 <= ctx["combined_relative_strength"]["score"] <= 100
    assert ctx["sector"] is not None


if __name__ == "__main__":
    tests = [test_parser, test_aliases, test_proxy_and_context]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"{len(tests)}/{len(tests)} sector tests passed")
