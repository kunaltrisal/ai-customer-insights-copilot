"""Shared data shapes and the fixed category list.

The category list is the "taxonomy": a fixed set of buckets every review
must fall into. Themes are finer-grained problems the AI discovers inside
those buckets (for example "No way to move accounts to a new phone" sits
inside "Missing feature").
"""
from pydantic import BaseModel, Field

# Each category has a one-line definition. The same definitions are sent to
# the AI and shown to you when you hand-label reviews, so both of you sort
# reviews by the same rules. Edit these to iterate on accuracy.
CATEGORIES = {
    "Bug or reliability": "Something that should work does not: wrong or rejected codes, crashes, sync or time errors, lost data after an update.",
    "Setup and onboarding friction": "The feature exists but getting started or setting it up is confusing: adding accounts, scanning QR codes, first-time steps, not knowing what to do.",
    "Missing feature": "The user asks for a new capability the product does not have today, even if it would improve an existing screen: backup, moving to a new phone, PIN or fingerprint lock, export, reordering codes, copy on tap, push approve.",
    "Usability and design": "The user asks for a new capability the product does not have today, even if it would improve an existing screen: backup, moving to a new phone, PIN or fingerprint lock, export, reordering codes, copy on tap, push approve.",
    "Privacy, security or permissions": "Concerns about permissions the app asks for, data access, or how secure the product is.",
    "Pricing or billing": "Cost, subscriptions, charges, refunds or confusion about what is free.",
    "Praise": "Positive feedback with no actionable problem.",
    "Other or unclear": "Off-topic, about a different product, or too vague to act on.",
}
NON_ACTIONABLE = {"Praise", "Other or unclear"}
PRAISE_THEME_ID = "PRAISE"
OTHER_THEME_ID = "OTHER"

SEVERITY_SCALE = {
    1: "Minor annoyance; the user can still do what they came to do.",
    2: "Slows the user down or blocks a task, but a workaround exists.",
    3: "User is locked out of accounts, loses data, or cannot use the product at all.",
}


class Theme(BaseModel):
    theme_id: str = Field(description="Short id like T1, T2")
    name: str = Field(description="Specific problem name, 3 to 8 words")
    category: str = Field(description="Exactly one of the allowed category names")
    description: str = Field(description="One sentence describing the user problem")


class ThemeList(BaseModel):
    themes: list[Theme]


class ReviewLabel(BaseModel):
    review_id: str
    theme_id: str = Field(description="One theme_id from the theme list, or PRAISE, or OTHER")
    category: str = Field(description="Exactly one of the allowed category names")
    severity: int = Field(description="1, 2 or 3 using the severity scale")
    churn_risk: bool = Field(description="True only if the user says they will stop using, uninstall, switch, or already left")
    reason: str = Field(description="Under 15 words: why this theme and severity")


class LabelBatch(BaseModel):
    labels: list[ReviewLabel]


def normalize_category(value: str) -> str:
    """Map whatever the AI returned onto an allowed category name."""
    if not value:
        return "Other or unclear"
    v = value.strip().lower()
    for name in CATEGORIES:
        if v == name.lower():
            return name
    for name in CATEGORIES:  # tolerate partial matches like "Bug"
        if v in name.lower() or name.lower().split(" ")[0] in v:
            return name
    return "Other or unclear"
