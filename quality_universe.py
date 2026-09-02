from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import pandas as pd

TIER_DEFAULTS = {
    "A": {"profile": "Core quality/liquid", "adjustment": 3.0, "min_liquidity_rpb": 5.0, "min_rr2": 1.5, "top_min_score": 70.0},
    "B": {"profile": "Quality / liquid mid-cap", "adjustment": 0.0, "min_liquidity_rpb": 5.0, "min_rr2": 1.7, "top_min_score": 74.0},
    "C": {"profile": "Tactical / higher-beta", "adjustment": -5.0, "min_liquidity_rpb": 10.0, "min_rr2": 2.0, "top_min_score": 85.0},
    "U": {"profile": "Unclassified", "adjustment": -2.0, "min_liquidity_rpb": 10.0, "min_rr2": 2.0, "top_min_score": 80.0},
}

@lru_cache(maxsize=1)
def load_quality_table() -> pd.DataFrame:
    path = Path(__file__).with_name("idx_quality_200.csv")
    df = pd.read_csv(path)
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.replace(".JK", "", regex=False)
    df["Tier"] = df["Tier"].astype(str).str.upper()
    return df

@lru_cache(maxsize=1)
def quality_map() -> dict:
    return {row.Ticker: row._asdict() for row in load_quality_table().itertuples(index=False)}

def get_tier_info(ticker: str) -> dict:
    t = str(ticker).upper().replace(".JK", "")
    row = quality_map().get(t)
    if row:
        tier = str(row.get("Tier", "U")).upper()
        defaults = TIER_DEFAULTS.get(tier, TIER_DEFAULTS["U"])
        return {
            "ticker": t,
            "tier": tier,
            "profile": row.get("Profile", defaults["profile"]),
            "adjustment": float(row.get("TierAdjustment", defaults["adjustment"])),
            "min_liquidity_rpb": float(row.get("MinLiquidityRpB", defaults["min_liquidity_rpb"])),
            "min_rr2": float(row.get("MinRR2", defaults["min_rr2"])),
            "top_min_score": float(row.get("TopCandidateMinScore", defaults["top_min_score"])),
        }
    d = TIER_DEFAULTS["U"]
    return {"ticker": t, "tier": "U", **d}

def quality_tickers() -> list[str]:
    return load_quality_table()["Ticker"].tolist()

def tier_counts() -> dict[str, int]:
    return load_quality_table()["Tier"].value_counts().sort_index().to_dict()
