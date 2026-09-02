from __future__ import annotations

import html
import math
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional

import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


USER_AGENT = "Mozilla/5.0 (compatible; AntoluiScreener/5.4; +local research tool)"

# Source quality is deliberately conservative. Unknown blogs/social-like sources are
# not treated as confirmed catalysts even if a headline sounds exciting.
OFFICIAL_SOURCE_HINTS = {
    "idx", "indonesia stock exchange", "bei", "ojk", "bank indonesia",
    "ksei", "kpei", "sec", "company announcement", "press release",
}
ESTABLISHED_MEDIA_HINTS = {
    "reuters", "bloomberg", "cnbc indonesia", "kontan", "bisnis indonesia",
    "bisnis.com", "investor daily", "katadata", "tempo", "antaranews",
    "antara", "the jakarta post", "kompas", "detikfinance", "idx channel",
    "market bisnis", "bareksa",
}

RUMOR_WORDS = {
    "rumor", "rumour", "isu", "dikabarkan", "kabarnya", "beredar",
    "disebut-sebut", "spekulasi", "spekulatif", "rumored", "chatter",
    "gosip", "bocoran", "konon",
}

POSITIVE_WORDS = {
    "buyback", "dividen", "dividend", "akuisisi", "acquisition", "merger",
    "kontrak", "contract", "proyek", "project", "laba naik", "profit rises",
    "rekor laba", "record profit", "ekspansi", "expansion", "upgrade",
    "masuk msci", "msci inclusion", "masuk ftse", "ftse inclusion",
    "strategic investor", "investor strategis", "order book naik", "guidance naik",
    "harga naik", "demand naik", "penjualan naik", "revenue rises", "earnings beat",
    "rights issue oversubscribed", "tender offer premium", "stock split",
}
NEGATIVE_WORDS = {
    "rights issue", "private placement", "dilusi", "dilution", "default",
    "gagal bayar", "suspensi", "suspension", "delisting", "gugatan", "lawsuit",
    "investigasi", "investigation", "rugi", "loss", "profit warning",
    "downgrade", "penjualan turun", "revenue falls", "laba turun", "profit falls",
    "kebakaran", "accident", "shutdown", "penutupan", "fraud", "korupsi",
    "pencabutan izin", "license revoked", "oversupply", "harga turun",
}

CATALYST_GROUPS = {
    "Corporate Action": [
        "rights issue", "private placement", "buyback", "stock split", "dividen",
        "dividend", "tender offer", "spin off", "spin-off", "merger", "akuisisi",
        "acquisition", "divestasi", "divestment",
    ],
    "Earnings/Fundamental": [
        "laba", "profit", "earnings", "pendapatan", "revenue", "margin",
        "guidance", "penjualan", "sales", "cash flow", "ebitda",
    ],
    "Contract/Project": [
        "kontrak", "contract", "proyek", "project", "tender", "order book",
        "smelter", "commissioning", "pabrik", "plant", "capex",
    ],
    "Ownership/M&A": [
        "pemegang saham", "shareholder", "investor strategis", "strategic investor",
        "pengendali", "controller", "takeover", "merger", "akuisisi", "acquisition",
    ],
    "Index/Regulation": [
        "msci", "ftse", "lq45", "idx30", "idx80", "rebalancing", "regulasi",
        "regulation", "ojk", "bei", "free float",
    ],
    "Commodity/Sector": [
        "emas", "gold", "nikel", "nickel", "batubara", "coal", "minyak", "oil",
        "gas", "cpo", "rupiah", "suku bunga", "interest rate", "tarif", "quota",
    ],
}


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: Optional[str]
    provider: str
    category: str
    item_type: str
    bias: str
    source_quality: float
    recency_score: float
    impact_score: float
    reliability_score: float


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _normalize_title(title: str) -> str:
    s = _clean_text(title).lower()
    s = re.sub(r"[^a-z0-9\u00c0-\u024f\u1e00-\u1eff\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _source_quality(source: str) -> float:
    s = (source or "").lower()
    if any(k in s for k in OFFICIAL_SOURCE_HINTS):
        return 1.0
    if any(k in s for k in ESTABLISHED_MEDIA_HINTS):
        return 0.85
    if s:
        return 0.55
    return 0.40


def _parse_pubdate(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _recency_score(dt: Optional[datetime], now: Optional[datetime] = None) -> float:
    if dt is None:
        return 0.45
    now = now or _now_utc()
    age_days = max((now - dt).total_seconds() / 86400.0, 0.0)
    if age_days <= 1:
        return 1.0
    if age_days <= 3:
        return 0.90
    if age_days <= 7:
        return 0.75
    if age_days <= 14:
        return 0.55
    if age_days <= 30:
        return 0.30
    return 0.12


def _category(text: str) -> str:
    t = text.lower()
    best = ("General", 0)
    for category, words in CATALYST_GROUPS.items():
        hits = sum(1 for w in words if w in t)
        if hits > best[1]:
            best = (category, hits)
    return best[0]


def _bias(text: str) -> str:
    t = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    if pos > neg:
        return "Bullish"
    if neg > pos:
        return "Bearish"
    return "Neutral"


def _is_rumor(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in RUMOR_WORDS)


def _impact_score(text: str, category: str) -> float:
    t = text.lower()
    base = {
        "Corporate Action": 0.90,
        "Ownership/M&A": 0.95,
        "Earnings/Fundamental": 0.85,
        "Contract/Project": 0.78,
        "Index/Regulation": 0.82,
        "Commodity/Sector": 0.70,
        "General": 0.45,
    }.get(category, 0.45)

    # Strong-event modifiers.
    if any(k in t for k in ["merger", "akuisisi", "acquisition", "takeover", "tender offer"]):
        base += 0.08
    if any(k in t for k in ["default", "gagal bayar", "suspensi", "delisting", "fraud"]):
        base += 0.10
    return min(base, 1.0)


def classify_item(
    title: str,
    source: str = "",
    published_at: Optional[str] = None,
    url: str = "",
    provider: str = "manual",
    now: Optional[datetime] = None,
) -> NewsItem:
    title_clean = _clean_text(title)
    category = _category(title_clean)
    rumor = _is_rumor(title_clean)
    bias = _bias(title_clean)
    sq = _source_quality(source)
    dt = _parse_pubdate(published_at or "")
    rec = _recency_score(dt, now=now)
    impact = _impact_score(title_clean, category)

    if rumor:
        item_type = "UNCONFIRMED RUMOR"
        # Explicit rumor language is capped regardless of media source.
        reliability = min(0.38, sq * 0.45)
    elif sq >= 0.95:
        item_type = "OFFICIAL/CONFIRMED"
        reliability = 0.98
    elif sq >= 0.80:
        item_type = "REPORTED NEWS"
        reliability = 0.82
    else:
        item_type = "MARKET NARRATIVE"
        reliability = 0.52

    return NewsItem(
        title=title_clean,
        url=url or "",
        source=source or "Unknown",
        published_at=dt.isoformat() if dt else None,
        provider=provider,
        category=category,
        item_type=item_type,
        bias=bias,
        source_quality=round(sq, 3),
        recency_score=round(rec, 3),
        impact_score=round(impact, 3),
        reliability_score=round(reliability, 3),
    )


def _title_tokens(title: str) -> set[str]:
    stop = {
        "dan", "yang", "untuk", "dari", "pada", "dengan", "saham", "emiten",
        "the", "and", "for", "with", "from", "this", "that", "idx", "bei",
    }
    return {w for w in _normalize_title(title).split() if len(w) >= 4 and w not in stop}


def _similarity(a: str, b: str) -> float:
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def dedupe_items(items: Iterable[NewsItem], threshold: float = 0.62) -> List[NewsItem]:
    out: List[NewsItem] = []
    for item in sorted(items, key=lambda x: x.published_at or "", reverse=True):
        duplicate = False
        for existing in out:
            if _similarity(item.title, existing.title) >= threshold:
                # Keep the stronger source/reliability version.
                if item.reliability_score > existing.reliability_score:
                    out.remove(existing)
                    out.append(item)
                duplicate = True
                break
        if not duplicate:
            out.append(item)
    return out


def fetch_google_news(ticker: str, max_items: int = 12, timeout: float = 8.0) -> List[NewsItem]:
    symbol = ticker.upper().replace(".JK", "")
    query = f'"{symbol}" saham OR emiten'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "id",
        "gl": "ID",
        "ceid": "ID:id",
    })
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    out: List[NewsItem] = []
    for node in root.findall(".//item")[:max_items]:
        title = _clean_text(node.findtext("title") or "")
        link = _clean_text(node.findtext("link") or "")
        pub = _clean_text(node.findtext("pubDate") or "")
        source_el = node.find("source")
        source = _clean_text(source_el.text if source_el is not None and source_el.text else "Google News")
        if title:
            out.append(classify_item(title, source, pub, link, provider="Google News RSS"))
    return out


def fetch_yahoo_news(ticker: str, max_items: int = 10) -> List[NewsItem]:
    if yf is None:
        return []
    symbol = ticker.upper()
    if not symbol.endswith(".JK"):
        symbol += ".JK"
    try:
        t = yf.Ticker(symbol)
        raw = t.news or []
    except Exception:
        return []

    out: List[NewsItem] = []
    for entry in raw[:max_items]:
        # yfinance news schema varies across versions.
        content = entry.get("content", entry) if isinstance(entry, dict) else {}
        title = content.get("title") or entry.get("title") if isinstance(entry, dict) else None
        provider = content.get("provider", {}) if isinstance(content, dict) else {}
        source = provider.get("displayName") if isinstance(provider, dict) else None
        source = source or (entry.get("publisher") if isinstance(entry, dict) else None) or "Yahoo Finance"
        url = ""
        canonical = content.get("canonicalUrl", {}) if isinstance(content, dict) else {}
        if isinstance(canonical, dict):
            url = canonical.get("url") or ""
        if not url and isinstance(entry, dict):
            url = entry.get("link") or ""

        pub = None
        if isinstance(content, dict):
            pub = content.get("pubDate") or content.get("displayTime")
        if not pub and isinstance(entry, dict):
            ts = entry.get("providerPublishTime")
            if ts:
                try:
                    pub = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
                except Exception:
                    pub = None
        if title:
            out.append(classify_item(str(title), str(source), pub, str(url), provider="Yahoo Finance"))
    return out


def fetch_news_bundle(ticker: str, max_items: int = 18) -> Dict[str, Any]:
    items: List[NewsItem] = []
    errors: List[str] = []
    try:
        items.extend(fetch_google_news(ticker, max_items=max(8, max_items)))
    except Exception as e:
        errors.append(f"Google News: {e}")
    try:
        items.extend(fetch_yahoo_news(ticker, max_items=10))
    except Exception as e:
        errors.append(f"Yahoo Finance: {e}")

    items = dedupe_items(items)[:max_items]
    summary = summarize_narrative(items)
    summary["items"] = [asdict(x) for x in items]
    summary["errors"] = errors
    summary["ticker"] = ticker.upper().replace(".JK", "")
    summary["fetched_at"] = _now_utc().isoformat()
    return summary


def _corroboration_count(item: NewsItem, items: Iterable[NewsItem]) -> int:
    sources = set()
    for other in items:
        if _similarity(item.title, other.title) >= 0.34 or (
            item.category != "General" and item.category == other.category and _similarity(item.title, other.title) >= 0.20
        ):
            sources.add((other.source or "Unknown").lower())
    return len(sources)


def summarize_narrative(items: Iterable[NewsItem]) -> Dict[str, Any]:
    items = list(items)
    if not items:
        return {
            "catalyst_score": 0.0,
            "confirmed_catalyst_score": 0.0,
            "bias": "Neutral",
            "heat": "Quiet",
            "rumor_risk": "Low",
            "verified_count": 0,
            "rumor_count": 0,
            "narrative_count": 0,
            "top_narrative": "No fresh public narrative found",
            "ranking_overlay": 0.0,
        }

    confirmed_scores = []
    all_scores = []
    bull = bear = 0.0
    rumor_count = 0
    verified_count = 0

    for item in items:
        corroboration = _corroboration_count(item, items)
        corroboration_boost = min(max(corroboration - 1, 0) * 0.08, 0.20)
        effective_reliability = min(item.reliability_score + corroboration_boost, 1.0)
        score = 100 * item.impact_score * item.recency_score * effective_reliability
        all_scores.append(score)

        confirmed = item.item_type in {"OFFICIAL/CONFIRMED", "REPORTED NEWS"} and effective_reliability >= 0.72
        if confirmed:
            confirmed_scores.append(score)
            verified_count += 1
        if item.item_type == "UNCONFIRMED RUMOR":
            rumor_count += 1

        directional = score if item.bias == "Bullish" else (-score if item.bias == "Bearish" else 0.0)
        if directional > 0:
            bull += directional
        elif directional < 0:
            bear += abs(directional)

    # Emphasize the strongest few stories instead of summing every duplicate headline.
    all_top = sorted(all_scores, reverse=True)[:4]
    confirmed_top = sorted(confirmed_scores, reverse=True)[:3]
    catalyst_score = min(100.0, (sum(all_top) / max(len(all_top), 1)) * (1 + min(len(items), 8) * 0.025))
    confirmed_score = min(100.0, (sum(confirmed_top) / max(len(confirmed_top), 1)) * (1 + min(verified_count, 5) * 0.035)) if confirmed_top else 0.0

    if bull > bear * 1.25 and bull >= 15:
        bias = "Bullish"
    elif bear > bull * 1.25 and bear >= 15:
        bias = "Bearish"
    elif bull + bear >= 20:
        bias = "Mixed"
    else:
        bias = "Neutral"

    fresh_strong = sum(1 for x in items if x.recency_score >= 0.75 and x.impact_score >= 0.70)
    if catalyst_score >= 65 or fresh_strong >= 4:
        heat = "Hot"
    elif catalyst_score >= 35 or fresh_strong >= 2:
        heat = "Warm"
    else:
        heat = "Quiet"

    if rumor_count >= 3 and verified_count == 0:
        rumor_risk = "High"
    elif rumor_count >= 1:
        rumor_risk = "Medium"
    else:
        rumor_risk = "Low"

    # Ranking overlay is intentionally tiny and ONLY based on confirmed news.
    # Rumors can appear in the UI but cannot directly boost rank.
    if confirmed_score <= 0:
        overlay = 0.0
    else:
        magnitude = min(5.0, confirmed_score / 20.0)
        if bias == "Bullish":
            overlay = magnitude
        elif bias == "Bearish":
            overlay = -magnitude
        else:
            overlay = 0.0

    strongest = sorted(
        items,
        key=lambda x: x.impact_score * x.recency_score * x.reliability_score,
        reverse=True,
    )[0]

    return {
        "catalyst_score": round(catalyst_score, 1),
        "confirmed_catalyst_score": round(confirmed_score, 1),
        "bias": bias,
        "heat": heat,
        "rumor_risk": rumor_risk,
        "verified_count": verified_count,
        "rumor_count": rumor_count,
        "narrative_count": len(items),
        "top_narrative": strongest.title,
        "ranking_overlay": round(overlay, 1),
    }


def enrich_rows_with_news(
    df,
    top_n: int = 15,
    progress_callback=None,
    apply_confirmed_overlay: bool = False,
):
    """Fetch news only for top N candidates and merge lightweight columns.

    This intentionally avoids making 200 web/news requests during the primary scan.
    """
    import pandas as pd

    if df is None or len(df) == 0:
        return df, {}

    out = df.copy()
    columns = {
        "Catalyst Score": None,
        "Confirmed Catalyst": None,
        "Catalyst Bias": None,
        "Narrative Heat": None,
        "Rumor Risk": None,
        "Verified News": None,
        "Rumor Count": None,
        "Top Narrative": None,
        "News Overlay": 0.0,
        "News Score": None,
    }
    for col, default in columns.items():
        if col not in out.columns:
            out[col] = default

    details = {}
    n = min(int(top_n), len(out))
    for pos, idx in enumerate(out.index[:n], start=1):
        ticker = str(out.at[idx, "Ticker"])
        if progress_callback:
            progress_callback(pos, n, ticker)
        bundle = fetch_news_bundle(ticker)
        details[ticker] = bundle
        out.at[idx, "Catalyst Score"] = bundle["catalyst_score"]
        out.at[idx, "Confirmed Catalyst"] = bundle["confirmed_catalyst_score"]
        out.at[idx, "Catalyst Bias"] = bundle["bias"]
        out.at[idx, "Narrative Heat"] = bundle["heat"]
        out.at[idx, "Rumor Risk"] = bundle["rumor_risk"]
        out.at[idx, "Verified News"] = bundle["verified_count"]
        out.at[idx, "Rumor Count"] = bundle["rumor_count"]
        out.at[idx, "Top Narrative"] = bundle["top_narrative"]
        out.at[idx, "News Overlay"] = bundle["ranking_overlay"]

        base = float(out.at[idx, "Scanner Score"])
        news_score = max(0.0, min(100.0, base + (bundle["ranking_overlay"] if apply_confirmed_overlay else 0.0)))
        out.at[idx, "News Score"] = round(news_score, 1)

        # Gentle pacing for public endpoints.
        time.sleep(0.08)

    if apply_confirmed_overlay:
        # Untouched rows use original score so they don't disappear unexpectedly.
        out["News Score"] = out["News Score"].fillna(out["Scanner Score"])
        out = out.sort_values(["News Score", "Scanner Score"], ascending=[False, False]).reset_index(drop=True)
        out["Rank"] = range(1, len(out) + 1)

    return out, details
