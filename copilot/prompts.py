"""All text sent to the AI lives here, so you can read and improve it in one place.

Bump PROMPT_VERSION every time you change a prompt, so the accuracy you
measure is tied to the prompt version that produced it.
"""
from .schemas import CATEGORIES, SEVERITY_SCALE

PROMPT_VERSION = "v2"


def _category_block() -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in CATEGORIES.items())


def _severity_block() -> str:
    return "\n".join(f"- {level}: {desc}" for level, desc in SEVERITY_SCALE.items())


def _reviews_block(rows) -> str:
    lines = []
    for r in rows:
        rating = f"{int(r['rating'])} stars" if r.get("rating") is not None else "no rating"
        lines.append(f"[{r['review_id']}] ({rating}) {r['text']}")
    return "\n".join(lines)


def theme_discovery_prompt(product: str, rows, max_themes: int) -> str:
    return f"""You are a senior product manager analysing customer feedback for {product}.

Read every review below and identify the {max_themes} or fewer most important recurring PROBLEMS.

Rules:
- A theme is one specific user problem, named so an engineer knows what to look at.
  Good: "No way to move accounts to a new phone". Bad: "Issues" or "Bugs".
- Each theme must appear in at least 3 reviews.
- Do not create themes for praise or off-topic reviews; those are handled separately.
- Do not merge different problems into one theme just to save space.
- Assign each theme exactly one category from this list (use the exact name):
{_category_block()}
- Use theme ids T1, T2, T3 and so on.

Reviews:
{_reviews_block(rows)}
"""


def classification_prompt(product: str, rows, themes) -> str:
    theme_lines = "\n".join(f"- {t.theme_id}: {t.name} ({t.category}). {t.description}" for t in themes)
    return f"""You are labelling customer reviews of {product} for a product manager.

For EVERY review below, return one label with:
1. theme_id: the single best matching theme. If a review mentions several problems, pick the one the user is most upset about.
   Use PRAISE for purely positive reviews and OTHER if no theme fits.
{theme_lines}
   - PRAISE: positive feedback with no actionable problem
   - OTHER: off-topic, vague, or a problem not in the list
2. category: exactly one of these names, judged from the review itself:
{_category_block()}
   If a review has praise and a problem, choose the problem's category.
3. severity (1 to 3):
{_severity_block()}
   Use 1 for PRAISE.
4. churn_risk: true only if the user says they will stop using, uninstall, switch to another app, or already did.
5. reason: under 15 words.

Return exactly one label per review id, and do not invent review ids.

Reviews:
{_reviews_block(rows)}
"""


def prd_prompt(product: str, theme, stats: dict, quotes) -> str:
    quote_lines = "\n".join(f"[{q['review_id']}] ({q['rating']} stars) {q['text']}" for q in quotes)
    return f"""You are an Associate Product Manager at the company that builds {product}.
Write a one-page Product Requirements Document (PRD), about 450 to 600 words, in Markdown, for this problem.

Problem theme: {theme['name']}
Category: {theme['category']}
Description: {theme['description']}

Evidence from customer feedback analysis (use these numbers exactly; do not invent other data):
- Reviews analysed in total: {stats['total_reviews']}
- Reviews about this theme: {stats['count']} ({stats['share_pct']}% of all reviews)
- Average severity: {stats['avg_severity']} on a 1 to 3 scale
- Share of these reviewers giving 1 or 2 stars: {stats['unhappy_pct']}%
- Share saying they will leave or already left: {stats['churn_pct']}%
- Priority rank: {stats['rank']} of {stats['theme_count']} problem themes

Customer quotes (cite them by id, like [R012]):
{quote_lines}

Use exactly these sections, as Markdown headings:
## Problem
## Evidence
## Target users
## Goals and success metrics
## Proposed solution (MVP scope)
## Out of scope
## Risks and open questions
## Launch and measurement plan

Rules:
- Quote at most 4 customers, each in under 25 words, with the review id.
- Success metrics must be measurable (for example: share of reviews mentioning this theme, support tickets, task completion rate).
- Anything not supported by the evidence above must start with "Assumption:".
- Plain, direct language. No em dashes.
"""
