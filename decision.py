from __future__ import annotations


def combine_decision(technical: dict, context: dict) -> dict:
    tech_score = float(technical["trade_quality"])
    context_score = float(context["score"])

    # Context matters, but should not erase the chart structure.
    composite = round(0.70 * tech_score + 0.30 * context_score, 1)

    base_action = technical["action"]
    phase = technical["phase"]["label"]
    momentum = technical["momentum"]["label"]

    final_action = base_action
    reasons = [technical["action_reason"]]

    if base_action == "AVOID":
        final_action = "AVOID"
    elif context["label"] == "Headwind":
        final_action = "WAIT"
        reasons.append("Market context menjadi headwind.")
    elif phase == "Confirmed Breakout" and context.get("market_headwind"):
        final_action = "WAIT"
        reasons.append("Breakout terjadi saat benchmark bearish; tunggu konfirmasi lanjutan.")
    elif base_action == "BUY CANDIDATE":
        if composite >= 72 and context_score >= 50:
            final_action = "BUY CANDIDATE"
        else:
            final_action = "WAIT"
            reasons.append("Composite score belum cukup kuat setelah market context.")
    elif base_action == "WAIT":
        # Context alone cannot turn a non-confirmed technical setup into a buy.
        final_action = "WAIT"

    if context["relative_strength"]["label"] == "Underperforming":
        reasons.append("Relative strength masih underperform benchmark.")
    elif context["relative_strength"]["label"] == "Outperforming":
        reasons.append("Relative strength outperform benchmark.")

    sector_rs = context.get("sector_relative_strength")
    if sector_rs and sector_rs.get("label") == "Underperforming":
        reasons.append("Saham masih underperform terhadap sektor IDX-IC-nya.")
    elif sector_rs and sector_rs.get("label") == "Outperforming":
        reasons.append("Saham outperform terhadap sektor IDX-IC-nya.")

    if context["volume_flow"]["label"] == "Accumulation":
        reasons.append("Volume flow mengindikasikan accumulation.")
    elif context["volume_flow"]["label"] == "Distribution":
        reasons.append("Volume flow mengindikasikan distribution.")

    return {
        "technical_quality": round(tech_score, 1),
        "context_score": round(context_score, 1),
        "composite_score": composite,
        "base_action": base_action,
        "final_action": final_action,
        "reason": " ".join(dict.fromkeys(reasons)),
    }
