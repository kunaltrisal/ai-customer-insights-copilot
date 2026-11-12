# AI Customer Insights Copilot
Live App: https://ai-customer-insights-copilot-cbmyq4gbpdvludcajf5aed.streamlit.app/

AI Customer Insights Copilot helps product teams turn unstructured customer feedback into actionable product insights. It analyses customer reviews, identifies recurring issues, prioritises them using configurable scoring criteria, and generates evidence-backed Product Requirement Documents (PRDs).

The application also includes a human-in-the-loop evaluation framework to measure the accuracy of AI-generated classifications against manually labelled reviews.

**Tech Stack:** Python, Streamlit, Google Gemini API, Pandas. This web app turns a CSV of customer feedback into a ranked list of product problems, backed by real customer quotes, and drafts a one-page PRD for the problem you pick. It also measures its own accuracy against labels a human gives it.

Built with Python, Streamlit and the Gemini API.

## What it does

1. **Upload**: a CSV of 10 to 300 reviews or tickets (a sample of 200 Google Authenticator Play Store reviews is included).
2. **Theme discovery**: Identifies recurring customer pain points through LLM-based theme discovery, each in one of 8 fixed categories (bug, onboarding friction, missing feature, usability, privacy, pricing, praise, other).
3. **Labelling**: Gemini gives every review a theme, a category, a severity from 1 to 3 and a churn-risk flag, 40 reviews per call.
4. **Prioritisation**: Ranks identified problems using a configurable, weighted scoring model, ranks the problems by frequency, severity and customer impact. You can change the weights.
5. **Evidence**: Provides traceability through original customer reviews associated with each theme.
6. **PRD**: Gemini drafts a one-page PRD for a chosen problem, using only the measured numbers and quotes.
7. **Accuracy check**: Evaluates model performance against a manually annotated dataset of 50 reviews; the app reports agreement, Cohen's kappa, per-category precision and recall, and every disagreement.

## Run it on your laptop

You need Python 3.10 or newer and a free Gemini API key from https://aistudio.google.com (click "Get API key").

```bash
cd ai-customer-insights-copilot
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q          # 8 offline tests, no API key needed
streamlit run app.py         # opens http://localhost:8501
```

Paste your API key in the sidebar, or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and put it there.

## Deploy a public link (Streamlit Community Cloud, free)

1. Push this folder to a public GitHub repo (never push `secrets.toml`).
2. After your first real run, click **Download analysis (.json)** on the Priorities tab, save it as `data/sample_analysis.json` and commit it. Visitors can then click **Load demo results** without a key.
3. Go to https://share.streamlit.io, click **Create app**, pick the repo, branch `main` and file `app.py`, and deploy.
4. The application supports user-provided Gemini API keys. Demo results can be accessed without an API key. API credentials are not stored in the public repository. Users supplying their own keys are responsible for their API usage.

## Project layout

```
app.py                  Streamlit screens (5 tabs)
copilot/schemas.py      Categories, severity scale, data shapes the AI must return
copilot/prompts.py      Every prompt sent to Gemini (PROMPT_VERSION lives here)
copilot/llm.py          Gemini API wrapper: structured JSON, retries, token counts
copilot/pipeline.py     Theme discovery and batch labelling, with validation
copilot/scoring.py      Priority formula and evidence lookup (no AI)
copilot/prd.py          PRD drafting
copilot/evaluation.py   Agreement, kappa, precision, recall, time saved
copilot/data_io.py      CSV loading and column detection
tests/                  Offline tests with a fake model
data/                   Sample reviews and the 50-row labelling sheet
```

## Data

The sample comes from *Android Apps and User Feedback: a Dataset for Software Evolution and Quality Improvement* by Grano, Di Sorbo, Mercaldo, Visaggio, Canfora and Panichella (University of Zurich and University of Sannio), https://github.com/sealuzh/user_quality. 200 English reviews of Google Authenticator (2016 to 2017) were sampled with the original star-rating mix kept, and lightly cleaned.

