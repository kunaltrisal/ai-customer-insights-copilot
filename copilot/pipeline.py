"""The analysis pipeline: discover themes, then label every review.

Step 1 (one AI call): read all reviews and propose problem themes.
Step 2 (one AI call per batch of reviews): give each review a theme,
        a category, a severity and a churn flag.
Ranking and evidence are then computed in plain Python (scoring.py), not by
the AI, so every number on screen can be traced back to real reviews.
"""
import time

import pandas as pd

from . import prompts
from .schemas import (
    CATEGORIES,
    OTHER_THEME_ID,
    PRAISE_THEME_ID,
    LabelBatch,
    Theme,
    ThemeList,
    normalize_category,
)


def discover_themes(llm, product: str, df: pd.DataFrame, max_themes: int = 8) -> list[Theme]:
    rows = df.to_dict("records")
    result = llm.generate_json(prompts.theme_discovery_prompt(product, rows, max_themes), ThemeList)
    themes, seen = [], set()
    for i, t in enumerate(result.themes[:max_themes], start=1):
        name = t.name.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        themes.append(Theme(theme_id=f"T{len(themes) + 1}", name=name,
                            category=normalize_category(t.category), description=t.description.strip()))
    if not themes:
        raise ValueError("The AI did not return any themes. Try again or check the uploaded text column.")
    return themes


def _label_rows(llm, product, rows, themes) -> dict:
    valid_ids = {t.theme_id for t in themes} | {PRAISE_THEME_ID, OTHER_THEME_ID}
    wanted = {r["review_id"] for r in rows}
    batch = llm.generate_json(prompts.classification_prompt(product, rows, themes), LabelBatch)
    out = {}
    for lab in batch.labels:
        if lab.review_id not in wanted or lab.review_id in out:
            continue  # ignore invented or duplicate ids
        theme_id = lab.theme_id.strip().upper() if lab.theme_id else OTHER_THEME_ID
        if theme_id not in valid_ids:
            theme_id = OTHER_THEME_ID
        out[lab.review_id] = {
            "review_id": lab.review_id,
            "theme_id": theme_id,
            "ai_category": normalize_category(lab.category),
            "severity": min(3, max(1, int(lab.severity or 1))),
            "churn_risk": bool(lab.churn_risk),
            "ai_reason": lab.reason.strip(),
        }
    return out


def classify_reviews(llm, product: str, df: pd.DataFrame, themes: list[Theme],
                     batch_size: int = 40, progress=None) -> pd.DataFrame:
    rows = df.to_dict("records")
    labels: dict = {}
    batches = [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]
    for n, b in enumerate(batches, start=1):
        labels.update(_label_rows(llm, product, b, themes))
        missing = [r for r in b if r["review_id"] not in labels]
        if missing:  # one retry for any review the AI skipped
            labels.update(_label_rows(llm, product, missing, themes))
        if progress:
            progress(n / len(batches))
    for r in rows:  # anything still missing is marked, never silently dropped
        if r["review_id"] not in labels:
            labels[r["review_id"]] = {"review_id": r["review_id"], "theme_id": OTHER_THEME_ID,
                                      "ai_category": "Other or unclear", "severity": 1,
                                      "churn_risk": False, "ai_reason": "Not labelled by the AI"}
    lab_df = pd.DataFrame(labels.values())
    return df.merge(lab_df, on="review_id", how="left")


def run_analysis(llm, product: str, df: pd.DataFrame, max_themes: int = 8, progress=None) -> dict:
    start = time.time()
    if progress:
        progress(0.05, "Step 1 of 2: discovering themes")
    themes = discover_themes(llm, product, df, max_themes)
    themes_all = themes + [
        Theme(theme_id=PRAISE_THEME_ID, name="Praise", category="Praise", description="Positive feedback with no actionable problem."),
        Theme(theme_id=OTHER_THEME_ID, name="Other or unclear", category="Other or unclear", description="Off-topic, vague, or not covered by a theme."),
    ]

    def step2(frac):
        if progress:
            progress(0.15 + 0.85 * frac, "Step 2 of 2: labelling reviews")

    labelled = classify_reviews(llm, product, df, themes, progress=step2)
    usage = llm.usage() if hasattr(llm, "usage") else {}
    return {
        "product": product,
        "prompt_version": prompts.PROMPT_VERSION,
        "model": getattr(llm, "model", "unknown"),
        "seconds": round(time.time() - start, 1),
        "usage": usage,
        "themes": [t.model_dump() for t in themes_all],
        "reviews": labelled.to_dict("records"),
        "categories": list(CATEGORIES),
    }
