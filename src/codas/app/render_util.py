from __future__ import annotations

# Neutral render helpers shared by the LLM-free view/book renderers (app/views.py,
# app/book.py). Imports NOTHING from app/ — it is the leaf that breaks the would-be
# app.book -> app.views -> app.wiki -> ... import cycle: both renderers depend on this
# leaf, never on each other.


def mermaid_label(text: str) -> str:
    """A Mermaid-safe quoted-label body. Beyond the quote/newline that break the `["..."]`
    label, also neutralize the bracket/angle/backtick chars that break Mermaid node syntax
    (real module paths never contain these, but a synthetic/adversarial path could).
    Deterministic substitution, never a crash."""
    out = text.replace("\\", "/").replace('"', "'").replace("`", "'")
    out = out.replace("[", "(").replace("]", ")").replace("<", "(").replace(">", ")")
    return out.replace("\n", " ").replace("\r", " ")
