from scanner_scoring import liquidity_score, rr_score, proximity_score, rank_candidate


def tech(quality=82, phase="Pre-Breakout", momentum="Healthy", structure="Bullish", price=100):
    return {
        "trade_quality": quality,
        "price": price,
        "phase": {"label": phase},
        "momentum": {"label": momentum},
        "structure": {"label": structure},
    }


def ctx(score=82, label="Supportive", rs="Outperforming"):
    return {
        "score": score,
        "label": label,
        "relative_strength": {"label": rs, "score": 80},
    }


def plan(trigger=102, rr2=2.4):
    return {
        "breakout_trigger": trigger,
        "aggressive_entry_low": 96,
        "aggressive_entry_high": 99,
        "conservative_entry_high": 103,
        "rr_tp2": rr2,
    }


def decision(action="BUY CANDIDATE"):
    return {"final_action": action}


def run_tests():
    passed = []

    assert liquidity_score(100e9, 80e9, 1.0) >= 95
    assert liquidity_score(1e9, 0.8e9, 1.0) <= 5
    passed.append("liquidity scaling")

    assert rr_score(3.0) > rr_score(2.0) > rr_score(1.0)
    passed.append("RR scaling")

    near = proximity_score("Pre-Breakout", 100, plan(trigger=101))
    far = proximity_score("Pre-Breakout", 100, plan(trigger=112))
    assert near > far
    passed.append("entry proximity")

    liq = {"score": 90}
    strong = rank_candidate(tech(), ctx(), decision(), plan(), liq)
    weak = rank_candidate(tech(), ctx(score=25, label="Headwind", rs="Underperforming"), decision("WAIT"), plan(), liq)
    assert strong["scanner_score"] > weak["scanner_score"] + 10
    passed.append("market context changes ranking")

    over = rank_candidate(
        tech(quality=82, phase="Overextended", momentum="Healthy"),
        ctx(), decision("WAIT"), plan(), liq
    )
    assert over["scanner_score"] < strong["scanner_score"]
    passed.append("overextended penalty")

    bear = rank_candidate(
        tech(quality=75, phase="Trend Continuation", momentum="Bearish", structure="Bearish"),
        ctx(), decision("AVOID"), plan(), liq
    )
    assert bear["scanner_score"] < 50
    passed.append("bearish hard penalty")

    assert strong["grade"] in {"A+", "A", "B+"}
    assert strong["setup_status"] == "ACTIONABLE"
    passed.append("grade and status")

    neutral_pattern = {"label":"None", "score":50, "status":"NONE", "priority_candidate":False}
    strong_pattern = {"label":"VCP", "score":92, "status":"FORMING", "priority_candidate":True}
    base_pat = rank_candidate(tech(), ctx(), decision(), plan(), liq, ticker="BBCA", pattern=neutral_pattern)
    vcp_pat = rank_candidate(tech(), ctx(), decision(), plan(), liq, ticker="BBCA", pattern=strong_pattern)
    assert vcp_pat["scanner_score"] > base_pat["scanner_score"] + 5
    assert vcp_pat["pattern_score"] == 92
    passed.append("pattern quality changes ranking")

    print(f"PASS: {len(passed)}/{len(passed)}")
    for p in passed:
        print(" -", p)


if __name__ == "__main__":
    run_tests()
