import html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data import load_stock, load_benchmark, download_universe
from indicators import add_indicators
from engine import run_engine
from strategy import build_trade_plan
from entry_engine import build_entry_plan
from timing_engine import build_timing_plan
from market_context import build_market_context, trend_health
from decision import combine_decision
from scanner import scan_frames
from universe import load_seed_universe, load_quality_200, parse_ticker_text, parse_uploaded_csv
from quality_universe import tier_counts
from patterns import detect_patterns
from news_narrative import fetch_news_bundle, enrich_rows_with_news
from sector_data import (
    fetch_idx_sector_directory, resolve_sector_info, sector_map_for_tickers,
    build_equal_weight_sector_proxies, load_official_sector_index_history,
)


APP_VERSION = "5.9"

st.set_page_config(
    page_title=f"Antolui Screener V{APP_VERSION}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------- Compact professional UI ----------
st.markdown(
    """
<style>
:root {
  --as-bg: #07101f;
  --as-surface: #0d1728;
  --as-surface2: #111d31;
  --as-surface3: #152238;
  --as-border: rgba(148,163,184,.18);
  --as-border-strong: rgba(148,163,184,.28);
  --as-text: #f4f7fb;
  --as-muted: #9aaac0;
  --as-dim: #718198;
  --as-blue: #5b91ff;
  --as-green: #34d399;
  --as-red: #fb7185;
  --as-amber: #fbbf24;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--as-bg) !important;
  color: var(--as-text) !important;
}
html, body, [class*="css"], .stApp {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}
.block-container, [data-testid="stMainBlockContainer"] {
  padding-top: .65rem !important;
  padding-bottom: 2rem !important;
  padding-left: 1.15rem !important;
  padding-right: 1.15rem !important;
  max-width: 1540px !important;
}
header[data-testid="stHeader"] { height:0 !important; min-height:0 !important; background:transparent !important; }
[data-testid="stToolbar"] { display:none !important; }
h1,h2,h3,h4,h5,h6,p,li,label,span,div { color: inherit; }
h1 { font-size:1.45rem !important; margin:.1rem 0 .2rem !important; }
h2 { font-size:1.08rem !important; margin:.65rem 0 .3rem !important; }
h3 { font-size:.94rem !important; margin:.5rem 0 .25rem !important; }
p, li, label, .stMarkdown { font-size:.82rem; line-height:1.38; }
small, .stCaption, [data-testid="stCaptionContainer"] { color:var(--as-muted) !important; }
.ss-header {
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
  min-height:58px; padding:.58rem .78rem; border:1px solid var(--as-border); border-radius:14px;
  background:linear-gradient(110deg, rgba(91,145,255,.14), rgba(13,23,40,.94) 43%, rgba(9,17,31,.98));
  box-shadow:0 10px 30px rgba(0,0,0,.16); margin-bottom:.45rem;
}
.ss-brand { color:var(--as-text) !important; font-size:1.02rem; font-weight:850; letter-spacing:.10em; }
.ss-sub { color:var(--as-muted) !important; font-size:.70rem; margin-top:.05rem; }
.ss-badge { display:inline-flex; align-items:center; padding:.20rem .46rem; border-radius:999px; border:1px solid rgba(91,145,255,.38); color:#bdd1ff !important; background:rgba(91,145,255,.10); font-size:.64rem; font-weight:750; white-space:nowrap; }
.ss-section { display:flex; align-items:center; gap:.42rem; margin:.68rem 0 .34rem; color:#dce7f6 !important; font-size:.80rem; font-weight:760; letter-spacing:.02em; }
.ss-section::before { content:""; width:3px; height:14px; border-radius:3px; background:var(--as-blue); }
.ss-hero { display:grid; grid-template-columns:minmax(250px,1.2fr) minmax(430px,2fr); gap:.75rem; padding:.78rem .86rem; border:1px solid var(--as-border); border-radius:14px; background:linear-gradient(125deg, rgba(17,29,49,.96), rgba(9,17,31,.95)); box-shadow:0 12px 32px rgba(0,0,0,.18); margin:.25rem 0 .55rem; }
.ss-identity { display:flex; flex-direction:column; justify-content:center; min-width:0; }
.ss-ticker-line { display:flex; align-items:baseline; gap:.60rem; flex-wrap:wrap; }
.ss-ticker { color:var(--as-text) !important; font-size:1.55rem; font-weight:850; letter-spacing:.015em; }
.ss-price { color:var(--as-text) !important; font-size:1.55rem; font-weight:720; }
.ss-meta { color:var(--as-muted) !important; font-size:.72rem; margin-top:.16rem; }
.ss-status-row { display:flex; align-items:center; gap:.42rem; margin-top:.55rem; flex-wrap:wrap; }
.ss-pill { display:inline-flex; align-items:center; border-radius:999px; padding:.27rem .55rem; font-size:.68rem; font-weight:800; letter-spacing:.02em; border:1px solid transparent; }
.ss-pill.good { color:#b7f7dc !important; background:rgba(52,211,153,.12); border-color:rgba(52,211,153,.30); }
.ss-pill.warn { color:#fde3a3 !important; background:rgba(251,191,36,.11); border-color:rgba(251,191,36,.30); }
.ss-pill.bad { color:#fecdd3 !important; background:rgba(251,113,133,.11); border-color:rgba(251,113,133,.30); }
.ss-pill.info { color:#cfe0ff !important; background:rgba(91,145,255,.12); border-color:rgba(91,145,255,.30); }
.ss-scoregrid { display:grid; grid-template-columns:repeat(4,minmax(90px,1fr)); gap:.45rem; align-content:center; }
.ss-score { padding:.54rem .60rem; border:1px solid var(--as-border); border-radius:10px; background:rgba(17,29,49,.72); }
.ss-score-label { color:var(--as-muted) !important; font-size:.62rem; text-transform:uppercase; letter-spacing:.055em; }
.ss-score-value { color:var(--as-text) !important; font-size:1.02rem; font-weight:760; margin-top:.06rem; }
.ss-reason { grid-column:1/-1; color:#c3cfdf !important; font-size:.70rem; line-height:1.35; padding:.34rem .08rem 0; }
.ss-entry-grid { display:grid; grid-template-columns:1.25fr 1fr 1fr 1fr 1fr; gap:.46rem; margin:.35rem 0 .50rem; }
.ss-entry-card { padding:.58rem .65rem; border:1px solid var(--as-border); border-radius:10px; background:var(--as-surface); min-width:0; }
.ss-entry-card.primary { border-color:rgba(91,145,255,.42); background:linear-gradient(135deg, rgba(91,145,255,.13), rgba(13,23,40,.95)); }
.ss-entry-label { color:var(--as-muted) !important; font-size:.61rem; text-transform:uppercase; letter-spacing:.05em; }
.ss-entry-value { color:var(--as-text) !important; font-size:1.06rem; font-weight:780; margin-top:.08rem; white-space:nowrap; }
.ss-entry-sub { color:var(--as-dim) !important; font-size:.61rem; margin-top:.05rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ss-panel-grid { display:grid; grid-template-columns:1fr 1fr; gap:.62rem; margin:.25rem 0 .5rem; }
.ss-panel { border:1px solid var(--as-border); border-radius:12px; background:rgba(13,23,40,.76); padding:.68rem .72rem; min-width:0; }
.ss-panel-head { display:flex; align-items:flex-start; justify-content:space-between; gap:.8rem; padding-bottom:.48rem; border-bottom:1px solid var(--as-border); }
.ss-panel-title { color:var(--as-text) !important; font-size:.79rem; font-weight:780; }
.ss-panel-main { color:var(--as-text) !important; font-size:1.07rem; font-weight:780; margin-top:.10rem; }
.ss-panel-score { color:#cfe0ff !important; font-size:.85rem; font-weight:800; white-space:nowrap; }
.ss-kv { display:grid; grid-template-columns:1fr auto; gap:.34rem .6rem; padding-top:.48rem; }
.ss-k { color:var(--as-muted) !important; font-size:.68rem; }
.ss-v { color:#e8eef8 !important; font-size:.69rem; font-weight:650; text-align:right; }
.ss-note { color:var(--as-dim) !important; font-size:.63rem; margin-top:.48rem; line-height:1.35; }
.ss-action { padding:.48rem .65rem; border-radius:9px; border:1px solid var(--as-border); background:var(--as-surface); color:#dce6f3 !important; font-size:.74rem; line-height:1.35; margin:.18rem 0 .4rem; }
.ss-action strong { color:var(--as-text) !important; font-size:.76rem; }
.ss-action .ss-muted { color:var(--as-muted) !important; }
.ss-good { border-left:3px solid var(--as-green); }
.ss-warn { border-left:3px solid var(--as-amber); }
.ss-bad { border-left:3px solid var(--as-red); }
div[data-testid="stMetric"] { background:var(--as-surface) !important; border:1px solid var(--as-border) !important; border-radius:9px; padding:.42rem .55rem !important; min-height:63px; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color:var(--as-muted) !important; font-size:.65rem !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color:var(--as-text) !important; font-size:.98rem !important; line-height:1.15 !important; }
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * { font-size:.62rem !important; }
.stTabs [data-baseweb="tab-list"] { gap:.12rem; background:rgba(13,23,40,.78) !important; padding:.20rem; border-radius:10px; border:1px solid var(--as-border); }
.stTabs [data-baseweb="tab"] { height:2.05rem; padding:0 .72rem; border-radius:7px; font-size:.73rem; color:var(--as-muted) !important; }
.stTabs [data-baseweb="tab"] p { color:inherit !important; }
.stTabs [aria-selected="true"] { background:rgba(91,145,255,.15) !important; color:var(--as-text) !important; }
.stButton > button { min-height:2.15rem; padding:.31rem .72rem; font-size:.76rem; border-radius:8px; }
.stButton > button[kind="primary"] { background:#4f7fe9 !important; border-color:#4f7fe9 !important; color:white !important; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, textarea { min-height:2.12rem; font-size:.77rem; background:var(--as-surface2) !important; color:var(--as-text) !important; border-color:var(--as-border) !important; }
[data-baseweb="select"] > div { min-height:2.12rem; font-size:.76rem; background:var(--as-surface2) !important; color:var(--as-text) !important; border-color:var(--as-border) !important; }
[data-baseweb="select"] * { color:var(--as-text) !important; }
[data-testid="stFileUploader"] section { padding:.5rem; background:var(--as-surface) !important; border-color:var(--as-border) !important; }

/* Streamlit Cloud widget contrast hardening */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] *,
[data-testid="stRadio"] > label, [data-testid="stRadio"] > label *,
[data-testid="stCheckbox"] > label, [data-testid="stCheckbox"] > label *,
[data-testid="stSlider"] > label, [data-testid="stSlider"] > label *,
[data-testid="stSelectSlider"] > label, [data-testid="stSelectSlider"] > label *,
[data-testid="stTextInput"] > label, [data-testid="stTextInput"] > label *,
[data-testid="stTextArea"] > label, [data-testid="stTextArea"] > label *,
[data-testid="stSelectbox"] > label, [data-testid="stSelectbox"] > label *,
[data-testid="stMultiSelect"] > label, [data-testid="stMultiSelect"] > label *,
[data-testid="stFileUploader"] > label, [data-testid="stFileUploader"] > label * {
  color:#aebbd0 !important;
  opacity:1 !important;
}
label[data-baseweb="radio"], label[data-baseweb="radio"] *,
label[data-baseweb="checkbox"], label[data-baseweb="checkbox"] * {
  color:#dce6f3 !important;
  opacity:1 !important;
}
[data-baseweb="radio"] p, [data-baseweb="checkbox"] p,
[data-testid="stRadio"] p, [data-testid="stCheckbox"] p {
  color:#dce6f3 !important;
  opacity:1 !important;
}
[data-testid="stSlider"] [data-testid="stThumbValue"],
[data-testid="stSelectSlider"] [data-testid="stThumbValue"] {
  color:#f4f7fb !important;
}

/* Expander headers: prevent Streamlit Cloud light-theme white strips */
[data-testid="stExpander"] {
  border:1px solid var(--as-border) !important;
  border-radius:10px !important;
  background:rgba(13,23,40,.55) !important;
  overflow:hidden !important;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details > summary {
  background:var(--as-surface2) !important;
  color:var(--as-text) !important;
}
[data-testid="stExpander"] summary {
  min-height:2.45rem !important;
  padding:.52rem .72rem !important;
  border-bottom:1px solid transparent !important;
}
[data-testid="stExpander"] details[open] > summary {
  border-bottom-color:var(--as-border) !important;
}
[data-testid="stExpander"] summary:hover {
  background:var(--as-surface3) !important;
}
[data-testid="stExpander"] summary *,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary svg {
  color:var(--as-text) !important;
  fill:currentColor !important;
  opacity:1 !important;
  font-size:.76rem !important;
  font-weight:700 !important;
}

/* Tabs: inactive labels must remain readable on Cloud */
.stTabs [data-baseweb="tab"], .stTabs [data-baseweb="tab"] * {
  color:#aebbd0 !important;
  opacity:1 !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"],
.stTabs [data-baseweb="tab"][aria-selected="true"] * {
  color:#f4f7fb !important;
}

[data-testid="stAlert"] { padding:.48rem .65rem; font-size:.76rem; background:var(--as-surface) !important; color:var(--as-text) !important; }
[data-testid="stDataFrame"] { border:1px solid var(--as-border); border-radius:9px; overflow:hidden; }
[data-testid="stDataFrame"] * { font-size:.71rem !important; }
hr { margin:.42rem 0 !important; border-color:var(--as-border) !important; }
div[data-testid="stVerticalBlock"] { gap:.44rem; }
[data-testid="column"] > div[data-testid="stVerticalBlock"] { gap:.30rem; }
@media (max-width: 900px) {
  .block-container, [data-testid="stMainBlockContainer"] { padding-left:.70rem !important; padding-right:.70rem !important; }
  .ss-header { align-items:flex-start; }
  .ss-sub { display:none; }
  .ss-hero { grid-template-columns:1fr; }
  .ss-scoregrid { grid-template-columns:repeat(2,1fr); }
  .ss-entry-grid { grid-template-columns:repeat(2,1fr); }
  .ss-entry-card.primary { grid-column:1/-1; }
  .ss-panel-grid { grid-template-columns:1fr; }
}
</style>
""",
    unsafe_allow_html=True,
)


def section(title: str):
    st.markdown(f'<div class="ss-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def action_banner(action: str, reason: str):
    a = str(action).upper()
    css = "ss-good" if "BUY" in a or "PRIORITY" in a else "ss-bad" if "AVOID" in a else "ss-warn"
    st.markdown(
        f'<div class="ss-action {css}"><strong>{html.escape(str(action))}</strong> '
        f'<span class="ss-muted">— {html.escape(str(reason))}</span></div>',
        unsafe_allow_html=True,
    )


def fmt_price(v):
    if v is None or pd.isna(v):
        return "N/A"
    return f"{float(v):,.0f}"


def table_height(n: int, cap: int = 500):
    return min(cap, max(150, 35 * (int(n) + 1)))


def _tone(status: str) -> str:
    s = str(status or "").upper()
    if any(x in s for x in ["BUY NOW", "BUY", "SUPER", "SUPPORTIVE", "BULLISH", "UPTREND"]):
        return "good"
    if any(x in s for x in ["AVOID", "INVALID", "BEARISH", "UNFAVORABLE"]):
        return "bad"
    if any(x in s for x in ["WAIT", "HEADWIND", "EXTENDED", "NO TREND"]):
        return "warn"
    return "info"


def _safe(v) -> str:
    return html.escape(str(v if v is not None else "N/A"))


def _score_box(label, value):
    return f'<div class="ss-score"><div class="ss-score-label">{_safe(label)}</div><div class="ss-score-value">{_safe(value)}</div></div>'


def _entry_box(label, value, sub="", primary=False):
    cls = "ss-entry-card primary" if primary else "ss-entry-card"
    return f'<div class="{cls}"><div class="ss-entry-label">{_safe(label)}</div><div class="ss-entry-value">{_safe(value)}</div><div class="ss-entry-sub">{_safe(sub)}</div></div>'


st.markdown(
    f"""
<div class="ss-header">
  <div>
    <div class="ss-brand">ANTOLUI SCREENER</div>
    <div class="ss-sub">IDX Technical & Entry Intelligence</div>
  </div>
  <div class="ss-badge">V{APP_VERSION}</div>
</div>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_stock(symbol: str):
    return load_stock(symbol)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_benchmark(symbol: str):
    return load_benchmark(symbol)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_universe_download(tickers_tuple, period: str, chunk_size: int):
    return download_universe(list(tickers_tuple), period=period, chunk_size=chunk_size)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_idx_sector_directory():
    # Official IDX company directory. The loader itself falls back to the last
    # successful local cache if IDX is temporarily unavailable.
    return fetch_idx_sector_directory(cache_path="idx_sector_cache.csv")


@st.cache_data(ttl=21600, show_spinner=False)
def cached_sector_index_history(sector_index: str):
    return load_official_sector_index_history(sector_index, period="2y")


@st.cache_data(ttl=900, show_spinner=False)
def cached_news_bundle(symbol: str):
    return fetch_news_bundle(symbol)


def run_single_analysis(ticker, benchmark_symbol):
    ticker_full, stock_raw = cached_stock(ticker)
    benchmark_full, bench_raw = cached_benchmark(benchmark_symbol)

    stock = add_indicators(stock_raw).dropna()
    benchmark = add_indicators(bench_raw).dropna()

    directory, sector_dir_source = cached_idx_sector_directory()
    sector_info = resolve_sector_info(ticker_full, directory, source_label=sector_dir_source)

    sector = None
    sector_history_symbol = None
    if sector_info.sector_index:
        sector_history_symbol, sector_raw = cached_sector_index_history(sector_info.sector_index)
        if sector_raw is not None:
            try:
                sector = add_indicators(sector_raw).dropna()
            except Exception:
                sector = None

    technical = run_engine(stock)
    plan = build_trade_plan(stock, technical["phase"]["label"])
    pattern = detect_patterns(stock)
    context = build_market_context(
        stock, benchmark, sector_df=sector,
        benchmark_name=benchmark_full,
        sector_name=(f"{sector_info.sector} ({sector_info.sector_index})" if sector is not None else sector_info.sector),
    )
    decision = combine_decision(technical, context)
    entry_plan = build_entry_plan(stock, technical, context, pattern, plan)
    timing_plan = build_timing_plan(stock, technical, context, pattern, plan, entry_plan)

    return {
        "ticker": ticker_full,
        "stock": stock,
        "technical": technical,
        "plan": plan,
        "pattern": pattern,
        "context": context,
        "decision": decision,
        "entry_plan": entry_plan,
        "timing_plan": timing_plan,
        "sector_info": sector_info.to_dict(),
        "sector_history_symbol": sector_history_symbol,
        "sector_directory_source": sector_dir_source,
    }


def render_single_stock():
    c1, c2 = st.columns([4.6, 1.0])
    ticker = c1.text_input("Ticker", value="VKTR", key="single_ticker", placeholder="Contoh: BBCA, ERAA, ANTM")
    c2.markdown("<div style='height:1.52rem'></div>", unsafe_allow_html=True)
    run_clicked = c2.button("Analyze", type="primary", use_container_width=True, key="run_single")
    with st.expander("Analysis settings", expanded=False):
        benchmark_symbol = st.text_input("Benchmark", value="^JKSE", key="single_bench", help="Default benchmark IDX Composite / IHSG.")

    if run_clicked:
        try:
            with st.spinner(f"Analyzing {ticker.upper()}..."):
                st.session_state["single_result"] = run_single_analysis(ticker, benchmark_symbol)
            if st.session_state.get("single_news_ticker") != st.session_state["single_result"]["ticker"]:
                st.session_state.pop("single_news_bundle", None)
        except Exception as e:
            st.exception(e)

    data = st.session_state.get("single_result")
    if not data:
        st.info("Masukkan ticker lalu klik **Analyze**. Antolui akan merangkum keputusan, entry, pattern, context, chart, dan level penting.")
        return

    ticker_full = data["ticker"]
    stock = data["stock"]
    technical = data["technical"]
    plan = data["plan"]
    pattern = data["pattern"]
    context = data["context"]
    decision = data["decision"]
    sector_info = data.get("sector_info") or {}
    entry_plan = data.get("entry_plan") or build_entry_plan(stock, technical, context, pattern, plan)
    timing_plan = data.get("timing_plan") or build_timing_plan(stock, technical, context, pattern, plan, entry_plan)

    active = timing_plan.get("active") or {}
    best = entry_plan.get("best") or {}
    active_entry = active.get("entry") if active else best.get("entry")
    entry_low = active.get("entry_low") if active else best.get("entry_low")
    entry_high = active.get("entry_high") if active else best.get("entry_high")
    active_stop = active.get("stop") if active else (best.get("stop") if best else plan.get("stop_loss"))
    active_rr = float((active.get("rr_tp2") if active else best.get("rr_tp2")) or 0)
    market_rs = float(context.get("relative_strength", {}).get("score", 0) or 0)

    sector_name = sector_info.get("sector", "Unknown")
    sector_index = sector_info.get("sector_index") or "N/A"
    status = timing_plan.get("status", decision.get("final_action", "WAIT"))
    status_tone = _tone(status)

    hero_scores = "".join([
        _score_box("Score", f'{decision["composite_score"]:.0f}/100'),
        _score_box("Timing", f'{timing_plan.get("score",0):.0f}/100'),
        _score_box("Market RS", f'{market_rs:.0f}/100'),
        _score_box("RR", f'{active_rr:.2f}x'),
    ])
    hero_reason = timing_plan.get("reason") or decision.get("reason", "")
    structure_label = technical.get("structure", {}).get("label", "N/A")
    st.markdown(
        f'''<div class="ss-hero">
          <div class="ss-identity">
            <div class="ss-ticker-line"><span class="ss-ticker">{_safe(ticker_full)}</span><span class="ss-price">{_safe(fmt_price(technical["price"]))}</span></div>
            <div class="ss-meta">{_safe(sector_name)} • {_safe(sector_index)} • {_safe(structure_label)} structure</div>
            <div class="ss-status-row">
              <span class="ss-pill {status_tone}">{_safe(status)}</span>
              <span class="ss-pill info">{_safe(pattern.get("label","No pattern"))}</span>
            </div>
          </div>
          <div class="ss-scoregrid">{hero_scores}<div class="ss-reason">{_safe(hero_reason)}</div></div>
        </div>''',
        unsafe_allow_html=True,
    )

    section("Entry Plan")
    zone_text = "N/A" if entry_low is None or entry_high is None else f"{fmt_price(entry_low)}–{fmt_price(entry_high)}"
    ideal_entry = fmt_price(best.get("entry")) if best else "N/A"
    entry_html = "".join([
        _entry_box("Buy Zone", zone_text, status, primary=True),
        _entry_box("Ideal Entry", ideal_entry, best.get("type", "Confluence") if best else "No valid entry"),
        _entry_box("Stop", fmt_price(active_stop), "Invalidation"),
        _entry_box("TP1", fmt_price(plan.get("tp1")), f'RR {float(plan.get("rr_tp1",0) or 0):.2f}x'),
        _entry_box("TP2", fmt_price(plan.get("tp2")), f'RR {float(plan.get("rr_tp2",0) or 0):.2f}x'),
    ])
    st.markdown(f'<div class="ss-entry-grid">{entry_html}</div>', unsafe_allow_html=True)
    st.caption(
        f'Confidence **{timing_plan.get("confidence","LOW")}** • Confirmation **{float(active.get("confirmation_score",0) or 0):.0f}/100** • '
        f'Trigger **{fmt_price(plan.get("breakout_trigger"))}**'
    )

    overview_tab, chart_tab, levels_tab, news_tab = st.tabs(["Overview", "Chart", "Levels & Entry", "News"])

    with overview_tab:
        tt = pattern.get("trend_template", {})
        trend_label = "UPTREND" if tt.get("passed") else "NO TREND"
        leader_label = "YES" if pattern.get("leader_52w", {}).get("passed") else "NO"
        detected = " • ".join(pattern.get("matches") or []) or "No additional setup"

        srs = context.get("sector_relative_strength")
        sector_rs_label = "N/A" if not srs else f'{srs.get("score",0):.0f}/100 • {srs.get("label","N/A")}'
        ex20 = context.get("relative_strength", {}).get("metrics", {}).get("excess_return_20d")
        ex20_text = "N/A" if ex20 is None else f"{ex20*100:+.1f}%"
        sector_regime = context.get("sector")
        sector_regime_text = "N/A" if not sector_regime else f'{sector_regime.get("label","N/A")} ({sector_regime.get("score",0):.0f}/100)'

        pattern_panel = f'''<div class="ss-panel">
          <div class="ss-panel-head">
            <div><div class="ss-panel-title">Pattern</div><div class="ss-panel-main">{_safe(pattern.get("label","N/A"))}</div></div>
            <div class="ss-panel-score">{float(pattern.get("score",0) or 0):.0f}/100</div>
          </div>
          <div class="ss-kv">
            <div class="ss-k">Status</div><div class="ss-v">{_safe(pattern.get("status","N/A"))}</div>
            <div class="ss-k">Pivot</div><div class="ss-v">{_safe(fmt_price(pattern.get("pivot")))}</div>
            <div class="ss-k">Trend</div><div class="ss-v">{_safe(trend_label)} • {float(tt.get("score",0) or 0):.0f}/100</div>
            <div class="ss-k">52W Leader</div><div class="ss-v">{_safe(leader_label)}</div>
          </div>
          <div class="ss-note">Detected: {_safe(detected)}</div>
        </div>'''

        market_panel = f'''<div class="ss-panel">
          <div class="ss-panel-head">
            <div><div class="ss-panel-title">Market Context</div><div class="ss-panel-main">{_safe(context.get("label","N/A"))}</div></div>
            <div class="ss-panel-score">{float(context.get("score",0) or 0):.0f}/100</div>
          </div>
          <div class="ss-kv">
            <div class="ss-k">IHSG Trend</div><div class="ss-v">{_safe(context.get("benchmark",{}).get("label","N/A"))} • {float(context.get("benchmark",{}).get("score",0) or 0):.0f}/100</div>
            <div class="ss-k">Market RS</div><div class="ss-v">{market_rs:.0f}/100 • {_safe(context.get("relative_strength",{}).get("label","N/A"))}</div>
            <div class="ss-k">Sector RS</div><div class="ss-v">{_safe(sector_rs_label)}</div>
            <div class="ss-k">20D vs IHSG</div><div class="ss-v">{_safe(ex20_text)}</div>
            <div class="ss-k">Sector</div><div class="ss-v">{_safe(sector_name)}</div>
            <div class="ss-k">Sector Regime</div><div class="ss-v">{_safe(sector_regime_text)}</div>
          </div>
        </div>'''
        st.markdown(f'<div class="ss-panel-grid">{pattern_panel}{market_panel}</div>', unsafe_allow_html=True)

        if pattern.get("super_setup"):
            action_banner("SUPER SETUP", "Multiple independent setup-quality signals are aligned near a tradable pivot.")

        section("At a Glance")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Structure", technical["structure"]["label"])
        g2.metric("Phase", technical["phase"]["label"])
        g3.metric("Momentum", technical["momentum"]["label"])
        g4.metric("Decision", decision["final_action"])

        with st.expander("Diagnostics", expanded=False):
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Technical", f'{decision["technical_quality"]:.0f}/100')
            d2.metric("Context", f'{context["score"]:.0f}/100')
            d3.metric("Pattern", f'{pattern["score"]:.0f}/100')
            d4.metric("Composite", f'{decision["composite_score"]:.0f}/100')
            with st.expander("Pattern engine details"):
                st.json(pattern)
            with st.expander("Market context details"):
                st.json(context)
            with st.expander("Technical engine details"):
                st.json(technical)

    with chart_tab:
        section("Price Chart")
        recent = stock.tail(180)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=recent.index, open=recent["Open"], high=recent["High"], low=recent["Low"], close=recent["Close"], name="Price"))
        fig.add_trace(go.Scatter(x=recent.index, y=recent["MA20"], name="MA20"))
        fig.add_trace(go.Scatter(x=recent.index, y=recent["MA50"], name="MA50"))
        fig.add_trace(go.Scatter(x=recent.index, y=recent["MA200"], name="MA200"))
        fig.add_trace(go.Scatter(x=recent.index, y=recent["EMA20"], name="EMA20", line=dict(dash="dot")))
        fig.add_trace(go.Scatter(x=recent.index, y=recent["EMA50"], name="EMA50", line=dict(dash="dot")))
        if pattern.get("pivot") is not None:
            fig.add_hline(y=pattern["pivot"], line_dash="dashdot", annotation_text=f'Pivot {pattern["pivot"]:,.0f}')
        rows = plan["level_engine"]["all_levels"]
        x0, x1 = recent.index[0], recent.index[-1]
        for lvl in rows:
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=lvl["zone_low"], y1=lvl["zone_high"], opacity=.07, line_width=0)
        dem = entry_plan.get("nearest_demand")
        sup = entry_plan.get("nearest_supply")
        if dem:
            fig.add_hrect(y0=dem["zone_low_exec"], y1=dem["zone_high_exec"], opacity=.10, line_width=0, annotation_text="Demand")
        if sup:
            fig.add_hrect(y0=sup["zone_low_exec"], y1=sup["zone_high_exec"], opacity=.08, line_width=0, annotation_text="Supply")
        if active and entry_low is not None and entry_high is not None:
            fig.add_hrect(y0=entry_low, y1=entry_high, opacity=.12, line_width=0, annotation_text="Buy Zone")
            if active_entry is not None:
                fig.add_hline(y=active_entry, line_dash="dashdot", annotation_text="Buy Entry")
        elif best:
            if best.get("entry_low") is not None and best.get("entry_high") is not None:
                fig.add_hrect(y0=best.get("entry_low"), y1=best.get("entry_high"), opacity=.10, line_width=0, annotation_text="Ideal Entry")
        fig.add_hline(y=plan["breakout_trigger"], line_dash="dash", annotation_text="Trigger")
        if active_stop is not None:
            fig.add_hline(y=active_stop, line_dash="dot", annotation_text="Stop")
        fig.update_layout(height=560, margin=dict(l=8, r=8, t=22, b=8), xaxis_rangeslider_visible=False, paper_bgcolor="#07101f", plot_bgcolor="#0b1526", font=dict(color="#d9e4f3", size=10), legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=10)))
        fig.update_xaxes(gridcolor="rgba(148,163,184,.10)")
        fig.update_yaxes(gridcolor="rgba(148,163,184,.10)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Demand / supply, buy zone, pivot, trigger, dan stop ditampilkan langsung di chart.")

    with levels_tab:
        section("Confluence Entry")
        if best:
            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Ideal Entry", fmt_price(best.get("entry")))
            e2.metric("Entry Zone", f'{fmt_price(best.get("entry_low"))}–{fmt_price(best.get("entry_high"))}')
            e3.metric("Entry Type", best.get("type", "N/A"))
            e4.metric("Entry Score", f'{float(best.get("score",0) or 0):.0f}/100')
            dem = entry_plan.get("nearest_demand")
            sup = entry_plan.get("nearest_supply")
            dtext = "N/A" if not dem else f'{fmt_price(dem["zone_low_exec"])}–{fmt_price(dem["zone_high_exec"])} • score {dem["score"]:.0f}'
            stext = "N/A" if not sup else f'{fmt_price(sup["zone_low_exec"])}–{fmt_price(sup["zone_high_exec"])} • score {sup["score"]:.0f}'
            st.caption(f'Demand **{dtext}** • Supply **{stext}** • Confidence **{entry_plan.get("confidence","LOW")}**')
            with st.expander("Alternative entry candidates"):
                cand = pd.DataFrame(entry_plan.get("candidates", []))
                if not cand.empty:
                    cols = [c for c in ["type","entry","entry_low","entry_high","stop","score","rr_tp2","reason"] if c in cand.columns]
                    st.dataframe(cand[cols], hide_index=True, use_container_width=True, height=table_height(len(cand), 260))
        else:
            st.info("Belum ada entry confluence yang valid.")

        section("Trade Plan")
        t1, t2, t3, t4, t5 = st.columns(5)
        t1.metric("Trigger", fmt_price(plan.get("breakout_trigger")))
        t2.metric("Support", fmt_price(plan.get("support1")))
        t3.metric("Stop", fmt_price(plan.get("stop_loss")))
        t4.metric("TP1", fmt_price(plan.get("tp1")), f'RR {float(plan.get("rr_tp1",0) or 0):.2f}x')
        t5.metric("TP2", fmt_price(plan.get("tp2")), f'RR {float(plan.get("rr_tp2",0) or 0):.2f}x')
        st.caption(f'IDX tick current/trigger **Rp{plan["idx_tick_size"]:,} / Rp{plan.get("trigger_tick_size", plan["idx_tick_size"]):,}** • Resistance **{fmt_price(plan.get("resistance1"))} / {fmt_price(plan.get("resistance2"))}**')

        section("Intelligent Price Levels")
        rows = plan["level_engine"]["all_levels"]
        if rows:
            level_df = pd.DataFrame(rows)
            cols = [c for c in ["role","center","zone_low","zone_high","score","touches","last_touch_bars_ago","confluence"] if c in level_df.columns]
            st.dataframe(level_df[cols], hide_index=True, use_container_width=True, height=table_height(len(level_df), 360), column_config={"role": st.column_config.TextColumn("Role", width="small"), "center": st.column_config.NumberColumn("Level", format="%.0f", width="small"), "zone_low": st.column_config.NumberColumn("Zone Low", format="%.0f", width="small"), "zone_high": st.column_config.NumberColumn("Zone High", format="%.0f", width="small"), "score": st.column_config.NumberColumn("Score", format="%.0f", width="small"), "touches": st.column_config.NumberColumn("Touches", format="%d", width="small")})
        else:
            st.warning("Pivot clusters belum cukup; strategy memakai fallback MA/ATR.")

    with news_tab:
        section("News & Narrative")
        st.caption("Rumor dipisahkan dari berita terverifikasi dan tidak otomatis menaikkan ranking.")
        nc1, nc2 = st.columns([.75, 3.25])
        fetch_news = nc1.button("Fetch / Refresh", type="primary", use_container_width=True, key="single_fetch_news")
        nc2.caption("Berita diambil on-demand supaya analisis technical tetap cepat.")
        if fetch_news:
            with st.spinner("Fetching recent public headlines..."):
                st.session_state["single_news_bundle"] = cached_news_bundle(ticker_full)
                st.session_state["single_news_ticker"] = ticker_full
        news_bundle = st.session_state.get("single_news_bundle") if st.session_state.get("single_news_ticker") == ticker_full else None
        if news_bundle:
            n1, n2, n3, n4, n5 = st.columns(5)
            n1.metric("Catalyst", f'{news_bundle["catalyst_score"]:.0f}/100')
            n2.metric("Confirmed", f'{news_bundle["confirmed_catalyst_score"]:.0f}/100')
            n3.metric("Bias", news_bundle["bias"])
            n4.metric("Heat", news_bundle["heat"])
            n5.metric("Rumor Risk", news_bundle["rumor_risk"])
            action_banner(news_bundle["bias"], news_bundle["top_narrative"])
            if news_bundle.get("items"):
                news_df = pd.DataFrame(news_bundle["items"])
                show_cols = [c for c in ["published_at", "source", "item_type", "category", "bias", "reliability_score", "title", "url"] if c in news_df.columns]
                st.dataframe(news_df[show_cols], hide_index=True, use_container_width=True, height=table_height(len(news_df), 460), column_config={"published_at": st.column_config.TextColumn("Date", width="small"), "source": st.column_config.TextColumn("Source", width="small"), "item_type": st.column_config.TextColumn("Type", width="small"), "category": st.column_config.TextColumn("Category", width="small"), "reliability_score": st.column_config.NumberColumn("Rel.", format="%.0f", width="small"), "title": st.column_config.TextColumn("Headline", width="large"), "url": st.column_config.LinkColumn("Link", display_text="Open", width="small")})
            if news_bundle.get("errors"):
                with st.expander("Source warnings"):
                    st.write(" | ".join(news_bundle["errors"]))
        else:
            st.info("Klik **Fetch / Refresh** untuk mengambil berita dan narrative terbaru ticker ini.")


def render_scanner():
    section("IDX Scanner")
    st.caption("Cari setup terbaik berdasarkan technical, pattern, sector/market context, entry timing, dan risk/reward.")

    with st.expander("1. Universe & Data", expanded=True):
        c1, c2, c3 = st.columns([1.7, 1, 1])
        with c1:
            source = st.radio(
                "Universe",
                ["Quality 200 (Tiered)", "Liquid IDX seed", "Paste ticker list", "Upload IDX CSV"],
                horizontal=True,
                help="Quality 200 memiliki Tier A/B/C. Custom ticker di luar daftar menjadi Tier U."
            )
            if source == "Quality 200 (Tiered)":
                tickers = load_quality_200()
                counts = tier_counts()
                st.caption(f'{len(tickers)} ticker • A {counts.get("A",0)} • B {counts.get("B",0)} • C {counts.get("C",0)}')
            elif source == "Liquid IDX seed":
                tickers = load_seed_universe()
                st.caption(f"{len(tickers)} ticker quick-test universe")
            elif source == "Paste ticker list":
                text = st.text_area("Ticker list", value="BBCA BBRI BMRI TLKM ANTM ADRO MDKA PGAS PTBA", height=80)
                tickers = parse_ticker_text(text)
                st.caption(f"{len(tickers)} ticker detected")
            else:
                uploaded = st.file_uploader("Upload IDX CSV", type=["csv"], help="Ticker / Symbol / Code / Kode / Kode Saham")
                if uploaded is not None:
                    try:
                        tickers = parse_uploaded_csv(uploaded.getvalue())
                        st.caption(f"{len(tickers)} ticker detected")
                    except Exception as e:
                        st.error(str(e)); tickers = []
                else:
                    tickers = []
        benchmark_symbol = c2.text_input("Benchmark", value="^JKSE", key="scanner_benchmark")
        chunk_size = c3.select_slider("Batch size", options=[20, 40, 60, 80, 100], value=60)

    with st.expander("2. Risk & Quality Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        min_liq_b = f1.slider("Min liquidity (RpB/day)", 1, 100, 5, 1)
        min_rr2 = f2.slider("Min RR to TP2", 0.5, 3.0, 1.5, 0.1)
        strict_tier = f3.checkbox("Strict Tier rules", value=True, help="Tighter rules for Tier B/C/U candidates.")
        include_bearish = f4.checkbox("Include bearish / AVOID", value=False, help="Diagnostics only; usually keep OFF.")

    scan_c1, scan_c2 = st.columns([.8, 3.2])
    scan_clicked = scan_c1.button("SCAN UNIVERSE", type="primary", disabled=(len(tickers) == 0), use_container_width=True)
    scan_c2.caption("Recommended baseline: Quality 200 • Min liquidity Rp5B • RR ≥1.5 • Strict Tier ON")

    if scan_clicked:
        try:
            bench_full, bench_raw = cached_benchmark(benchmark_symbol)
            benchmark = add_indicators(bench_raw).dropna()
            bench_health = trend_health(benchmark, bench_full)

            status = st.empty(); progress = st.progress(0.0)
            status.caption(f"Downloading {len(tickers)} symbols...")
            frames, download_errors = cached_universe_download(tuple(tickers), "2y", int(chunk_size))

            status.caption("Loading IDX-IC sectors and building sector proxies...")
            sector_directory, sector_source = cached_idx_sector_directory()
            scan_sector_map = sector_map_for_tickers(tickers, sector_directory, source_label=sector_source)
            raw_sector_proxies = build_equal_weight_sector_proxies(frames, scan_sector_map, min_constituents=3)
            sector_proxies = {}
            for sector_code, proxy_raw in raw_sector_proxies.items():
                try:
                    proxy_ind = add_indicators(proxy_raw).dropna()
                    if len(proxy_ind) >= 65:
                        sector_proxies[sector_code] = proxy_ind
                except Exception:
                    continue

            def on_progress(i, total, ticker):
                progress.progress(i / max(total, 1))
                status.caption(f"Analyzing {i}/{total}: {ticker}")

            result, skipped = scan_frames(
                frames, benchmark,
                min_avg_value=float(min_liq_b) * 1e9,
                min_rr2=float(min_rr2),
                include_bearish=include_bearish,
                progress_callback=on_progress,
                sector_map=scan_sector_map,
                sector_proxies=sector_proxies,
            )

            if download_errors:
                err_df = pd.DataFrame([{"Ticker": k.replace(".JK", ""), "Reason": v} for k, v in download_errors.items()])
                skipped = pd.concat([skipped, err_df], ignore_index=True)

            progress.progress(1.0); status.caption("Scan complete")
            st.session_state["scan_result"] = result
            st.session_state["scan_skipped"] = skipped
            st.session_state["scan_meta"] = {
                "universe": len(tickers), "downloaded": len(frames), "passed": len(result),
                "benchmark": bench_full, "benchmark_label": bench_health["label"],
                "benchmark_score": bench_health["score"], "strict_tier": strict_tier,
                "sector_source": sector_source,
                "sector_mapped": sum(1 for v in scan_sector_map.values() if v.get("sector_code")),
                "sector_proxies": len(sector_proxies),
            }
        except Exception as e:
            st.exception(e)

    result = st.session_state.get("scan_result")
    skipped = st.session_state.get("scan_skipped")
    meta = st.session_state.get("scan_meta")

    if not isinstance(result, pd.DataFrame):
        return

    if meta:
        section("Scan Summary")
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("Universe", meta["universe"])
        s2.metric("Downloaded", meta["downloaded"])
        s3.metric("Candidates", meta["passed"])
        s4.metric("IHSG", meta["benchmark_label"])
        s5.metric("IHSG Score", f'{meta["benchmark_score"]:.0f}/100')
        s6.metric("Sector Map", f'{meta.get("sector_mapped",0)}/{meta["universe"]}', f'{meta.get("sector_proxies",0)} proxies')
        st.caption(f'Sector classification source: **{meta.get("sector_source","Unknown")}** • Scanner sector regime/RS uses an equal-weight proxy from downloaded stocks in each IDX-IC sector, not the official IDX sector-index weighting.')

    if result.empty:
        st.warning("Tidak ada saham yang lolos. Longgarkan liquidity/RR atau cek data source.")
        return

    with st.expander("3. News Enrichment (optional)", expanded=False):
        n1, n2, n3 = st.columns([1, 1.2, 1])
        news_top_n = n1.select_slider("Fetch news for Top N", options=[5, 10, 15, 20, 30], value=15)
        apply_news_overlay = n2.checkbox(
            "Apply confirmed-news overlay", value=False,
            help="Max ±5 points, verified/reported news only. Rumor never boosts score."
        )
        n3.markdown("<div style='height:1.52rem'></div>", unsafe_allow_html=True)
        enrich_clicked = n3.button("ENRICH NEWS", type="secondary", use_container_width=True)
        if enrich_clicked:
            news_status = st.empty(); news_progress = st.progress(0.0)
            def on_news_progress(i, total, ticker):
                news_progress.progress(i / max(total, 1)); news_status.caption(f"News {i}/{total}: {ticker}")
            enriched, details = enrich_rows_with_news(
                result, top_n=int(news_top_n), progress_callback=on_news_progress,
                apply_confirmed_overlay=bool(apply_news_overlay),
            )
            news_progress.progress(1.0); news_status.caption("News enrichment complete")
            st.session_state["scan_result"] = enriched
            st.session_state["scan_news_details"] = details
            st.session_state["scan_news_overlay"] = bool(apply_news_overlay)
            result = enriched

    section("Top Setups")
    preset = st.selectbox(
        "Screener Preset",
        [
            "All Setups", "SUPER SETUP", "VCP / Early VCP", "Flat Base", "Cup & Handle",
            "Darvas Box", "Bull Flag", "High Tight Flag", "Volatility Squeeze / NR7",
            "EMA20/50 Golden Cross", "Pre-Golden Cross", "Ascending Triangle",
            "Pattern Breakout", "Uptrend", "52W Leader", "Priority Setup",
            "BUY NOW", "WAIT RETEST", "WAIT BREAKOUT", "TOO EXTENDED",
            "Hot Narrative", "Bullish Catalyst", "Bearish Catalyst", "Rumor Watch"
        ],
        help="Pattern preset uses all detected matches, not only the primary pattern."
    )

    with st.expander("Result filters", expanded=False):
        f1, f2, f3, f4 = st.columns(4)
        sectors = f1.multiselect("Sector", sorted(result["Sector"].dropna().unique()), default=sorted(result["Sector"].dropna().unique())) if "Sector" in result.columns else []
        tiers = f2.multiselect("Tier", sorted(result["Tier"].dropna().unique()), default=sorted(result["Tier"].dropna().unique()))
        grades = f3.multiselect("Grade", sorted(result["Grade"].dropna().unique()), default=sorted(result["Grade"].dropna().unique()))
        phases = f4.multiselect("Phase", sorted(result["Phase"].dropna().unique()), default=sorted(result["Phase"].dropna().unique()))
        f5, f6, f7 = st.columns(3)
        patterns = f5.multiselect("Pattern", sorted(result["Pattern"].dropna().unique()), default=sorted(result["Pattern"].dropna().unique()))
        actions = f6.multiselect("Technical Action", sorted(result["Final Action"].dropna().unique()), default=sorted(result["Final Action"].dropna().unique()))
        executions = f7.multiselect("Execution", sorted(result["Execution"].dropna().unique()), default=sorted(result["Execution"].dropna().unique()))

    sector_mask = result["Sector"].isin(sectors) if "Sector" in result.columns else True
    view = result[
        sector_mask & result["Tier"].isin(tiers) & result["Grade"].isin(grades) & result["Phase"].isin(phases) &
        result["Pattern"].isin(patterns) & result["Final Action"].isin(actions) & result["Execution"].isin(executions)
    ].copy()

    if preset == "SUPER SETUP":
        view = view[view["Super Setup"].eq("YES")].copy()
    elif preset == "VCP / Early VCP":
        view = view[view["Pattern Matches"].str.contains("VCP", na=False)].copy()
    elif preset == "Flat Base":
        view = view[view["Pattern Matches"].str.contains("Flat Base", na=False)].copy()
    elif preset == "Cup & Handle":
        view = view[view["Pattern Matches"].str.contains("Cup & Handle", na=False, regex=False)].copy()
    elif preset == "Darvas Box":
        view = view[view["Pattern Matches"].str.contains("Darvas Box", na=False)].copy()
    elif preset == "Bull Flag":
        view = view[view["Pattern Matches"].str.contains("Bull Flag", na=False)].copy()
    elif preset == "High Tight Flag":
        view = view[view["Pattern Matches"].str.contains("High Tight Flag", na=False)].copy()
    elif preset == "Volatility Squeeze / NR7":
        view = view[view["Pattern Matches"].str.contains("Volatility Squeeze", na=False)].copy()
    elif preset == "EMA20/50 Golden Cross":
        view = view[view["EMA Signal"].eq("EMA20/50 Golden Cross")].copy()
    elif preset == "Pre-Golden Cross":
        view = view[view["EMA Signal"].eq("Pre-Golden Cross")].copy()
    elif preset == "Ascending Triangle":
        view = view[view["Pattern Matches"].str.contains("Ascending Triangle", na=False)].copy()
    elif preset == "Pattern Breakout":
        view = view[view["Pattern Matches"].str.contains(r"\(BREAKOUT\)", regex=True, na=False)].copy()
    elif preset == "Uptrend":
        view = view[view["Trend"].eq("UPTREND")].copy()
    elif preset == "52W Leader":
        view = view[view["52W Leader"].eq("YES")].copy()
    elif preset == "Priority Setup":
        view = view[view["Priority"].eq("YES")].copy()
    elif preset in {"BUY NOW", "WAIT RETEST", "WAIT BREAKOUT", "TOO EXTENDED"}:
        view = view[view["Execution"].eq(preset)].copy()
    elif preset == "Hot Narrative":
        view = view[view["Narrative Heat"].eq("Hot")].copy() if "Narrative Heat" in view.columns else view.iloc[0:0].copy()
    elif preset == "Bullish Catalyst":
        view = view[(view["Catalyst Bias"].eq("Bullish")) & (pd.to_numeric(view["Confirmed Catalyst"], errors="coerce").fillna(0) >= 35)].copy() if "Catalyst Bias" in view.columns else view.iloc[0:0].copy()
    elif preset == "Bearish Catalyst":
        view = view[(view["Catalyst Bias"].eq("Bearish")) & (pd.to_numeric(view["Confirmed Catalyst"], errors="coerce").fillna(0) >= 35)].copy() if "Catalyst Bias" in view.columns else view.iloc[0:0].copy()
    elif preset == "Rumor Watch":
        view = view[pd.to_numeric(view["Rumor Count"], errors="coerce").fillna(0) > 0].copy() if "Rumor Count" in view.columns else view.iloc[0:0].copy()

    if bool(strict_tier):
        view = view[view["Top Eligible"] == "YES"].copy()
        st.caption("Strict Tier ON • only tier-eligible candidates are shown.")

    if view.empty:
        st.warning("Tidak ada kandidat untuk preset/filter ini.")
    else:
        max_top = min(100, len(view))
        top_n = st.slider("Rows", 5, max(5, max_top), min(20, max(5, max_top)), 5) if max_top >= 5 else max_top

        compact_cols = [
            "Rank", "Ticker", "Sector", "Tier", "Scanner Score", "Pattern", "Execution", "Timing Score",
            "Buy Entry", "Buy Entry Type", "Combined RS Score", "Buy Entry RR", "Buy Stop", "TP2"
        ]
        for c in ["Narrative Heat", "Catalyst Bias", "Rumor Risk"]:
            if c in view.columns:
                compact_cols.append(c)
        compact_cols = [c for c in compact_cols if c in view.columns]
        compact = view.head(top_n)[compact_cols]

        st.dataframe(
            compact, hide_index=True, use_container_width=True,
            height=table_height(len(compact), 560),
            column_config={
                "Rank": st.column_config.NumberColumn("#", width="small", format="%d"),
                "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                "Sector": st.column_config.TextColumn("Sector", width="medium"),
                "Tier": st.column_config.TextColumn("Tier", width="small"),
                "Scanner Score": st.column_config.NumberColumn("Score", width="small", format="%.1f"),
                "Grade": st.column_config.TextColumn("Grade", width="small"),
                "Setup": st.column_config.TextColumn("Setup", width="medium"),
                "Pattern": st.column_config.TextColumn("Pattern", width="medium"),
                "Pattern Score": st.column_config.NumberColumn("P.Score", width="small", format="%.0f"),
                "Execution": st.column_config.TextColumn("Execution", width="medium"),
                "Timing Score": st.column_config.NumberColumn("Timing", width="small", format="%.0f"),
                "Buy Entry": st.column_config.NumberColumn("Entry", width="small", format="%.0f"),
                "Buy Entry RR": st.column_config.NumberColumn("RR", width="small", format="%.2f"),
                "Buy Entry Type": st.column_config.TextColumn("Entry Type", width="medium"),
                "Buy Stop": st.column_config.NumberColumn("SL", width="small", format="%.0f"),
                "Trend": st.column_config.TextColumn("Trend", width="small"),
                "52W Leader": st.column_config.TextColumn("52W", width="small"),
                "Final Action": st.column_config.TextColumn("Action", width="medium"),
                "Phase": st.column_config.TextColumn("Phase", width="medium"),
                "Momentum": st.column_config.TextColumn("Momentum", width="small"),
                "RS": st.column_config.TextColumn("RS", width="small"),
                "Entry": st.column_config.NumberColumn("Entry", width="small", format="%.0f"),
                "Entry Score": st.column_config.NumberColumn("E.Score", width="small", format="%.0f"),
                "Entry Type": st.column_config.TextColumn("Entry Type", width="medium"),
                "RS Score": st.column_config.NumberColumn("RS Mkt", width="small", format="%.0f"),
                "Combined RS Score": st.column_config.NumberColumn("RS", width="small", format="%.0f"),
                "Sector RS Score": st.column_config.NumberColumn("RS Sec", width="small", format="%.0f"),
                "RR TP2": st.column_config.NumberColumn("RR", width="small", format="%.2f"),
                "Trigger": st.column_config.NumberColumn("Trigger", width="small", format="%.0f"),
                "Stop": st.column_config.NumberColumn("Stop", width="small", format="%.0f"),
                "TP2": st.column_config.NumberColumn("TP2", width="small", format="%.0f"),
            }
        )

        with st.expander("Detailed result table"):
            display_cols = [
                "Rank", "Ticker", "Sector", "Sector Code", "Sector Index", "Sector Source", "Tier", "Top Eligible", "Super Setup", "Priority", "Scanner Score", "Grade", "Setup",
                "Pattern", "Pattern Score", "Pattern Status", "Pattern Pivot", "Pattern Dist %", "Trend", "Trend Score",
                "52W Leader", "52W Dist %", "NR7", "Volume Dry-Up",
                "Entry", "Entry Low", "Entry High", "Entry Score", "Entry Type", "Entry Status", "Entry Confidence",
                "Execution", "Timing Score", "Timing Confidence", "Buy Entry", "Buy Entry Low", "Buy Entry High", "Buy Entry Type", "Buy Stop",
                "Confirmation Score", "Entry Distance %", "Supply Headroom %",
                "Demand Low", "Demand High", "Demand Score", "Supply Low", "Supply High", "Supply Score",
                "Final Action", "Phase", "Momentum", "Tech Quality",
                "Context Score", "RS Score", "Sector RS Score", "Combined RS Score", "Sector Strength", "Sector Regime", "Avg Value 20D (RpB)", "Volume Ratio", "RR TP1", "RR TP2", "Trigger", "Trigger Dist %",
                "Support 1", "Stop", "TP1", "TP2"
            ]
            news_cols = ["News Score", "Catalyst Score", "Confirmed Catalyst", "Catalyst Bias", "Narrative Heat", "Rumor Risk", "Verified News", "Rumor Count", "Top Narrative"]
            display_cols = [c for c in display_cols + news_cols if c in view.columns]
            st.dataframe(view.head(top_n)[display_cols], hide_index=True, use_container_width=True, height=table_height(top_n, 590))

        st.download_button(
            "Download results CSV", data=result.to_csv(index=False).encode("utf-8"),
            file_name="antolui_screener_v5_9_scanner_results.csv", mime="text/csv"
        )

        section("Quick Drilldown")
        pick = st.selectbox("Ticker detail", view["Ticker"].tolist(), key="scanner_pick")
        row = view[view["Ticker"] == pick].iloc[0]
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        d1.metric("Tier / Grade", f'{row["Tier"]} / {row["Grade"]}')
        d2.metric("Scanner", f'{row["Scanner Score"]:.1f}')
        d3.metric("Execution", row.get("Execution", "N/A"))
        d4.metric("Timing", f'{float(row.get("Timing Score",0) or 0):.0f}/100')
        d5.metric("Buy Entry", fmt_price(row.get("Buy Entry")))
        d6.metric("RR", f'{float(row.get("Buy Entry RR",0) or 0):.2f}x')
        action_banner(row.get("Execution", row["Final Action"]), row.get("Timing Reason", row["Reason"]))

        dl, dr = st.columns([1, 1])
        with dl:
            st.caption(
                f'Sector: **{row.get("Sector","Unknown")}** • Phase: **{row["Phase"]}** • Momentum: **{row["Momentum"]}** • '
                f'Pattern: **{row["Pattern Score"]:.0f}** • RS: **{float(row.get("Combined RS Score", row.get("RS Score",0)) or 0):.0f}**'
            )
            st.caption(
                f'Active entry {fmt_price(row.get("Buy Entry Low"))}–{fmt_price(row.get("Buy Entry High"))} • Demand {fmt_price(row.get("Demand Low"))}–{fmt_price(row.get("Demand High"))} • Stop {fmt_price(row.get("Buy Stop"))} • TP2 {fmt_price(row.get("TP2"))}'
            )
        with dr:
            news_details = st.session_state.get("scan_news_details", {})
            bundle = news_details.get(str(pick)) if isinstance(news_details, dict) else None
            if bundle:
                st.caption(
                    f'Catalyst **{bundle["catalyst_score"]:.0f}** • Confirmed **{bundle["confirmed_catalyst_score"]:.0f}** • '
                    f'Bias **{bundle["bias"]}** • Heat **{bundle["heat"]}** • Rumor **{bundle["rumor_risk"]}**'
                )
                st.caption(bundle["top_narrative"])

            if row["Top Eligible"] != "YES":
                st.warning(f'Tier guardrail: {row["Tier Rule"]}')

            if bundle and bundle.get("items"):
                with st.expander("Latest news for selected ticker"):
                    ndf = pd.DataFrame(bundle["items"])
                    ncols = [c for c in ["published_at", "source", "item_type", "bias", "title", "url"] if c in ndf.columns]
                    st.dataframe(
                        ndf[ncols], hide_index=True, use_container_width=True,
                        column_config={"url": st.column_config.LinkColumn("Link", display_text="Open", width="small")}
                    )

    if isinstance(skipped, pd.DataFrame) and not skipped.empty:
        with st.expander(f"Skipped / failed ({len(skipped)})"):
            st.dataframe(skipped, hide_index=True, use_container_width=True, height=min(420, table_height(len(skipped))))


single_tab, scanner_tab = st.tabs(["Single Stock", "IDX Scanner"])
with single_tab:
    render_single_stock()
with scanner_tab:
    render_scanner()
