"""Offline tests: a fake model stands in for Gemini so the logic can be checked for free.

Run with:  python -m pytest -q
"""
import re
from pathlib import Path

import pandas as pd

from copilot.data_io import load_feedback
from copilot.evaluation import compare, time_saved
from copilot.pipeline import run_analysis
from copilot.prd import draft_prd
from copilot.schemas import LabelBatch, ReviewLabel, Theme, ThemeList
from copilot.scoring import evidence, theme_table

DATA = Path(__file__).resolve().parents[1] / "data" / "google_authenticator_reviews.csv"

RULES = [  # keyword -> (theme, category, severity)
    ("new phone", ("T1", "Missing feature", 3)),
    ("backup", ("T1", "Missing feature", 3)),
    ("wrong", ("T2", "Bug or reliability", 3)),
    ("incorrect", ("T2", "Bug or reliability", 3)),
    ("pin", ("T3", "Missing feature", 1)),
    ("fingerprint", ("T3", "Missing feature", 1)),
    ("camera", ("T4", "Privacy, security or permissions", 2)),
]


class FakeLLM:
    model = "fake"

    def __init__(self, skip_first=False):
        self.calls = 0
        self.skip_first = skip_first

    def usage(self):
        return {"api_calls": self.calls, "input_tokens": 0, "output_tokens": 0}

    def generate_json(self, prompt, schema, temperature=0.0):
        self.calls += 1
        if schema is ThemeList:
            return ThemeList(themes=[
                Theme(theme_id="T1", name="No way to move accounts to a new phone", category="Missing feature", description="d"),
                Theme(theme_id="T2", name="Codes rejected as wrong", category="bug", description="d"),
                Theme(theme_id="T3", name="No PIN or fingerprint lock", category="Missing feature", description="d"),
                Theme(theme_id="T4", name="Camera permission concern", category="Privacy, security or permissions", description="d"),
            ])
        ids = re.findall(r"^\[(R\d+)\] \((\d) stars\) (.*)$", prompt, flags=re.M)
        labels = []
        for i, (rid, stars, text) in enumerate(ids):
            if self.skip_first and i == 0:
                self.skip_first = False
                continue  # simulate the model skipping a review
            low = text.lower()
            theme, cat, sev = ("PRAISE", "Praise", 1) if int(stars) >= 4 else ("OTHER", "Other or unclear", 1)
            for kw, val in RULES:
                if kw in low:
                    theme, cat, sev = val
                    break
            labels.append(ReviewLabel(review_id=rid, theme_id=theme, category=cat, severity=sev,
                                      churn_risk="uninstall" in low, reason="kw"))
        labels.append(ReviewLabel(review_id="R999", theme_id="T9", category="x", severity=7, churn_risk=False, reason="invented"))
        return LabelBatch(labels=labels)

    def generate_text(self, prompt, temperature=0.3):
        self.calls += 1
        assert "Reviews about this theme" in prompt
        return "## Problem\nUsers lose accounts — badly.\n"


def _analysis(**kw):
    df, _ = load_feedback(DATA)
    return run_analysis(FakeLLM(**kw), "Google Authenticator", df), df


def test_load_feedback():
    df, notes = load_feedback(DATA)
    assert len(df) == 200 and set(["review_id", "text", "rating"]) <= set(df.columns)


def test_every_review_labelled_once_and_ids_validated():
    a, df = _analysis(skip_first=True)
    r = pd.DataFrame(a["reviews"])
    assert len(r) == len(df) and r.review_id.is_unique
    assert "R999" not in set(r.review_id)
    assert r.severity.between(1, 3).all()
    assert set(r.theme_id) <= {"T1", "T2", "T3", "T4", "PRAISE", "OTHER"}


def test_ranking_excludes_praise_and_is_sorted():
    a, _ = _analysis()
    t = theme_table(a)
    assert "PRAISE" not in set(t.theme_id) and "OTHER" not in set(t.theme_id)
    assert list(t.priority_score) == sorted(t.priority_score, reverse=True)
    assert t.priority_score.between(0, 100).all()
    assert (t.category == "Bug or reliability").any()  # "bug" was normalised


def test_weights_change_order():
    a, _ = _analysis()
    by_freq = theme_table(a, {"frequency": 1, "severity": 0, "impact": 0})
    assert by_freq.iloc[0]["count"] == by_freq["count"].max()


def test_evidence_is_real_reviews():
    a, df = _analysis()
    ev = evidence(a, "T1")
    assert set(ev.text) <= set(df.text) and len(ev) > 0


def test_prd_has_header_and_no_em_dash():
    a, _ = _analysis()
    top = theme_table(a).iloc[0]["theme_id"]
    md = draft_prd(FakeLLM(), a, top)
    assert md.startswith("# PRD:") and "—" not in md


def test_evaluation_metrics():
    a, _ = _analysis()
    r = pd.DataFrame(a["reviews"]).head(50)
    human = r[["review_id"]].copy()
    human["human_category"] = r["ai_category"].values
    human.loc[:4, "human_category"] = "Usability and design"  # 5 deliberate disagreements
    res = compare(a, human)
    assert res["n"] == 50
    assert res["agreement_pct"] <= 100 and len(res["disagreements"]) >= 1
    assert -1 <= res["kappa"] <= 1


def test_time_saved():
    t = time_saved(25, 50, 200, 90)
    assert t["manual_minutes_projected"] == 100 and t["ai_minutes"] == 1.5
