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
  --ss-bg: #09111F;
  --ss-panel: #111B2D;
  --ss-panel2: #0D1727;
  --ss-border: rgba(148,163,184,.16);
  --ss-text: #E9EFF8;
  --ss-muted: #8FA2BA;
  --ss-blue: #4F8CFF;
  --ss-green: #31C48D;
  --ss-red: #F05252;
  --ss-amber: #F6B94A;
}
html, body, [class*="css"] {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.block-container {
  padding-top: .72rem !important;
  padding-bottom: 2rem !important;
  padding-left: 1.35rem !important;
  padding-right: 1.35rem !important;
  max-width: 1780px;
}
header[data-testid="stHeader"] { height: 2.2rem; background: transparent; }
[data-testid="stToolbar"] { top: .25rem; }

h1 { font-size: 1.62rem !important; letter-spacing: -.025em; margin: .1rem 0 .2rem !important; }
h2 { font-size: 1.12rem !important; letter-spacing: -.01em; margin: .7rem 0 .35rem !important; }
h3 { font-size: .96rem !important; margin: .55rem 0 .25rem !important; }
p, li, label, .stMarkdown { font-size: .84rem; line-height: 1.4; }
small, .stCaption { color: var(--ss-muted) !important; }

.ss-header {
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
  padding:.62rem .8rem; border:1px solid var(--ss-border); border-radius:14px;
  background:linear-gradient(115deg, rgba(79,140,255,.12), rgba(17,27,45,.84) 40%, rgba(17,27,45,.96));
  margin-bottom:.55rem;
}
.ss-brand { font-size:1.08rem; font-weight:800; letter-spacing:.08em; }
.ss-sub { color:var(--ss-muted); font-size:.74rem; margin-top:.08rem; }
.ss-badge {
  display:inline-flex; align-items:center; padding:.22rem .48rem; border-radius:999px;
  border:1px solid rgba(79,140,255,.35); color:#AFCBFF; background:rgba(79,140,255,.10);
  font-size:.68rem; font-weight:700; white-space:nowrap;
}
.ss-section {
  display:flex; align-items:center; gap:.42rem; margin:.62rem 0 .34rem;
  color:#DCE7F6; font-size:.83rem; font-weight:750; letter-spacing:.02em;
}
.ss-section::before { content:""; width:3px; height:15px; border-radius:3px; background:var(--ss-blue); }
.ss-action {
  padding:.55rem .72rem; border-radius:10px; border:1px solid var(--ss-border);
  background:var(--ss-panel2); font-size:.79rem; line-height:1.35; margin:.2rem 0 .45rem;
}
.ss-action strong { font-size:.82rem; }
.ss-good { border-left:3px solid var(--ss-green); }
.ss-warn { border-left:3px solid var(--ss-amber); }
.ss-bad  { border-left:3px solid var(--ss-red); }
.ss-muted { color:var(--ss-muted); }

/* compact metrics */
div[data-testid="stMetric"] {
  background:rgba(17,27,45,.76);
  border:1px solid var(--ss-border);
  border-radius:10px;
  padding:.45rem .6rem !important;
  min-height:67px;
}
[data-testid="stMetricLabel"] { font-size:.67rem !important; color:var(--ss-muted) !important; }
[data-testid="stMetricValue"] { font-size:1.03rem !important; line-height:1.15 !important; }
[data-testid="stMetricDelta"] { font-size:.65rem !important; }

/* compact tabs */
.stTabs [data-baseweb="tab-list"] {
  gap:.18rem; background:rgba(17,27,45,.62); padding:.2rem; border-radius:10px;
  border:1px solid var(--ss-border);
}
.stTabs [data-baseweb="tab"] {
  height:2.05rem; padding:0 .68rem; border-radius:8px; font-size:.75rem;
}
.stTabs [aria-selected="true"] { background:rgba(79,140,255,.14); }

/* compact controls */
.stButton > button { min-height:2.18rem; padding:.32rem .72rem; font-size:.78rem; border-radius:8px; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input { min-height:2.12rem; font-size:.78rem; }
[data-baseweb="select"] > div { min-height:2.12rem; font-size:.77rem; }
[data-testid="stFileUploader"] section { padding:.55rem; }
[data-testid="stExpander"] { border:1px solid var(--ss-border); border-radius:10px; background:rgba(17,27,45,.35); }
[data-testid="stExpander"] summary { font-size:.78rem; font-weight:650; }

/* dataframe/readability */
[data-testid="stDataFrame"] { border:1px solid var(--ss-border); border-radius:9px; overflow:hidden; }
[data-testid="stDataFrame"] * { font-size:.72rem !important; }
[data-testid="stAlert"] { padding:.5rem .7rem; font-size:.78rem; }
hr { margin:.45rem 0 !important; border-color:var(--ss-border) !important; }

/* reduce vertical gaps */
div[data-testid="stVerticalBlock"] { gap:.48rem; }
[data-testid="column"] > div[data-testid="stVerticalBlock"] { gap:.34rem; }
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


st.markdown(
    f"""
<div class="ss-header">
  <div>
    <div class="ss-brand">ANTOLUI SCREENER</div>
    <div class="ss-sub">IDX technical intelligence • auto IDX-IC sector • patterns • execution • narrative</div>
  </div>
  <div class="ss-badge">V{APP_VERSION} • AUTO SECTOR</div>
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
    # Compact input strip instead of a large sidebar.
    with st.container():
        c1, c2, c3 = st.columns([1.35, 1.15, .72])
        ticker = c1.text_input("Ticker", value="VKTR", key="single_ticker")
        benchmark_symbol = c2.text_input("Benchmark", value="^JKSE", key="single_bench")
        c3.markdown("<div style='height:1.52rem'></div>", unsafe_allow_html=True)
        run_clicked = c3.button("Analyze", type="primary", use_container_width=True, key="run_single")

    if run_clicked:
        try:
            with st.spinner(f"Analyzing {ticker.upper()}..."):
                st.session_state["single_result"] = run_single_analysis(ticker, benchmark_symbol)
            # Clear previous ticker news when a new analysis is run.
            if st.session_state.get("single_news_ticker") != st.session_state["single_result"]["ticker"]:
                st.session_state.pop("single_news_bundle", None)
        except Exception as e:
            st.exception(e)

    data = st.session_state.get("single_result")
    if not data:
        st.info("Masukkan ticker lalu klik **Analyze**. Hasil akan ditata dalam Overview, Chart & Levels, News, dan Diagnostics.")
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

    section(f"{ticker_full} — Decision Snapshot")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Price", fmt_price(technical["price"]))
    m2.metric("Action", decision["final_action"])
    m3.metric("Composite", f'{decision["composite_score"]:.0f}/100')
    m4.metric("Structure", technical["structure"]["label"])
    m5.metric("Phase", technical["phase"]["label"])
    m6.metric("Momentum", technical["momentum"]["label"])
    sector_name_display = sector_info.get("sector", "Unknown")
    sector_index_display = sector_info.get("sector_index") or "N/A"
    sector_src_display = sector_info.get("source", data.get("sector_directory_source", "Unknown"))
    st.caption(f'IDX-IC Sector: **{sector_name_display}** • Index: **{sector_index_display}** • Source: **{sector_src_display}**')
    action_banner(decision["final_action"], decision["reason"])

    section("Execution Timing")
    active_timing = timing_plan.get("active") or {}
    t1, t2, t3, t4, t5, t6 = st.columns(6)
    t1.metric("Execution", timing_plan.get("status", "NO ENTRY"))
    t2.metric("Timing", f'{timing_plan.get("score",0):.0f}/100')
    t3.metric("Buy Entry", fmt_price(active_timing.get("entry")))
    t4.metric("Entry Zone", f'{fmt_price(active_timing.get("entry_low"))}–{fmt_price(active_timing.get("entry_high"))}')
    t5.metric("Stop", fmt_price(active_timing.get("stop")))
    t6.metric("RR", f'{float(active_timing.get("rr_tp2",0) or 0):.2f}x')
    action_banner(timing_plan.get("status", "NO ENTRY"), timing_plan.get("reason", ""))
    st.caption(f'Execution confidence: **{timing_plan.get("confidence","LOW")}** • Confirmation score: **{float(active_timing.get("confirmation_score",0) or 0):.0f}/100**')

    overview_tab, chart_tab, news_tab, diag_tab = st.tabs(
        ["Overview", "Chart & Levels", "News & Narrative", "Advanced"]
    )

    with overview_tab:
        left, right = st.columns([1, 1])
        with left:
            section("Pattern & Setup")
            p1, p2, p3 = st.columns(3)
            p1.metric("Primary Pattern", pattern["label"])
            p2.metric("Pattern Score", f'{pattern["score"]:.0f}/100')
            p3.metric("Status", pattern["status"])
            p4, p5, p6 = st.columns(3)
            p4.metric("Pattern Pivot", fmt_price(pattern.get("pivot")))
            tt = pattern.get("trend_template", {})
            p5.metric("Trend", "UPTREND" if tt.get("passed") else "NO TREND", f'{tt.get("score",0):.0f}/100')
            p6.metric("52W Leader", "YES" if pattern.get("leader_52w", {}).get("passed") else "NO")
            if pattern.get("super_setup"):
                action_banner("SUPER SETUP", "Multiple independent setup-quality signals are aligned near a tradable pivot.")
            if pattern.get("matches"):
                st.caption("Detected: " + " • ".join(pattern["matches"]))

        with right:
            section("Market Context")
            q1, q2, q3 = st.columns(3)
            q1.metric("Context", context["label"], f'{context["score"]:.0f}/100')
            q2.metric("RS vs IHSG", context["relative_strength"]["label"], f'{context["relative_strength"]["score"]:.0f}/100')
            srs = context.get("sector_relative_strength")
            q3.metric("RS vs Sector", "N/A" if not srs else srs["label"], None if not srs else f'{srs["score"]:.0f}/100')
            q4, q5, q6 = st.columns(3)
            q4.metric("IHSG", context["benchmark"]["label"], f'{context["benchmark"]["score"]:.0f}/100')
            if context["sector"]:
                q5.metric("Sector Regime", context["sector"]["label"], f'{context["sector"]["score"]:.0f}/100')
            else:
                q5.metric("IDX-IC Sector", sector_info.get("sector", "Unknown"))
            ex20 = context["relative_strength"]["metrics"].get("excess_return_20d")
            q6.metric("20D vs IHSG", "N/A" if ex20 is None else f"{ex20*100:+.1f}%")
            if sector_info.get("sector_index") and not context.get("sector"):
                st.caption(f'Sector detected automatically from {sector_info.get("source","IDX")}. Historical {sector_info.get("sector_index")} series was not available from the current Yahoo data source, so sector RS is not forced.')

        section("Confluence Entry — Indicators + Pattern + Supply/Demand")
        best = entry_plan.get("best")
        if best:
            e1, e2, e3, e4, e5, e6 = st.columns(6)
            e1.metric("Ideal Entry", fmt_price(best["entry"]))
            e2.metric("Entry Zone", f'{fmt_price(best["entry_low"])}–{fmt_price(best["entry_high"])}')
            e3.metric("Entry Type", best["type"])
            e4.metric("Entry Score", f'{best["score"]:.0f}/100')
            e5.metric("Status", entry_plan.get("status",""))
            e6.metric("RR to TP2", f'{best["rr_tp2"]:.2f}x')
            dem = entry_plan.get("nearest_demand")
            sup = entry_plan.get("nearest_supply")
            dtext = "N/A" if not dem else f'{fmt_price(dem["zone_low_exec"])}–{fmt_price(dem["zone_high_exec"])} ({dem["score"]:.0f})'
            stext = "N/A" if not sup else f'{fmt_price(sup["zone_low_exec"])}–{fmt_price(sup["zone_high_exec"])} ({sup["score"]:.0f})'
            st.caption(f'Demand {dtext}  •  Supply {stext}  •  Confidence {entry_plan.get("confidence","LOW")}  •  {best["reason"]}')
            with st.expander("Alternative entry candidates"):
                cand = pd.DataFrame(entry_plan.get("candidates", []))
                if not cand.empty:
                    cols = [c for c in ["type","entry","entry_low","entry_high","stop","score","rr_tp2","reason"] if c in cand.columns]
                    st.dataframe(cand[cols], hide_index=True, use_container_width=True, height=table_height(len(cand), 260))
        else:
            st.info("Belum ada entry confluence yang valid.")

        section("Trade Plan — Executable IDX Prices")
        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Trigger", fmt_price(plan["breakout_trigger"]))
        t2.metric("Support 1", fmt_price(plan["support1"]))
        t3.metric("Stop", fmt_price(plan["stop_loss"]))
        t4.metric("TP1", fmt_price(plan["tp1"]), f'RR {plan["rr_tp1"]:.2f}x')
        t5.metric("TP2", fmt_price(plan["tp2"]), f'RR {plan["rr_tp2"]:.2f}x')
        t6.metric("Tick Cur/Trig", f'Rp{plan["idx_tick_size"]:,} / Rp{plan.get("trigger_tick_size", plan["idx_tick_size"]):,}')
        st.caption(
            f'Aggressive entry {fmt_price(plan["aggressive_entry_low"])}–{fmt_price(plan["aggressive_entry_high"])}  •  '
            f'Conservative entry {fmt_price(plan["conservative_entry_low"])}–{fmt_price(plan["conservative_entry_high"])}  •  '
            f'Resistance {fmt_price(plan["resistance1"])} / {fmt_price(plan["resistance2"])}'
        )

    with chart_tab:
        section("Price Chart")
        recent = stock.tail(180)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=recent.index, open=recent["Open"], high=recent["High"],
            low=recent["Low"], close=recent["Close"], name="Price"
        ))
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
        if timing_plan.get("active"):
            b = timing_plan["active"]
            fig.add_hrect(y0=b["entry_low"], y1=b["entry_high"], opacity=.12, line_width=0, annotation_text="Active Entry")
            fig.add_hline(y=b["entry"], line_dash="dashdot", annotation_text="Buy Entry")
        elif entry_plan.get("best"):
            b = entry_plan["best"]
            fig.add_hrect(y0=b["entry_low"], y1=b["entry_high"], opacity=.10, line_width=0, annotation_text="Ideal Entry")
        fig.add_hline(y=plan["breakout_trigger"], line_dash="dash", annotation_text="Trigger")
        stop_line = timing_plan.get("active", {}).get("stop") if timing_plan.get("active") else plan["stop_loss"]
        fig.add_hline(y=stop_line, line_dash="dot", annotation_text="Stop")
        fig.update_layout(
            height=535,
            margin=dict(l=8, r=8, t=22, b=8),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)

        section("Intelligent Price Levels")
        if rows:
            level_df = pd.DataFrame(rows)
            cols = ["role", "center", "zone_low", "zone_high", "score", "touches", "last_touch_bars_ago", "confluence"]
            cols = [c for c in cols if c in level_df.columns]
            st.dataframe(
                level_df[cols], hide_index=True, use_container_width=True,
                height=table_height(len(level_df), 360),
                column_config={
                    "role": st.column_config.TextColumn("Role", width="small"),
                    "center": st.column_config.NumberColumn("Level", format="%.0f", width="small"),
                    "zone_low": st.column_config.NumberColumn("Zone Low", format="%.0f", width="small"),
                    "zone_high": st.column_config.NumberColumn("Zone High", format="%.0f", width="small"),
                    "score": st.column_config.NumberColumn("Score", format="%.0f", width="small"),
                    "touches": st.column_config.NumberColumn("Touches", format="%d", width="small"),
                },
            )
        else:
            st.warning("Pivot clusters belum cukup; strategy memakai fallback MA/ATR.")

    with news_tab:
        section("News & Narrative Monitor")
        st.caption("Rumor dipisahkan dari berita terverifikasi dan tidak otomatis menaikkan ranking.")
        nc1, nc2 = st.columns([.75, 3.25])
        fetch_news = nc1.button("Fetch / Refresh", type="primary", use_container_width=True, key="single_fetch_news")
        nc2.caption("Fetch hanya saat dibutuhkan agar halaman Single Stock tetap cepat dan ringkas.")
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
                st.dataframe(
                    news_df[show_cols], hide_index=True, use_container_width=True,
                    height=table_height(len(news_df), 460),
                    column_config={
                        "published_at": st.column_config.TextColumn("Date", width="small"),
                        "source": st.column_config.TextColumn("Source", width="small"),
                        "item_type": st.column_config.TextColumn("Type", width="small"),
                        "category": st.column_config.TextColumn("Category", width="small"),
                        "reliability_score": st.column_config.NumberColumn("Rel.", format="%.0f", width="small"),
                        "title": st.column_config.TextColumn("Headline", width="large"),
                        "url": st.column_config.LinkColumn("Link", display_text="Open", width="small"),
                    },
                )
            if news_bundle.get("errors"):
                with st.expander("Source warnings"):
                    st.write(" | ".join(news_bundle["errors"]))
        else:
            st.info("Klik **Fetch / Refresh** untuk mengambil berita dan narrative terbaru ticker ini.")

    with diag_tab:
        section("Advanced Diagnostics")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Technical Quality", f'{decision["technical_quality"]:.0f}/100')
        d2.metric("Context Score", f'{context["score"]:.0f}/100')
        d3.metric("Pattern Score", f'{pattern["score"]:.0f}/100')
        d4.metric("Composite", f'{decision["composite_score"]:.0f}/100')
        with st.expander("Pattern engine details", expanded=False):
            st.json(pattern)
        with st.expander("Market context details"):
            st.json(context)
        with st.expander("Technical engine details"):
            st.json(technical)


def render_scanner():
    section("IDX Scanner")
    st.caption("Scan technical + pattern + market context first; enrich news only for top candidates.")

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
