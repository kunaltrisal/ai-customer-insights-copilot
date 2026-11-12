# How the Copilot works, from first principles

Read this top to bottom once. Every section matches a file in the code, so you can open the file next to it.

---

## 1. The product in one paragraph

A PM has 200 reviews. Reading and sorting them by hand takes well over an hour, and the person doing it gets tired and inconsistent. The Copilot asks an AI model to do the reading and sorting. Then it does the counting and ranking with plain math, shows the real reviews behind every number, and drafts a PRD. Finally it checks the AI's sorting against a human's, so you know how far to trust it.

## 2. The flow

```
CSV  ->  data_io.py     clean rows: review_id, text, rating
     ->  pipeline.py    AI call 1: read all reviews, name the problem themes
                        AI calls 2..6: label 40 reviews per call
                          (theme, category, severity, churn risk, reason)
     ->  scoring.py     math only: count, average, rank      ->  Priorities tab
                        filter real reviews by theme           ->  Evidence tab
     ->  prd.py         AI call: write a PRD from the numbers  ->  PRD tab
     ->  evaluation.py  compare AI labels with yours           ->  Accuracy tab
```

For 200 reviews that is 6 AI calls to analyse, plus 1 per PRD.

## 3. Concepts, one at a time

### What an LLM is (llm.py)
A large language model is a program trained on a huge amount of text to predict the next words. If you give it instructions plus data ("sort these reviews into these buckets"), the most likely continuation is the answer. It does not look anything up and it does not "know" your product; it only sees the text you send. Gemini is Google's LLM.

### API and API key
An API is a door that lets your program send a request to someone else's computer and get a reply. Your code sends text to Google's Gemini servers and gets text back. The API key is a password that tells Google the request is yours, so it can apply your free quota. It must never be put on GitHub.

### Prompt (prompts.py)
The prompt is the full text sent to the model: role, task, rules, category definitions, and the reviews. Prompt quality decides output quality, so all prompts sit in one file. `PROMPT_VERSION` is bumped every time you change one, so every accuracy number is tied to the prompt that produced it.

### Structured output (schemas.py)
If you ask "what theme is this?", the model might reply in a full sentence, and code cannot read that reliably. So the app hands Gemini a schema: an exact shape the reply must take, for example a list where every item has `review_id`, `theme_id`, `category`, `severity` (a number), `churn_risk` (true or false) and `reason`. Gemini then returns JSON in that shape, and Python reads it directly.

### Temperature
A setting from 0 upward that controls randomness. At 0 the model picks its most likely answer every time, which you want for labelling, because the same review should get the same label on every run. The PRD uses 0.4, so the writing reads naturally.

### Taxonomy vs themes
- **Categories** (8, fixed, in `schemas.py`) are broad buckets that never change: Bug, Onboarding friction, Missing feature, and so on. Because they are fixed, you can measure accuracy against them.
- **Themes** (up to 8, discovered fresh each run) are specific problems inside the buckets, for example "No way to move accounts to a new phone". They make the output actionable.

### Batching (pipeline.py)
The app sends 40 reviews per labelling call, not all 200 at once. A shorter reply is less likely to skip reviews or get cut off, and if one call fails only that batch is retried. On the free tier 40 is also a good balance between number of calls and reply length.

### Guardrails: not trusting the AI blindly (pipeline.py)
Models sometimes make things up. The code checks every reply:
- A review id the model invents is thrown away.
- A theme id that does not exist becomes "Other".
- A severity outside 1 to 3 is clipped back into range.
- A review the model skipped is sent again once. If it is still missing, it is marked "Not labelled by the AI", never silently dropped.
- Evidence quotes are pulled from your CSV by review id, not written by the AI, so a quote on screen is always something a customer really wrote. This is called **grounding**.

### Prioritisation (scoring.py)
The AI only labels. Ranking is arithmetic, so you can explain and defend every number:

- Frequency = reviews in this theme ÷ reviews in the biggest theme
- Severity = (average severity − 1) ÷ 2, which turns the 1-to-3 scale into 0-to-1
- Impact = half the share of 1 to 2 star reviewers + half the share at churn risk
- Score = 100 × (0.5 × Frequency + 0.3 × Severity + 0.2 × Impact)

Worked example: a theme has 30 reviews (the biggest has 40), average severity 2.6, 80% of its reviewers gave 1 or 2 stars, and 20% said they would leave.
Frequency = 30/40 = 0.75. Severity = (2.6 − 1)/2 = 0.8. Impact = 0.5×0.8 + 0.5×0.2 = 0.5.
Score = 100 × (0.375 + 0.24 + 0.10) = **71.5**.

The weights are a product judgment, which is why they are sliders: a PM fighting churn might raise Impact.

### PRD generation (prd.py)
The PRD prompt contains only the measured numbers and up to 12 real quotes. It forces fixed sections, makes the model cite review ids, and makes it start anything unsupported with "Assumption:". That keeps the draft honest and easy to check.

### Evaluation (evaluation.py)
This is what makes it a PM project and not a demo. You label 50 reviews into the same 8 categories, using the same definitions the AI saw.
- **Agreement**: the share of reviews where you and the AI picked the same category. 42 of 50 is 84%.
- **Cohen's kappa**: agreement after removing what pure luck would give. If both of you call 60% of reviews "Bug", you would agree often by chance alone. Kappa = (observed agreement − chance agreement) ÷ (1 − chance agreement). 0 means no better than luck, 1 means perfect, and above 0.6 is usually called substantial.
- **Precision for a category**: of the reviews the AI called "Bug", the share you also called "Bug".
- **Recall for a category**: of the reviews you called "Bug", the share the AI also found.
- **Disagreements list**: the reviews to read. If the AI keeps calling "no backup to new phone" a Bug while you call it a Missing feature, sharpen the definition in `schemas.py`, bump `PROMPT_VERSION` to v2, re-run and compare. That loop (measure, find the failure, change one thing, measure again) is "launch, test performance and iterate quickly" from the job post.

### Cost and speed
Models charge, or count against your free quota, by **tokens**, which are chunks of about 4 characters. 200 reviews come to roughly 10,000 input tokens per pass. The app shows calls, tokens and seconds after each run, which is the data you would use to estimate cost at scale.

## 4. Product decisions you can defend in an interview

1. **AI labels, math ranks.** An AI ranking cannot be explained and can change from run to run. Arithmetic on labels is explainable and adjustable.
2. **Fixed categories plus discovered themes.** Fixed categories make accuracy measurable; themes make output specific.
3. **Quotes are never generated.** A PM shares evidence with engineers and leaders, and one invented quote would destroy trust in the tool.
4. **Human evaluation built in.** Teams need a number to decide how much to trust the tool before using it for roadmap decisions.
5. **One primary theme per review.** Simpler to count and evaluate. The trade-off is that a review with two complaints counts only once. Multi-label is the next version.
6. **Validation on every reply.** The product handles model mistakes instead of hoping there are none.

What you would build next: clustering with embeddings to handle 10,000+ reviews, trends over time and by app version, direct import from Play Console or Zendesk, and multi-label support.

## 5. A strong story for the interview

The dataset ends in April 2017. If the Copilot ranks "no way to move accounts to a new phone" or "no backup" near the top, you can point out that Google later shipped account transfer by QR code (2020) and Google Account cloud sync for Authenticator (2023). The tool found, from 200 public reviews, a problem the product team later chose to fix. Only say this if your run actually shows it, and check those dates yourself before using them.

## 6. Runbook to finish by Nov 12

1. Get a key at aistudio.google.com (2 min).
2. Install and run the tests (10 min). See README.
3. **Label first, before you look at any AI output**, so you are not biased: open `data/labeling_sheet_50.csv` in Excel, or use the Accuracy tab after step 4 without looking at the other tabs. Time yourself with your phone (about 20 to 30 min).
4. `streamlit run app.py`, use the sample data, click Run (about 1 to 2 min).
5. Accuracy tab: enter your labels and minutes, then click Compare. Write down the numbers.
6. Read the disagreements. If one pattern repeats, edit that category definition in `schemas.py`, set `PROMPT_VERSION = "v2"`, re-run and compare again. Keep both results, because v1 to v2 is your iteration story.
7. Draft the PRD for the #1 problem, edit it yourself, and download it.
8. Download `analysis.json` and save it as `data/sample_analysis.json`. Fill the Results table in README.
9. Push to GitHub and deploy on Streamlit Cloud (20 min).
10. Record a 60 to 90 second screen video: upload, priorities, evidence, PRD, accuracy.

## 7. Resume bullets (fill with your measured values only)

**AI Customer Insights Copilot** | Python, Gemini API, Streamlit | [GitHub] | [Live app]
- Built an LLM web app that turns 200 customer reviews into ranked product problems with real-quote evidence and a drafted PRD, cutting triage time from [X] min to [Y] min ([Z]% faster)
- Measured AI labels against 50 hand-labelled reviews ([A]% agreement, kappa [K]) and raised agreement to [B]% by revising category definitions across [N] prompt versions

If you only ran one version, drop the second half of bullet 2 and keep the agreement number.

## 8. Questions to expect, with short answers

- **Why trust the AI?** I don't blindly. I measured [A]% agreement with my own labels, and every number links back to real reviews.
- **Where does it fail?** [Name the category pair from your confusion table], because those definitions overlap.
- **How would it scale to 1 million reviews?** Embeddings to cluster first, then label a sample of each cluster, plus a cheaper model like Flash-Lite for labelling.
- **How would you know it helps PMs?** Time to first insight, the share of themes PMs accept without edits, and whether roadmap items cite it.
- **Why these weights?** A starting judgment of frequency first. They are sliders because the right weights depend on the team's goal, such as growth vs retention.
- **What is the biggest risk?** A confident but wrong theme that drives a roadmap decision. That is why evidence and the accuracy check are built in.
