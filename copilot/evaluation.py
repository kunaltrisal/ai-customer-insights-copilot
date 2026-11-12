"""Accuracy check: compare the AI's categories with your own hand labels.

Agreement  = share of reviews where the AI picked the same category as you.
Cohen's kappa = agreement after removing the agreement you would get by
                luck. 0 means no better than chance, 1 means perfect.
                Above 0.6 is usually called "substantial" agreement.
Precision for a category = of the reviews the AI put there, share you agree with.
Recall for a category    = of the reviews you put there, share the AI also found.
"""
import pandas as pd

from .schemas import normalize_category


def compare(analysis: dict, human: pd.DataFrame) -> dict:
    ai = pd.DataFrame(analysis["reviews"])[["review_id", "text", "ai_category", "theme_id", "ai_reason"]]
    h = human[["review_id", "human_category"]].copy()
    h["human_category"] = h["human_category"].astype(str).str.strip()
    h = h[(h["human_category"] != "") & (h["human_category"].str.lower() != "nan")]
    h["human_category"] = h["human_category"].map(normalize_category)
    m = h.merge(ai, on="review_id", how="inner")
    if m.empty:
        raise ValueError("No labelled reviews matched the analysed reviews by review_id.")
    m["match"] = m["human_category"] == m["ai_category"]
    n = len(m)
    agreement = m["match"].mean()

    cats = sorted(set(m["human_category"]) | set(m["ai_category"]))
    p_h = m["human_category"].value_counts(normalize=True)
    p_a = m["ai_category"].value_counts(normalize=True)
    chance = sum(p_h.get(c, 0) * p_a.get(c, 0) for c in cats)
    kappa = (agreement - chance) / (1 - chance) if chance < 1 else 1.0

    rows = []
    for c in cats:
        tp = int(((m["ai_category"] == c) & (m["human_category"] == c)).sum())
        ai_n = int((m["ai_category"] == c).sum())
        hu_n = int((m["human_category"] == c).sum())
        rows.append({"category": c, "your_count": hu_n, "ai_count": ai_n, "both_agree": tp,
                     "precision_pct": round(100 * tp / ai_n, 1) if ai_n else None,
                     "recall_pct": round(100 * tp / hu_n, 1) if hu_n else None})
    confusion = pd.crosstab(m["human_category"], m["ai_category"], rownames=["You"], colnames=["AI"])
    return {
        "n": n,
        "agreement_pct": round(100 * agreement, 1),
        "kappa": round(kappa, 2),
        "per_category": pd.DataFrame(rows),
        "confusion": confusion,
        "disagreements": m[~m["match"]][["review_id", "text", "human_category", "ai_category", "ai_reason"]],
    }


def time_saved(manual_minutes_for_sample: float, sample_size: int, total_reviews: int, ai_seconds: float) -> dict:
    per_review = manual_minutes_for_sample / max(sample_size, 1)
    manual_total = per_review * total_reviews
    ai_minutes = ai_seconds / 60
    return {
        "manual_minutes_projected": round(manual_total, 1),
        "ai_minutes": round(ai_minutes, 1),
        "minutes_saved": round(manual_total - ai_minutes, 1),
        "pct_faster": round(100 * (1 - ai_minutes / manual_total), 1) if manual_total else None,
    }
