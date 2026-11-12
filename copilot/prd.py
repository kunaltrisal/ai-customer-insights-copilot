"""Draft a one-page PRD for one ranked problem theme."""
from . import prompts
from .scoring import evidence, theme_stats, theme_table


def draft_prd(llm, analysis: dict, theme_id: str, weights: dict = None, n_quotes: int = 12) -> str:
    table = theme_table(analysis, weights)
    row = table[table["theme_id"] == theme_id]
    if row.empty:
        raise ValueError("Pick a problem theme (Praise and Other cannot get a PRD).")
    row = row.iloc[0]
    stats = theme_stats(row, len(analysis["reviews"]), len(table))
    quotes = evidence(analysis, theme_id, n_quotes)
    quote_rows = [{"review_id": q.review_id, "rating": "?" if q.get("rating") is None else int(q["rating"]),
                   "text": q["text"]} for _, q in quotes.iterrows()]
    theme = {"name": row["name"], "category": row["category"], "description": row["description"]}
    text = llm.generate_text(prompts.prd_prompt(analysis["product"], theme, stats, quote_rows), temperature=0.4)
    header = (f"# PRD: {row['name']}\n\n"
              f"*Product: {analysis['product']}. Drafted by AI Customer Insights Copilot from "
              f"{stats['total_reviews']} reviews; review and edit before sharing.*\n\n")
    return header + text.replace("—", ", ")
