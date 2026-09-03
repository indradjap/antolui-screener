from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import math
import pandas as pd

HISTORY_FILE = Path(__file__).with_name("analyst_pick_history.csv")


def _boolish(v):
    if pd.isna(v):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "hit", "win"}:
        return True
    if s in {"0", "false", "no", "n", "miss", "loss"}:
        return False
    return None


def load_history(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else HISTORY_FILE
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


def _resolved_outcomes(group: pd.DataFrame) -> tuple[int, int, int]:
    """Return resolved count, TP1 wins, TP2 wins.

    Calibration is deliberately based on resolved outcomes, never on how often an
    analyst selected a setup. This prevents selection frequency from being mistaken
    for predictive edge.
    """
    resolved = 0
    tp1_wins = 0
    tp2_wins = 0
    for _, r in group.iterrows():
        tp1 = _boolish(r.get("tp1_before_sl"))
        sl = _boolish(r.get("sl_before_tp1"))
        tp2 = _boolish(r.get("tp2_before_sl"))
        if tp1 is None and sl is None:
            continue
        resolved += 1
        if tp1 is True:
            tp1_wins += 1
        if tp2 is True:
            tp2_wins += 1
    return resolved, tp1_wins, tp2_wins


def setup_calibration(setup_family: str, path: str | Path | None = None) -> Dict[str, Any]:
    """Outcome-based Bayesian calibration for a setup family.

    A neutral Beta(5,5) prior is used and calibration is disabled until at least
    10 resolved examples exist. Even then the score adjustment is capped to +/-5
    points so live price structure remains dominant.
    """
    hist = load_history(path)
    if hist.empty or "setup_family" not in hist.columns:
        return {"active": False, "n": 0, "posterior_tp1": 0.5, "score_adjustment": 0.0}
    subset = hist[hist["setup_family"].astype(str).str.upper() == str(setup_family).upper()]
    resolved, wins, tp2_wins = _resolved_outcomes(subset)
    posterior = (wins + 5.0) / (resolved + 10.0)
    # TP2 is a secondary quality signal; only small influence after enough data.
    posterior_tp2 = (tp2_wins + 3.0) / (resolved + 6.0) if resolved else 0.5
    active = resolved >= 10
    raw_adj = (posterior - 0.5) * 16.0 + (posterior_tp2 - 0.5) * 4.0
    adj = max(-5.0, min(5.0, raw_adj)) if active else 0.0
    return {
        "active": active,
        "n": int(resolved),
        "posterior_tp1": round(float(posterior), 3),
        "posterior_tp2": round(float(posterior_tp2), 3),
        "score_adjustment": round(float(adj), 2),
    }


def research_summary(path: str | Path | None = None) -> Dict[str, Any]:
    hist = load_history(path)
    if hist.empty:
        return {"examples": 0, "resolved": 0, "setups": {}}
    setups = {}
    resolved_total = 0
    if "setup_family" in hist.columns:
        for setup, grp in hist.groupby("setup_family", dropna=False):
            resolved, wins, tp2_wins = _resolved_outcomes(grp)
            resolved_total += resolved
            setups[str(setup)] = {
                "examples": int(len(grp)),
                "resolved": int(resolved),
                "tp1_wins": int(wins),
                "tp2_wins": int(tp2_wins),
            }
    return {"examples": int(len(hist)), "resolved": int(resolved_total), "setups": setups}
