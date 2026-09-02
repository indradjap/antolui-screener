from __future__ import annotations

from pathlib import Path
from typing import Iterable, List
import io
import pandas as pd


def clean_ticker(v: str) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper()
    if not s or s in {"NAN", "NONE"}:
        return None
    if s.endswith(".JK"):
        s = s[:-3]
    # IDX stock codes are normally compact alphanumeric codes.
    s = "".join(ch for ch in s if ch.isalnum())
    if not (3 <= len(s) <= 8):
        return None
    return s


def normalize_universe(values: Iterable[str]) -> List[str]:
    out, seen = [], set()
    for v in values:
        t = clean_ticker(v)
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def parse_ticker_text(text: str) -> List[str]:
    for sep in [",", ";", "\n", "\t"]:
        text = text.replace(sep, " ")
    return normalize_universe(text.split())


def parse_uploaded_csv(uploaded_bytes: bytes) -> List[str]:
    # Try common CSV encodings and autodetect a likely ticker/code column.
    last_exc = None
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            df = pd.read_csv(io.BytesIO(uploaded_bytes), encoding=enc)
            break
        except Exception as e:
            last_exc = e
    else:
        raise ValueError(f"CSV tidak bisa dibaca: {last_exc}")

    if df.empty:
        return []

    candidates = [
        "ticker", "symbol", "code", "kode", "kode saham", "stock code",
        "kode emiten", "emiten", "security code",
    ]
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    chosen = next((lower_map[c] for c in candidates if c in lower_map), None)
    if chosen is None:
        # Fallback: first column with mostly ticker-looking short strings.
        best = None
        best_ratio = -1
        for c in df.columns:
            vals = df[c].dropna().astype(str).head(300)
            if len(vals) == 0:
                continue
            ratio = sum(clean_ticker(v) is not None for v in vals) / len(vals)
            if ratio > best_ratio:
                best, best_ratio = c, ratio
        chosen = best

    if chosen is None:
        return []
    return normalize_universe(df[chosen].tolist())


def load_seed_universe(path: str | None = None) -> List[str]:
    if path is None:
        path = str(Path(__file__).with_name("idx_liquid_seed.csv"))
    df = pd.read_csv(path)
    col = "Ticker" if "Ticker" in df.columns else df.columns[0]
    return normalize_universe(df[col].tolist())


def load_quality_200() -> List[str]:
    from quality_universe import quality_tickers
    return normalize_universe(quality_tickers())
