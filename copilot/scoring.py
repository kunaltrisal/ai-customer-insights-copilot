"""Prioritisation: turn labelled reviews into a ranked list of problems.

No AI here, on purpose. The score is a weighted sum of three plain signals,
each scaled to 0..1, so a PM can explain and adjust it:

  Frequency  = reviews in this theme / reviews in the biggest theme
  Severity   = (average severity - 1) / 2      (maps 1..3 onto 0..1)
  Impact     = half the share of 1-2 star reviewers + half the share at churn risk

  Priority score = 100 x (wF x Frequency + wS x Severity + wI x Impact) / (wF + wS + wI)
"""
import pandas as pd

from .schemas import NON_ACTIONABLE

DEFAULT_WEIGHTS = {"frequency": 0.5, "severity": 0.3, "impact": 0.2}


def theme_table(analysis: dict, weights: dict = None) -> pd.DataFrame:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_w = sum(w.values()) or 1.0
    reviews = pd.DataFrame(analysis["reviews"])
    themes = pd.DataFrame(analysis["themes"])
    total = len(reviews)
    has_rating = "rating" in reviews and reviews["rating"].notna().any()
    reviews["unhappy"] = (reviews["rating"] <= 2) if has_rating else False

    g = reviews.groupby("theme_id").agg(
        count=("review_id", "size"),
        avg_severity=("severity", "mean"),
        unhappy_share=("unhappy", "mean"),
        churn_share=("churn_risk", "mean"),
    ).reset_index()
    t = themes.merge(g, on="theme_id", how="left").fillna({"count": 0, "avg_severity": 1, "unhappy_share": 0, "churn_share": 0})
    t["count"] = t["count"].astype(int)
    t["share_pct"] = (100 * t["count"] / max(total, 1)).round(1)

    actionable = t[~t["category"].isin(NON_ACTIONABLE) & (t["count"] > 0)].copy()
    max_count = actionable["count"].max() if len(actionable) else 1
    actionable["frequency_norm"] = actionable["count"] / max_count
    actionable["severity_norm"] = (actionable["avg_severity"] - 1) / 2
    actionable["impact_norm"] = 0.5 * actionable["unhappy_share"] + 0.5 * actionable["churn_share"]
    actionable["priority_score"] = (100 * (
        w["frequency"] * actionable["frequency_norm"]
        + w["severity"] * actionable["severity_norm"]
        + w["impact"] * actionable["impact_norm"]
    ) / total_w).round(1)
    actionable = actionable.sort_values(["priority_score", "count"], ascending=False).reset_index(drop=True)
    actionable["rank"] = actionable.index + 1
    return actionable


def theme_stats(row, total_reviews: int, theme_count: int) -> dict:
    return {
        "total_reviews": total_reviews,
        "count": int(row["count"]),
        "share_pct": float(row["share_pct"]),
        "avg_severity": round(float(row["avg_severity"]), 2),
        "unhappy_pct": round(100 * float(row["unhappy_share"]), 1),
        "churn_pct": round(100 * float(row["churn_share"]), 1),
        "rank": int(row["rank"]),
        "theme_count": theme_count,
    }


def evidence(analysis: dict, theme_id: str, limit: int = None) -> pd.DataFrame:
    """Real reviews behind a theme, most severe and least happy first."""
    r = pd.DataFrame(analysis["reviews"])
    r = r[r["theme_id"] == theme_id].copy()
    sort_cols, asc = ["severity"], [False]
    if "rating" in r and r["rating"].notna().any():
        sort_cols.append("rating")
        asc.append(True)
    r = r.sort_values(sort_cols, ascending=asc)
    return r.head(limit) if limit else r


def category_table(analysis: dict) -> pd.DataFrame:
    r = pd.DataFrame(analysis["reviews"])
    c = r["ai_category"].value_counts().rename_axis("category").reset_index(name="reviews")
    c["share_pct"] = (100 * c["reviews"] / len(r)).round(1)
    return c
