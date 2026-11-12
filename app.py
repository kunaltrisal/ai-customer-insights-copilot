"""AI Customer Insights Copilot: the web app.

Run locally with:  streamlit run app.py
"""
import json
import os
from pathlib import Path

import io
from docx import Document

import altair as alt
import pandas as pd
import streamlit as st

from copilot.data_io import load_feedback
from copilot.evaluation import compare, time_saved
from copilot.llm import GeminiClient, LLMError
from copilot.pipeline import run_analysis
from copilot.prd import draft_prd
from copilot.schemas import CATEGORIES, SEVERITY_SCALE
from copilot.scoring import DEFAULT_WEIGHTS, category_table, evidence, theme_table

ROOT = Path(__file__).parent
SAMPLE_CSV = ROOT / "data" / "google_authenticator_reviews.csv"
SAMPLE_LABELS = ROOT / "data" / "labeling_sheet_50.csv"
SAVED_DEMO = ROOT / "data" / "sample_analysis.json"
BAR_COLOR = "#4C6FFF"

def prd_to_docx(md_text: str) -> bytes:
    doc = Document()
    for line in md_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("### "):
            doc.add_heading(s[4:].replace("**", ""), level=3)
        elif s.startswith("## "):
            doc.add_heading(s[3:].replace("**", ""), level=2)
        elif s.startswith("# "):
            doc.add_heading(s[2:].replace("**", ""), level=1)
        elif s.startswith(("- ", "* ")):
            doc.add_paragraph(s[2:].replace("**", "").replace("*", ""), style="List Bullet")
        else:
            doc.add_paragraph(s.replace("**", "").replace("*", ""))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

st.set_page_config(page_title="AI Customer Insights Copilot", layout="wide")
ss = st.session_state
ss.setdefault("analysis", None)
ss.setdefault("prds", {})
ss.setdefault("human_labels", None)


def secret_key() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def set_analysis(a: dict):
    ss.analysis, ss.prds, ss.human_labels = a, {}, None


# ---------------- Sidebar: settings ----------------
with st.sidebar:
    st.header("Settings")
    key = secret_key()
    if not key:
        key = st.text_input("Gemini API key", type="password",
                            help="Free key from aistudio.google.com. It stays in this browser session only.")
    else:
        st.caption("Gemini API key loaded from secrets.")
    model = st.selectbox("Gemini model", ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"],
                         accept_new_options=True, help="Type another model id if these are retired.")
    product = st.text_input("Product name", "Google Authenticator (Android app)")
    max_themes = st.slider("Max problem themes", 4, 10, 8)

    st.subheader("Priority weights")
    st.caption("How much each signal counts in the priority score.")
    w_f = st.slider("Frequency", 0.0, 1.0, DEFAULT_WEIGHTS["frequency"], 0.05)
    w_s = st.slider("Severity", 0.0, 1.0, DEFAULT_WEIGHTS["severity"], 0.05)
    w_i = st.slider("Customer impact", 0.0, 1.0, DEFAULT_WEIGHTS["impact"], 0.05)
    weights = {"frequency": w_f, "severity": w_s, "impact": w_i}

    st.subheader("Saved analysis")
    saved = st.file_uploader("Load a saved analysis (.json)", type=["json"])
    if saved is not None and st.button("Load it"):
        set_analysis(json.load(saved))
    if SAVED_DEMO.exists() and st.button("Load demo results"):
        set_analysis(json.loads(SAVED_DEMO.read_text()))


def get_llm():
    if not key:
        st.error("Add a Gemini API key in the sidebar first.")
        st.stop()
    return GeminiClient(key, model)


st.title("AI Customer Insights Copilot")
st.write("Upload customer feedback. The AI groups it into problem themes, ranks them, shows the customer quotes behind "
         "each one, drafts a one-page PRD, and checks its own accuracy against your labels.")

tab_up, tab_pri, tab_ev, tab_prd, tab_acc = st.tabs(
    ["1. Upload", "2. Priorities", "3. Evidence", "4. PRD", "5. Accuracy check"])

# ---------------- 1. Upload ----------------
with tab_up:
    src = st.radio("Feedback source", ["Sample: 200 Google Authenticator Play Store reviews", "Upload my own CSV"])
    df, notes = None, []
    try:
        if src.startswith("Sample"):
            df, notes = load_feedback(SAMPLE_CSV)
            st.caption("Public reviews from the University of Zurich 'Android Apps and User Feedback' dataset "
                       "(github.com/sealuzh/user_quality), 2016 to 2017.")
        else:
            up = st.file_uploader("CSV with one piece of feedback per row (10 to 300 rows). "
                                  "Columns: text (required), rating and review_id (optional).", type=["csv"])
            if up is not None:
                df, notes = load_feedback(up)
    except ValueError as e:
        st.error(str(e))
    for n in notes:
        st.info(n)
    if df is not None:
        c1, c2 = st.columns(2)
        c1.metric("Feedback rows", len(df))
        if df["rating"].notna().any():
            c2.metric("Average rating", f"{df['rating'].mean():.2f}")
        st.dataframe(df, use_container_width=True, height=260, hide_index=True)
        calls = 1 + -(-len(df) // 40)
        if st.button(f"Run AI analysis (about {calls} Gemini calls)", type="primary"):
            llm = get_llm()
            bar = st.progress(0.0, "Starting")
            try:
                a = run_analysis(llm, product, df, max_themes, progress=lambda f, t="Working": bar.progress(min(f, 1.0), t))
                set_analysis(a)
                bar.progress(1.0, "Done")
            except (LLMError, ValueError) as e:
                st.error(str(e))
    if ss.analysis:
        a = ss.analysis
        u = a.get("usage", {})
        st.success(f"Analysed {len(a['reviews'])} reviews in {a['seconds']} seconds with {a['model']} "
                   f"({u.get('api_calls', '?')} API calls, {u.get('input_tokens', 0) + u.get('output_tokens', 0):,} tokens, "
                   f"prompt {a['prompt_version']}). Open the Priorities tab.")

if not ss.analysis:
    for t in (tab_pri, tab_ev, tab_prd, tab_acc):
        with t:
            st.info("Run the analysis in the Upload tab first.")
    st.stop()

a = ss.analysis
table = theme_table(a, weights)
name_of = {t["theme_id"]: t["name"] for t in a["themes"]}

# ---------------- 2. Priorities ----------------
with tab_pri:
    st.subheader("Ranked problems")
    show = table[["rank", "name", "category", "count", "share_pct", "avg_severity", "unhappy_share", "churn_share", "priority_score"]].copy()
    show["unhappy_share"] = (100 * show["unhappy_share"]).round(1)
    show["churn_share"] = (100 * show["churn_share"]).round(1)
    show["avg_severity"] = show["avg_severity"].round(2)
    st.dataframe(show.rename(columns={
        "rank": "Rank", "name": "Problem theme", "category": "Category", "count": "Reviews", "share_pct": "% of all reviews",
        "avg_severity": "Avg severity (1-3)", "unhappy_share": "% 1-2 stars", "churn_share": "% churn risk",
        "priority_score": "Priority score"}), use_container_width=True, hide_index=True)

    chart = alt.Chart(table).mark_bar(color=BAR_COLOR).encode(
        x=alt.X("priority_score:Q", title="Priority score (0 to 100)"),
        y=alt.Y("name:N", sort="-x", title=None),
        tooltip=["name", "count", "priority_score"]).properties(height=36 * len(table) + 40)
    st.altair_chart(chart, use_container_width=True)

    with st.expander("How the priority score is calculated"):
        st.markdown(
            "- **Frequency** = reviews in this theme ÷ reviews in the biggest theme\n"
            "- **Severity** = (average severity − 1) ÷ 2, so 1 becomes 0 and 3 becomes 1\n"
            "- **Customer impact** = half the share of 1 to 2 star reviewers + half the share at churn risk\n"
            "- **Score** = 100 × weighted average of the three, using the sidebar weights\n\n"
            "Severity scale given to the AI:\n" + "\n".join(f"- {k}: {v}" for k, v in SEVERITY_SCALE.items()) +
            "\n\nThe AI only labels each review. All counting and ranking is plain arithmetic on those labels.")

    st.subheader("All feedback by category")
    st.dataframe(category_table(a).rename(columns={"category": "Category", "reviews": "Reviews", "share_pct": "% of all"}),
                 hide_index=True)

    c1, c2 = st.columns(2)
    c1.download_button("Download analysis (.json)", json.dumps(a, default=str, indent=1), "analysis.json", "application/json")
    c2.download_button("Download labelled reviews (.csv)", pd.DataFrame(a["reviews"]).assign(
        theme=lambda d: d.theme_id.map(name_of)).to_csv(index=False), "labelled_reviews.csv", "text/csv")

# ---------------- 3. Evidence ----------------
with tab_ev:
    options = list(table["theme_id"]) + ["PRAISE", "OTHER"]
    pick = st.selectbox("Theme", options, format_func=lambda t: name_of.get(t, t), key="ev_theme")
    th = next(t for t in a["themes"] if t["theme_id"] == pick)
    st.markdown(f"**{th['name']}** ({th['category']}). {th['description']}")
    ev = evidence(a, pick)
    st.caption(f"{len(ev)} reviews, most severe first. These are the customers' own words, not AI summaries.")
    for _, r in ev.iterrows():
        rating = "" if pd.isna(r.get("rating")) else f"{int(r['rating'])}★ · "
        churn = " · churn risk" if r["churn_risk"] else ""
        with st.container(border=True):
            st.markdown(f"> {r['text']}")
            st.caption(f"{r['review_id']} · {rating}severity {r['severity']}{churn} · AI note: {r['ai_reason']}")

# ---------------- 4. PRD ----------------
with tab_prd:
    pick = st.selectbox("Problem to write a PRD for", list(table["theme_id"]),
                        format_func=lambda t: f"#{int(table.set_index('theme_id').loc[t, 'rank'])} {name_of[t]}", key="prd_theme")
    if st.button("Draft PRD with Gemini", type="primary"):
        with st.spinner("Drafting"):
            try:
                ss.prds[pick] = draft_prd(get_llm(), a, pick, weights)
            except (LLMError, ValueError) as e:
                st.error(str(e))
    if pick in ss.prds:
        md = st.text_area("Edit the draft", ss.prds[pick], height=420)
        ss.prds[pick] = md
        with st.container(border=True):
            st.markdown(md)
        st.download_button("Download PRD (.md)", md, f"PRD_{name_of[pick][:40].replace(' ', '_')}.md", "text/markdown")
        st.download_button(
            "Download PRD (.docx)",
            prd_to_docx(md),
            f"PRD_{name_of[pick][:40].replace(' ', '_')}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

# ---------------- 5. Accuracy check ----------------
with tab_acc:
    st.write("Label reviews yourself, then compare. Time yourself while you label: that is your manual baseline.")
    with st.expander("Category definitions (use these while labelling)"):
        st.markdown("\n".join(f"- **{k}**: {v}" for k, v in CATEGORIES.items()))
    how = st.radio("Your labels", ["Label 50 reviews here", "Upload a filled labeling CSV"], horizontal=True)
    if how.startswith("Label"):
        if ss.human_labels is None:
            base = pd.DataFrame(a["reviews"]).head(50)[["review_id", "text"]]
            if SAMPLE_LABELS.exists() and src.startswith("Sample"):
                pre = pd.read_csv(SAMPLE_LABELS, dtype=str).fillna("")
                base = base.merge(pre[["review_id", "human_category"]], on="review_id", how="left").fillna("")
            else:
                base["human_category"] = ""
            ss.human_labels = base
        edited = st.data_editor(
            ss.human_labels, hide_index=True, use_container_width=True, height=420, disabled=["review_id", "text"],
            column_config={"human_category": st.column_config.SelectboxColumn("Your category", options=list(CATEGORIES)),
                           "text": st.column_config.TextColumn("Review", width="large")}, key="label_editor")
        ss.human_labels = edited
        human = edited
        st.download_button("Save my labels (.csv)", edited.to_csv(index=False), "my_labels.csv", "text/csv")
    else:
        f = st.file_uploader("CSV with review_id and human_category columns", type=["csv"], key="lab_up")
        human = pd.read_csv(f, dtype=str).fillna("") if f is not None else None

    done = 0 if human is None else int((human["human_category"].astype(str).str.strip() != "").sum())
    st.caption(f"{done} reviews labelled.")
    manual_min = st.number_input("Minutes you took to label them by hand", min_value=0.0, step=1.0)

    if human is not None and done >= 10 and st.button("Compare with AI", type="primary"):
        try:
            res = compare(a, human)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        c1, c2, c3 = st.columns(3)
        c1.metric("Agreement with you", f"{res['agreement_pct']}%")
        c2.metric("Cohen's kappa", res["kappa"], help="Agreement after removing luck. Above 0.6 is substantial.")
        c3.metric("Reviews compared", res["n"])
        st.dataframe(res["per_category"], hide_index=True, use_container_width=True)
        st.write("Where you and the AI disagree (read these to improve the category definitions or prompt):")
        st.dataframe(res["disagreements"], hide_index=True, use_container_width=True)
        with st.expander("Confusion table (rows = you, columns = AI)"):
            st.dataframe(res["confusion"], use_container_width=True)
        if manual_min > 0:
            ts = time_saved(manual_min, res["n"], len(a["reviews"]), a["seconds"])
            st.subheader("Time saved")
            st.write(f"By hand: {manual_min:g} min for {res['n']} reviews, so about **{ts['manual_minutes_projected']} min** "
                     f"for all {len(a['reviews'])}. The copilot took **{ts['ai_minutes']} min**, "
                     f"**{ts['pct_faster']}% faster**.")
            top = table.iloc[0]
            st.subheader("Your measured results")
            st.code(
                f"Prompt {a['prompt_version']}, model {a['model']}\n"
                f"Reviews analysed: {len(a['reviews'])}\n"
                f"Agreement with my labels: {res['agreement_pct']}% on {res['n']} reviews (kappa {res['kappa']})\n"
                f"Triage time: {ts['manual_minutes_projected']} min by hand vs {ts['ai_minutes']} min with the copilot\n"
                f"Top problem: {top['name']} ({int(top['count'])} reviews, {top['share_pct']}%)", language=None)
