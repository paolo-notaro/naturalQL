"""Small, deterministic natural-language normalizations."""

import re
from datetime import date


def normalize_time_phrases(nl: str, today: date) -> str:
    """Resolve supported relative phrases against a configured date."""
    year = today.year
    s = nl
    repl = {
        r"\bthis summer\b": f"between {year}-06-01 and {year}-08-31",
        r"\bthis july\b": f"between {year}-07-01 and {year}-07-31",
        r"\bthis august\b": f"between {year}-08-01 and {year}-08-31",
    }
    for pat, val in repl.items():
        s = re.sub(pat, val, s, flags=re.I)
    return s
