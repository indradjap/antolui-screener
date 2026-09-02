from __future__ import annotations

"""Automatic IDX-IC sector classification and sector proxies.

Primary classification source: official IDX listed-company directory.
The module is intentionally fault tolerant:
1) IDX live directory
2) local CSV cache from the last successful IDX request
3) Yahoo metadata for a single symbol (classification fallback only)

For scanner market context, sector performance is represented by an equal-weight
proxy built from the stocks that were successfully downloaded in the scan. This
avoids pretending that an unofficial Yahoo symbol is the official IDX sector index.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, Optional, Any
import json
import re
import time

import numpy as np
import pandas as pd
import requests

try:  # Better success rate with IDX/Cloudflare when available.
    from curl_cffi import requests as curl_requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    curl_requests = None


IDX_DIRECTORY_ENDPOINTS = (
    "https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles",
    "https://www.idx.co.id/umbraco/Surface/ListedCompany/GetCompanyProfiles",
)

# Official IDX-IC high-level sectors and the corresponding sector-index codes.
SECTOR_DEFS = {
    "A": {"name": "Energy", "idx_name": "Energi", "index": "IDXENERGY"},
    "B": {"name": "Basic Materials", "idx_name": "Barang Baku", "index": "IDXBASIC"},
    "C": {"name": "Industrials", "idx_name": "Perindustrian", "index": "IDXINDUST"},
    "D": {"name": "Consumer Non-Cyclicals", "idx_name": "Barang Konsumen Primer", "index": "IDXNONCYC"},
    "E": {"name": "Consumer Cyclicals", "idx_name": "Barang Konsumen Non-Primer", "index": "IDXCYCLIC"},
    "F": {"name": "Healthcare", "idx_name": "Kesehatan", "index": "IDXHEALTH"},
    "G": {"name": "Financials", "idx_name": "Keuangan", "index": "IDXFINANCE"},
    "H": {"name": "Properties & Real Estate", "idx_name": "Properti & Real Estat", "index": "IDXPROPERT"},
    "I": {"name": "Technology", "idx_name": "Teknologi", "index": "IDXTECHNO"},
    "J": {"name": "Infrastructures", "idx_name": "Infrastruktur", "index": "IDXINFRA"},
    "K": {"name": "Transportation & Logistics", "idx_name": "Transportasi & Logistik", "index": "IDXTRANS"},
    "Z": {"name": "Listed Investment Products", "idx_name": "Produk Investasi Tercatat", "index": None},
}


def _norm_text(value: Any) -> str:
    s = "" if value is None else str(value)
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


# Names seen across IDX-IC Indonesian/English labels and Yahoo metadata.
_SECTOR_ALIASES = {
    "A": ["energi", "energy"],
    "B": ["barang baku", "basic materials", "materials"],
    "C": ["perindustrian", "industrials", "industrial"],
    "D": ["barang konsumen primer", "consumer non-cyclicals", "consumer defensive", "consumer staples"],
    "E": ["barang konsumen non-primer", "barang konsumen sekunder", "consumer cyclicals", "consumer cyclical", "consumer discretionary"],
    "F": ["kesehatan", "healthcare", "health care"],
    "G": ["keuangan", "financials", "financial services"],
    "H": ["properti & real estat", "properti dan real estat", "properties & real estate", "real estate"],
    "I": ["teknologi", "technology"],
    "J": ["infrastruktur", "infrastructures", "infrastructure", "communication services", "utilities"],
    "K": ["transportasi & logistik", "transportasi dan logistik", "transportation & logistics", "transportation", "logistics"],
    "Z": ["produk investasi tercatat", "listed investment products"],
}


def sector_code_from_name(name: Any) -> Optional[str]:
    s = _norm_text(name)
    if not s:
        return None
    for code, aliases in _SECTOR_ALIASES.items():
        if s in aliases:
            return code
    # Handle decorated values such as "A - Energi" / "Energy (A)".
    m = re.search(r"(?:^|[\s(\-])([A-KZ])(?:$|[\s)])", str(name).upper())
    if m and m.group(1) in SECTOR_DEFS:
        return m.group(1)
    for code, aliases in _SECTOR_ALIASES.items():
        if any(a in s for a in aliases if len(a) >= 6):
            return code
    return None


@dataclass
class SectorInfo:
    ticker: str
    sector_code: Optional[str] = None
    sector: str = "Unknown"
    idx_sector: str = "Unknown"
    sector_index: Optional[str] = None
    subsector: Optional[str] = None
    industry: Optional[str] = None
    subindustry: Optional[str] = None
    company_name: Optional[str] = None
    source: str = "Unknown"

    def to_dict(self) -> dict:
        return asdict(self)


def _pick(row: dict, *keys: str):
    # Case-insensitive / punctuation-tolerant field lookup.
    if not isinstance(row, dict):
        return None
    norm = {re.sub(r"[^a-z0-9]", "", str(k).lower()): v for k, v in row.items()}
    for key in keys:
        k = re.sub(r"[^a-z0-9]", "", key.lower())
        if k in norm and norm[k] not in (None, ""):
            return norm[k]
    return None


def parse_idx_directory_payload(payload: Any, source: str = "IDX Live") -> pd.DataFrame:
    """Normalize official IDX GetCompanyProfiles response to one row per ticker."""
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("Data") or payload.get("results") or payload.get("Results") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ticker = _pick(r, "KodeEmiten", "Code", "Ticker", "Symbol")
        if not ticker:
            continue
        ticker = str(ticker).strip().upper().replace(".JK", "")
        raw_sector = _pick(r, "Sektor", "Sector")
        code = sector_code_from_name(raw_sector)
        definition = SECTOR_DEFS.get(code or "", {})
        out.append({
            "Ticker": ticker,
            "Sector Code": code,
            "Sector": definition.get("name", str(raw_sector).strip() if raw_sector else "Unknown"),
            "IDX Sector": definition.get("idx_name", str(raw_sector).strip() if raw_sector else "Unknown"),
            "Sector Index": definition.get("index"),
            "Subsector": _pick(r, "SubSektor", "SubSector"),
            "Industry": _pick(r, "Industri", "Industry"),
            "Subindustry": _pick(r, "SubIndustri", "SubIndustry"),
            "Company Name": _pick(r, "NamaEmiten", "Name", "CompanyName"),
            "Source": source,
        })
    if not out:
        return pd.DataFrame(columns=[
            "Ticker", "Sector Code", "Sector", "IDX Sector", "Sector Index",
            "Subsector", "Industry", "Subindustry", "Company Name", "Source",
        ])
    return pd.DataFrame(out).drop_duplicates("Ticker", keep="last").reset_index(drop=True)


def _request_idx_json(url: str, params: dict, timeout: float) -> Any:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.idx.co.id/id/data-pasar/data-saham/daftar-saham/",
    }
    errors = []
    if curl_requests is not None:
        try:
            r = curl_requests.get(url, params=params, headers=headers, timeout=timeout, impersonate="chrome")
            r.raise_for_status()
            return r.json()
        except Exception as e:  # pragma: no cover - network dependent
            errors.append(f"curl_cffi: {e}")
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # pragma: no cover - network dependent
        errors.append(f"requests: {e}")
    raise RuntimeError("; ".join(errors))


def fetch_idx_sector_directory(
    cache_path: str | Path = "idx_sector_cache.csv",
    timeout: float = 12.0,
    force_refresh: bool = False,
    max_cache_age_hours: float = 24.0,
) -> tuple[pd.DataFrame, str]:
    """Load IDX ticker→IDX-IC mapping with local-cache fallback.

    Returns (directory, source_label). Live refresh is skipped when a recent cache
    exists. A stale cache is still preferable to losing sector classification when
    IDX is temporarily unavailable.
    """
    path = Path(cache_path)
    cached = None
    if path.exists():
        try:
            cached = pd.read_csv(path)
            if "Ticker" in cached.columns:
                cached["Ticker"] = cached["Ticker"].astype(str).str.upper().str.replace(".JK", "", regex=False)
            age_h = (time.time() - path.stat().st_mtime) / 3600.0
            if not force_refresh and age_h <= max_cache_age_hours and not cached.empty:
                return cached, "IDX Cache"
        except Exception:
            cached = None

    params = {
        "draw": 1,
        "start": 0,
        "length": 2000,
        "search[value]": "",
        "search[regex]": "false",
    }
    last_error = None
    for url in IDX_DIRECTORY_ENDPOINTS:
        try:
            payload = _request_idx_json(url, params=params, timeout=timeout)
            directory = parse_idx_directory_payload(payload, source="IDX Live")
            if len(directory) >= 100:  # sanity guard: do not overwrite cache with partial junk
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    directory.to_csv(path, index=False)
                except Exception:
                    pass
                return directory, "IDX Live"
            last_error = RuntimeError(f"IDX returned only {len(directory)} usable rows")
        except Exception as e:  # pragma: no cover - network dependent
            last_error = e

    if cached is not None and not cached.empty:
        return cached, "IDX Cache (stale)"
    return parse_idx_directory_payload([]), f"IDX unavailable: {last_error}" if last_error else "IDX unavailable"


def directory_to_map(directory: pd.DataFrame) -> Dict[str, dict]:
    if directory is None or directory.empty:
        return {}
    result = {}
    for _, row in directory.iterrows():
        ticker = str(row.get("Ticker", "")).upper().replace(".JK", "")
        if ticker:
            result[ticker] = row.to_dict()
    return result


def lookup_sector(ticker: str, directory: Optional[pd.DataFrame] = None, source_label: Optional[str] = None) -> SectorInfo:
    code_ticker = str(ticker).strip().upper().replace(".JK", "")
    if directory is not None and not directory.empty and "Ticker" in directory.columns:
        match = directory[directory["Ticker"].astype(str).str.upper().str.replace(".JK", "", regex=False).eq(code_ticker)]
        if not match.empty:
            r = match.iloc[0]
            code = r.get("Sector Code")
            if pd.isna(code):
                code = sector_code_from_name(r.get("Sector"))
            code = str(code) if code and not pd.isna(code) else None
            definition = SECTOR_DEFS.get(code or "", {})
            return SectorInfo(
                ticker=code_ticker,
                sector_code=code,
                sector=str(r.get("Sector") or definition.get("name") or "Unknown"),
                idx_sector=str(r.get("IDX Sector") or definition.get("idx_name") or "Unknown"),
                sector_index=(str(r.get("Sector Index")) if r.get("Sector Index") and not pd.isna(r.get("Sector Index")) else definition.get("index")),
                subsector=None if pd.isna(r.get("Subsector")) else r.get("Subsector"),
                industry=None if pd.isna(r.get("Industry")) else r.get("Industry"),
                subindustry=None if pd.isna(r.get("Subindustry")) else r.get("Subindustry"),
                company_name=None if pd.isna(r.get("Company Name")) else r.get("Company Name"),
                source=source_label or str(r.get("Source") or "IDX"),
            )
    return SectorInfo(ticker=code_ticker)


def yahoo_sector_fallback(ticker: str) -> SectorInfo:
    """Best-effort classification fallback when IDX cannot be reached.

    This is deliberately marked as Yahoo fallback and is never presented as IDX data.
    """
    code_ticker = str(ticker).strip().upper().replace(".JK", "")
    try:  # pragma: no cover - network dependent
        import yfinance as yf
        info = yf.Ticker(code_ticker + ".JK").get_info()
        raw = info.get("sector") or info.get("sectorDisp")
        code = sector_code_from_name(raw)
        definition = SECTOR_DEFS.get(code or "", {})
        if code:
            return SectorInfo(
                ticker=code_ticker,
                sector_code=code,
                sector=definition.get("name", str(raw)),
                idx_sector=definition.get("idx_name", str(raw)),
                sector_index=definition.get("index"),
                company_name=info.get("longName") or info.get("shortName"),
                source="Yahoo fallback",
            )
    except Exception:
        pass
    return SectorInfo(ticker=code_ticker)


def resolve_sector_info(ticker: str, directory: Optional[pd.DataFrame], source_label: Optional[str] = None) -> SectorInfo:
    info = lookup_sector(ticker, directory, source_label=source_label)
    if info.sector_code:
        return info
    return yahoo_sector_fallback(ticker)


def sector_map_for_tickers(tickers: Iterable[str], directory: pd.DataFrame, source_label: Optional[str] = None) -> Dict[str, dict]:
    out = {}
    lookup = directory_to_map(directory)
    for t in tickers:
        code_ticker = str(t).strip().upper().replace(".JK", "")
        r = lookup.get(code_ticker)
        if r:
            code = r.get("Sector Code")
            if pd.isna(code):
                code = sector_code_from_name(r.get("Sector"))
            definition = SECTOR_DEFS.get(str(code) if code else "", {})
            sector_value = r.get("Sector")
            idx_sector_value = r.get("IDX Sector")
            source_value = r.get("Source")
            if sector_value is None or pd.isna(sector_value) or not str(sector_value).strip():
                sector_value = definition.get("name", "Unknown")
            if idx_sector_value is None or pd.isna(idx_sector_value) or not str(idx_sector_value).strip():
                idx_sector_value = definition.get("idx_name", "Unknown")
            if source_value is None or pd.isna(source_value) or not str(source_value).strip():
                source_value = "IDX"
            out[code_ticker] = {
                "sector_code": None if not code or pd.isna(code) else str(code),
                "sector": str(sector_value),
                "idx_sector": str(idx_sector_value),
                "sector_index": r.get("Sector Index") if r.get("Sector Index") and not pd.isna(r.get("Sector Index")) else definition.get("index"),
                "source": source_label or str(source_value),
            }
        else:
            out[code_ticker] = {"sector_code": None, "sector": "Unknown", "idx_sector": "Unknown", "sector_index": None, "source": "Unknown"}
    return out


def build_equal_weight_sector_proxies(
    frames: Dict[str, pd.DataFrame],
    sector_map: Dict[str, dict],
    min_constituents: int = 3,
) -> Dict[str, pd.DataFrame]:
    """Build normalized equal-weight OHLC sector proxies from downloaded scan frames.

    These are explicitly proxies, not the official IDX sector-index calculation.
    Classification membership comes from IDX-IC; the price series is an equal-weight
    aggregate of the successfully downloaded stocks in the current scan.
    """
    grouped: Dict[str, list[pd.DataFrame]] = {}
    for symbol, raw in frames.items():
        ticker = str(symbol).upper().replace(".JK", "")
        info = sector_map.get(ticker) or {}
        code = info.get("sector_code")
        if not code or raw is None or raw.empty:
            continue
        df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
        if len(df) < 80:
            continue
        first = float(df["Close"].iloc[0])
        if not np.isfinite(first) or first <= 0:
            continue
        norm = df[["Open", "High", "Low", "Close"]].astype(float) / first * 100.0
        # Volume is irrelevant to trend_health. Dollar-value normalization gives a stable positive series.
        norm["Volume"] = (df["Close"].astype(float) * df["Volume"].astype(float)) / 1e9
        grouped.setdefault(str(code), []).append(norm)

    proxies = {}
    for code, members in grouped.items():
        if len(members) < min_constituents:
            continue
        fields = {}
        for col in ("Open", "High", "Low", "Close", "Volume"):
            panel = pd.concat([m[col].rename(str(i)) for i, m in enumerate(members)], axis=1)
            # Require a modest breadth of constituents on each date.
            min_count = min(min_constituents, len(members))
            fields[col] = panel.mean(axis=1, skipna=True).where(panel.count(axis=1) >= min_count)
        proxy = pd.DataFrame(fields).dropna()
        if len(proxy) >= 80:
            proxies[code] = proxy
    return proxies


def load_official_sector_index_history(sector_index: Optional[str], period: str = "2y"):
    """Best-effort Yahoo historical lookup for the named official IDX sector index.

    The classification/index *name* comes from IDX. Historical delivery is attempted
    through Yahoo because the existing Antolui Screener OHLC pipeline already uses
    yfinance. If Yahoo does not expose the sector index, callers should continue
    without sector-history context rather than inventing a proxy for Single Stock.
    Returns (resolved_symbol, raw_ohlcv) or (None, None).
    """
    if not sector_index:
        return None, None
    try:  # pragma: no cover - network dependent
        import yfinance as yf
        candidates = []
        try:
            search = yf.Search(str(sector_index), max_results=12)
            for q in getattr(search, "quotes", []) or []:
                sym = q.get("symbol")
                name = " ".join(str(q.get(k, "")) for k in ("shortname", "longname", "displayName"))
                if sym and (str(sector_index).lower() in str(sym).lower() or str(sector_index).lower() in name.lower()):
                    candidates.append(str(sym))
        except Exception:
            pass
        candidates += [str(sector_index), "^" + str(sector_index), str(sector_index) + ".JK"]
        seen = set()
        for symbol in candidates:
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            try:
                df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
                if df is None or df.empty:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                required = ["Open", "High", "Low", "Close", "Volume"]
                if not all(c in df.columns for c in required):
                    continue
                df = df[required].dropna()
                if len(df) >= 220:
                    return symbol, df
            except Exception:
                continue
    except Exception:
        pass
    return None, None
