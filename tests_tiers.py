from quality_universe import load_quality_table, get_tier_info
from scanner_scoring import rank_candidate


def tech(quality=82, phase="Pre-Breakout", momentum="Healthy", structure="Bullish", price=100):
    return {
        "trade_quality": quality,
        "price": price,
        "phase": {"label": phase},
        "momentum": {"label": momentum},
        "structure": {"label": structure},
    }


def ctx(score=82):
    return {
        "score": score,
        "label": "Supportive",
        "relative_strength": {"label": "Outperforming", "score": 80},
    }


def plan(rr2=2.4):
    return {
        "breakout_trigger": 102,
        "aggressive_entry_low": 96,
        "aggressive_entry_high": 99,
        "conservative_entry_high": 103,
        "rr_tp2": rr2,
    }


def decision():
    return {"final_action": "BUY CANDIDATE"}


def strong_pattern(score=92):
    return {
        "label": "VCP",
        "score": score,
        "status": "FORMING",
        "priority_candidate": True,
    }


def run_tests():
    passed = []
    df = load_quality_table()
    assert len(df) == 200
    assert df["Ticker"].nunique() == 200
    counts = df["Tier"].value_counts().to_dict()
    assert counts == {"A": 80, "B": 70, "C": 50}
    passed.append("200 unique tickers: A80/B70/C50")

    assert get_tier_info("BBCA")["tier"] == "A"
    assert get_tier_info("VKTR")["tier"] == "B"
    assert get_tier_info("BREN")["tier"] == "C"
    assert get_tier_info("ZZZZ")["tier"] == "U"
    passed.append("tier lookup")

    liq = {"score": 90, "avg_value_20": 20e9}
    a = rank_candidate(tech(), ctx(), decision(), plan(), liq, ticker="BBCA")
    b = rank_candidate(tech(), ctx(), decision(), plan(), liq, ticker="VKTR")
    c = rank_candidate(tech(), ctx(), decision(), plan(), liq, ticker="BREN")
    assert a["scanner_score"] > b["scanner_score"] > c["scanner_score"]
    assert a["tier_adjustment"] == 3.0
    assert b["tier_adjustment"] == 0.0
    assert c["tier_adjustment"] == -5.0
    passed.append("tier trust adjustment")

    assert c["top_eligible"] is False
    assert "score < 85" in c["tier_rule"]
    passed.append("Tier C strict score gate")

    strong_c = rank_candidate(
        tech(quality=96), ctx(score=96), decision(), plan(rr2=3.0),
        {"score": 100, "avg_value_20": 100e9}, ticker="BREN", pattern=strong_pattern()
    )
    assert strong_c["scanner_score"] >= 85
    assert strong_c["top_eligible"] is True
    passed.append("exceptional Tier C can qualify")

    weak_liq_c = rank_candidate(
        tech(quality=96), ctx(score=96), decision(), plan(rr2=3.0),
        {"score": 55, "avg_value_20": 7e9}, ticker="BREN", pattern=strong_pattern()
    )
    assert weak_liq_c["top_eligible"] is False
    assert "liquidity" in weak_liq_c["tier_rule"]
    passed.append("Tier C liquidity gate")

    low_rr_c = rank_candidate(
        tech(quality=96), ctx(score=96), decision(), plan(rr2=1.8),
        {"score": 100, "avg_value_20": 100e9}, ticker="BREN", pattern=strong_pattern()
    )
    assert low_rr_c["top_eligible"] is False
    assert "RR2" in low_rr_c["tier_rule"]
    passed.append("Tier C RR gate")

    print(f"PASS: {len(passed)}/{len(passed)}")
    for x in passed:
        print(" -", x)


if __name__ == "__main__":
    run_tests()
