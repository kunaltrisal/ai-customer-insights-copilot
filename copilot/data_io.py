"""Read an uploaded CSV and find the feedback text, rating and id columns."""
import pandas as pd

TEXT_NAMES = ["text", "review", "feedback", "comment", "comments", "body", "content", "message", "ticket", "description"]
RATING_NAMES = ["rating", "star", "stars", "score"]
ID_NAMES = ["review_id", "id", "ticket_id", "feedback_id"]
MIN_ROWS, MAX_ROWS = 10, 300


def _find(cols, names):
    lower = {c.lower().strip(): c for c in cols}
    for n in names:
        if n in lower:
            return lower[n]
    return None


def load_feedback(file) -> tuple[pd.DataFrame, list[str]]:
    """Return a clean frame with review_id, text, rating (optional) and any notes for the user."""
    notes = []
    raw = pd.read_csv(file)
    text_col = _find(raw.columns, TEXT_NAMES)
    if text_col is None:  # fall back to the column with the longest average text
        obj = raw.select_dtypes("object")
        if obj.empty:
            raise ValueError("No text column found. Name the feedback column 'text' or 'review'.")
        text_col = obj.apply(lambda s: s.astype(str).str.len().mean()).idxmax()
        notes.append(f"Using column '{text_col}' as the feedback text.")
    df = pd.DataFrame({"text": raw[text_col].astype(str).str.strip()})

    rating_col = _find(raw.columns, RATING_NAMES)
    df["rating"] = pd.to_numeric(raw[rating_col], errors="coerce") if rating_col else None
    if rating_col is None:
        notes.append("No rating column found, so the impact score uses churn risk only.")

    id_col = _find(raw.columns, ID_NAMES)
    df["review_id"] = raw[id_col].astype(str) if id_col else [f"R{i + 1:03d}" for i in range(len(df))]
    if "date" in [c.lower() for c in raw.columns]:
        df["date"] = raw[[c for c in raw.columns if c.lower() == "date"][0]]

    df = df[df["text"].str.len() > 3]
    df = df[df["text"].str.lower() != "nan"].drop_duplicates("review_id")
    if len(df) < MIN_ROWS:
        raise ValueError(f"Need at least {MIN_ROWS} pieces of feedback; found {len(df)}.")
    if len(df) > MAX_ROWS:
        notes.append(f"Using the first {MAX_ROWS} of {len(df)} rows to stay within free API limits.")
        df = df.head(MAX_ROWS)
    cols = ["review_id", "text", "rating"] + (["date"] if "date" in df else [])
    return df[cols].reset_index(drop=True), notes
