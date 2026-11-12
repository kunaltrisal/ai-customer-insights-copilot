# AI Customer Insights Copilot
Live App: https://ai-customer-insights-copilot-cbmyq4gbpdvludcajf5aed.streamlit.app/

Product managers get hundreds of reviews and support tickets. Reading them all takes hours, and patterns get missed. This web app turns a CSV of customer feedback into a ranked list of product problems, backed by real customer quotes, and drafts a one-page PRD for the problem you pick. It also measures its own accuracy against labels a human gives it.

Built with Python, Streamlit and the Gemini API.

## What it does

1. **Upload**: a CSV of 10 to 300 reviews or tickets (a sample of 200 Google Authenticator Play Store reviews is included).
2. **Theme discovery**: Gemini reads all the feedback and names the recurring problems, each in one of 8 fixed categories (bug, onboarding friction, missing feature, usability, privacy, pricing, praise, other).
3. **Labelling**: Gemini gives every review a theme, a category, a severity from 1 to 3 and a churn-risk flag, 40 reviews per call.
4. **Prioritisation**: plain arithmetic, not AI, ranks the problems by frequency, severity and customer impact. You can change the weights.
5. **Evidence**: click a theme to read the actual reviews behind it.
6. **PRD**: Gemini drafts a one-page PRD for a chosen problem, using only the measured numbers and quotes.
7. **Accuracy check**: you label 50 reviews yourself; the app reports agreement, Cohen's kappa, per-category precision and recall, and every disagreement.

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
4. Do not add your key to the cloud secrets. Visitors either load the demo results or paste their own key, so nobody uses up your free quota.

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
LEARN.md                Every concept explained, plus interview prep
```

## Data

The sample comes from *Android Apps and User Feedback: a Dataset for Software Evolution and Quality Improvement* by Grano, Di Sorbo, Mercaldo, Visaggio, Canfora and Panichella (University of Zurich and University of Sannio), https://github.com/sealuzh/user_quality. 200 English reviews of Google Authenticator (2016 to 2017) were sampled with the original star-rating mix kept, and lightly cleaned.

## Results

Fill this in from the Accuracy check tab after your run:

| Measure | Value |
|---|---|
| Reviews analysed | 200 |
| Agreement with human labels (50 reviews) | _%_ |
| Cohen's kappa | _ |
| Manual triage time (projected for 200) | _ min |
| Copilot time | _ min |
| Top-ranked problem | _ |
