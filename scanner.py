from __future__ import annotations

from typing import Dict, Any, Iterable, Callable, Optional
import math
import pandas as pd

from data import download_universe
from indicators import add_indicators
from engine import run_engine
from strategy import build_trade_plan
from entry_engine import build_entry_plan
from timing_engine import build_timing_plan
from market_context import build_market_context
from decision import combine_decision
from scanner_scoring import liquidity_score, rank_candidate
from patterns import detect_patterns


def liquidity_metrics(raw_df: pd.DataFrame) -> Dict[str, Any]:
    recent = raw_df.dropna().tail(20).copy()
    if recent.empty:
        return {
            "avg_value_20": 0.0, "median_value_20": 0.0,
            "active_ratio_20": 0.0, "score": 0.0,
        }
    value = recent["Close"].astype(float) * recent["Volume"].astype(float)
    avg = float(value.mean())
    med = float(value.median())
    active = float((recent["Volume"] > 0).mean())
    return {
        "avg_value_20": avg,
        "median_value_20": med,
        "active_ratio_20": active,
        "score": liquidity_score(avg, med, active),
    }


def _distance_to_trigger_pct(price: float, trigger: float) -> float:
    if price <= 0:
        return 0.0
    return (trigger / price - 1.0) * 100.0


def analyze_frame(
    ticker: str,
    raw_df: pd.DataFrame,
    benchmark_ind: pd.DataFrame,
    min_avg_value: float = 5e9,
    min_rr2: float = 1.5,
    include_bearish: bool = False,
    sector_map: Optional[Dict[str, dict]] = None,
    sector_proxies: Optional[Dict[str, pd.DataFrame]] = None,
) -> tuple[dict | None, str | None]:
    liq = liquidity_metrics(raw_df)
    if liq["avg_value_20"] < min_avg_value:
        return None, f"liquidity < Rp{min_avg_value/1e9:.1f}B/day"

    try:
        stock = add_indicators(raw_df).dropna()
        if len(stock) < 20:
            return None, "insufficient post-indicator history"

        technical = run_engine(stock)
        if not include_bearish and technical["structure"]["label"] == "Bearish":
            return None, "bearish structure"
        if technical["action"] == "AVOID" and not include_bearish:
            return None, "technical AVOID"

        plan = build_trade_plan(stock, technical["phase"]["label"])
        if float(plan.get("rr_tp2", 0) or 0) < min_rr2:
            return None, f"RR2 < {min_rr2:.1f}"

        ticker_code = str(ticker).upper().replace(".JK", "")
        sector_info = (sector_map or {}).get(ticker_code, {})
        sector_code = sector_info.get("sector_code")
        sector_df = (sector_proxies or {}).get(str(sector_code)) if sector_code else None
        sector_name = sector_info.get("sector", "Unknown")
        sector_context_name = f"{sector_name} EW Proxy" if sector_df is not None else sector_name

        context = build_market_context(
            stock, benchmark_ind, benchmark_name="^JKSE",
            sector_df=sector_df, sector_name=sector_context_name,
        )
        decision = combine_decision(technical, context)
        pattern = detect_patterns(stock)
        entry_plan = build_entry_plan(stock, technical, context, pattern, plan)
        timing_plan = build_timing_plan(stock, technical, context, pattern, plan, entry_plan)
        rank = rank_candidate(technical, context, decision, plan, liq, ticker=ticker, pattern=pattern)

        x = stock.iloc[-1]
        rs = context["relative_strength"]
        flow = context["volume_flow"]
        price = float(technical["price"])
        trigger = int(plan["breakout_trigger"])

        row = {
            "Ticker": ticker.replace(".JK", ""),
            "Sector": sector_info.get("sector", "Unknown"),
            "Sector Code": sector_info.get("sector_code"),
            "Sector Index": sector_info.get("sector_index"),
            "Sector Source": sector_info.get("source", "Unknown"),
            "Tier": rank["tier"],
            "Tier Profile": rank["tier_profile"],
            "Top Eligible": "YES" if rank["top_eligible"] else "NO",
            "Tier Rule": rank["tier_rule"],
            "Price": int(plan["price"]),
            "IDX Tick": int(plan["idx_tick_size"]),
            "Trigger Tick": int(plan.get("trigger_tick_size", plan["idx_tick_size"])),
            "Base Score": rank["base_scanner_score"],
            "Tier Adj": rank["tier_adjustment"],
            "Scanner Score": rank["scanner_score"],
            "Grade": rank["grade"],
            "Setup": rank["setup_status"],
            "Priority": "YES" if rank.get("priority_setup") else "NO",
            "Super Setup": "YES" if rank.get("super_setup") else "NO",
            "Pattern": pattern["label"],
            "Pattern Score": pattern["score"],
            "Pattern Status": pattern["status"],
            "Pattern Pivot": pattern.get("pivot"),
            "Pattern Dist %": pattern.get("distance_to_pivot_pct"),
            "Pattern Matches": " | ".join(pattern.get("matches", [])),
            "EMA Signal": pattern["ema"].get("signal", "None"),
            "EMA Cross Days": pattern["ema"].get("days_since_cross"),
            "Trend": "UPTREND" if pattern.get("trend_template", {}).get("passed") else "NO TREND",
            "Trend Score": pattern.get("trend_template", {}).get("score", 0),
            "52W Leader": "YES" if pattern.get("leader_52w", {}).get("passed") else "NO",
            "52W Dist %": pattern.get("leader_52w", {}).get("distance_high52_pct"),
            "NR7": "YES" if pattern.get("squeeze", {}).get("nr7") else "NO",
            "Base Depth %": pattern.get("flat_base", {}).get("base_depth_pct"),
            "VCP Contractions": "/".join(str(v) for v in pattern["vcp"].get("contractions", [])),
            "Volume Dry-Up": "YES" if pattern.get("volume_dry_up") else "NO",
            "ATR Contraction": "YES" if (pattern["vcp"].get("atr_contraction") or pattern["triangle"].get("atr_contraction") or pattern.get("flat_base",{}).get("atr_contraction") or pattern.get("squeeze",{}).get("atr_contraction")) else "NO",
            "Entry Type": entry_plan["best"]["type"] if entry_plan.get("best") else "NONE",
            "Entry": entry_plan["best"]["entry"] if entry_plan.get("best") else None,
            "Entry Low": entry_plan["best"]["entry_low"] if entry_plan.get("best") else None,
            "Entry High": entry_plan["best"]["entry_high"] if entry_plan.get("best") else None,
            "Entry Score": entry_plan["best"]["score"] if entry_plan.get("best") else 0,
            "Entry Status": entry_plan.get("status", "NO ENTRY"),
            "Entry Confidence": entry_plan.get("confidence", "LOW"),
            "Execution": timing_plan.get("status", "NO ENTRY"),
            "Timing Score": timing_plan.get("score", 0),
            "Timing Confidence": timing_plan.get("confidence", "LOW"),
            "Timing Reason": timing_plan.get("reason", ""),
            "Buy Entry": timing_plan.get("active", {}).get("entry") if timing_plan.get("active") else None,
            "Buy Entry Low": timing_plan.get("active", {}).get("entry_low") if timing_plan.get("active") else None,
            "Buy Entry High": timing_plan.get("active", {}).get("entry_high") if timing_plan.get("active") else None,
            "Buy Entry Type": timing_plan.get("active", {}).get("type") if timing_plan.get("active") else None,
            "Buy Entry RR": timing_plan.get("active", {}).get("rr_tp2") if timing_plan.get("active") else None,
            "Buy Stop": timing_plan.get("active", {}).get("stop") if timing_plan.get("active") else None,
            "Confirmation Score": timing_plan.get("active", {}).get("confirmation_score") if timing_plan.get("active") else None,
            "Entry Distance %": timing_plan.get("active", {}).get("zone_distance_pct") if timing_plan.get("active") else None,
            "Supply Headroom %": timing_plan.get("active", {}).get("supply_headroom_pct") if timing_plan.get("active") else None,
            "Demand Low": entry_plan.get("nearest_demand",{}).get("zone_low_exec") if entry_plan.get("nearest_demand") else None,
            "Demand High": entry_plan.get("nearest_demand",{}).get("zone_high_exec") if entry_plan.get("nearest_demand") else None,
            "Demand Score": entry_plan.get("nearest_demand",{}).get("score") if entry_plan.get("nearest_demand") else None,
            "Supply Low": entry_plan.get("nearest_supply",{}).get("zone_low_exec") if entry_plan.get("nearest_supply") else None,
            "Supply High": entry_plan.get("nearest_supply",{}).get("zone_high_exec") if entry_plan.get("nearest_supply") else None,
            "Supply Score": entry_plan.get("nearest_supply",{}).get("score") if entry_plan.get("nearest_supply") else None,
            "Final Action": decision["final_action"],
            "Structure": technical["structure"]["label"],
            "Phase": technical["phase"]["label"],
            "Momentum": technical["momentum"]["label"],
            "Tech Quality": decision["technical_quality"],
            "Context Score": context["score"],
            "Context": context["label"],
            "RS Score": rs["score"],
            "RS": rs["label"],
            "Combined RS Score": context.get("combined_relative_strength", {}).get("score", rs["score"]),
            "Sector RS Score": None if not context.get("sector_relative_strength") else context["sector_relative_strength"].get("score"),
            "Sector RS": None if not context.get("sector_relative_strength") else context["sector_relative_strength"].get("label"),
            "Sector Strength": None if not context.get("sector") else context["sector"].get("score"),
            "Sector Regime": None if not context.get("sector") else context["sector"].get("label"),
            "20D vs IHSG %": None if rs["metrics"].get("excess_return_20d") is None else round(rs["metrics"]["excess_return_20d"] * 100, 2),
            "Liquidity Score": rank["liquidity_score"],
            "Avg Value 20D (RpB)": round(liq["avg_value_20"] / 1e9, 2),
            "Volume Ratio": round(float(x.get("Volume_ratio", 0)), 2),
            "Volume Flow": flow["label"],
            "RR TP1": float(plan["rr_tp1"]),
            "RR TP2": float(plan["rr_tp2"]),
            "Proximity": rank["proximity_score"],
            "Trigger": trigger,
            "Trigger Dist %": round(_distance_to_trigger_pct(price, trigger), 2),
            "Agg Entry Low": plan["aggressive_entry_low"],
            "Agg Entry High": plan["aggressive_entry_high"],
            "Support 1": plan["support1"],
            "Support 2": plan["support2"],
            "Stop": plan["stop_loss"],
            "TP1": plan["tp1"],
            "TP2": plan["tp2"],
            "Reason": decision["reason"],
        }
        return row, None
    except Exception as e:
        return None, f"analysis error: {e}"


def scan_frames(
    frames: Dict[str, pd.DataFrame],
    benchmark_ind: pd.DataFrame,
    min_avg_value: float = 5e9,
    min_rr2: float = 1.5,
    include_bearish: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    sector_map: Optional[Dict[str, dict]] = None,
    sector_proxies: Optional[Dict[str, pd.DataFrame]] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, skipped = [], []
    items = list(frames.items())
    total = len(items)
    for i, (ticker, raw_df) in enumerate(items, start=1):
        if progress_callback:
            progress_callback(i, total, ticker)
        row, reason = analyze_frame(
            ticker, raw_df, benchmark_ind,
            min_avg_value=min_avg_value,
            min_rr2=min_rr2,
            include_bearish=include_bearish,
            sector_map=sector_map,
            sector_proxies=sector_proxies,
        )
        if row is not None:
            rows.append(row)
        else:
            skipped.append({"Ticker": ticker.replace(".JK", ""), "Reason": reason or "filtered"})

    result = pd.DataFrame(rows)
    if not result.empty:
        result["_eligible_sort"] = result["Top Eligible"].eq("YES").astype(int)
        result["_super_sort"] = result["Super Setup"].eq("YES").astype(int)
        result["_priority_sort"] = result["Priority"].eq("YES").astype(int)
        result["_buy_now_sort"] = result["Execution"].eq("BUY NOW").astype(int)
        result = result.sort_values(
            ["_eligible_sort", "_buy_now_sort", "Timing Score", "_super_sort", "_priority_sort", "Scanner Score", "Pattern Score"],
            ascending=[False, False, False, False, False, False, False],
        ).drop(columns=["_eligible_sort", "_buy_now_sort", "_super_sort", "_priority_sort"]).reset_index(drop=True)
        result.insert(0, "Rank", range(1, len(result) + 1))

    return result, pd.DataFrame(skipped)


def scan_universe(
    tickers: Iterable[str],
    benchmark_ind: pd.DataFrame,
    period: str = "2y",
    chunk_size: int = 60,
    min_avg_value: float = 5e9,
    min_rr2: float = 1.5,
    include_bearish: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    sector_map: Optional[Dict[str, dict]] = None,
    sector_proxies: Optional[Dict[str, pd.DataFrame]] = None,
):
    frames, download_errors = download_universe(tickers, period=period, chunk_size=chunk_size)
    result, skipped = scan_frames(
        frames,
        benchmark_ind,
        min_avg_value=min_avg_value,
        min_rr2=min_rr2,
        include_bearish=include_bearish,
        progress_callback=progress_callback,
        sector_map=sector_map,
        sector_proxies=sector_proxies,
    )
    err_rows = [{"Ticker": k.replace(".JK", ""), "Reason": v} for k, v in download_errors.items()]
    if err_rows:
        skipped = pd.concat([skipped, pd.DataFrame(err_rows)], ignore_index=True)
    return result, skipped
