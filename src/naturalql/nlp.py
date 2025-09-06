"""src/naturalql/nlp.py: Natural language preprocessing for NaturalQL."""

import re


# Minimal phrase normalizer to make NL more deterministic pre-LLM
def normalize_time_phrases(nl: str, year: int = 2025) -> str:
    s = nl
    repl = {
        r"\bthis summer\b": f"between {year}-06-01 and {year}-08-31",
        r"\bthis july\b": f"between {year}-07-01 and {year}-07-31",
        r"\bthis august\b": f"between {year}-08-01 and {year}-08-31",
    }
    for pat, val in repl.items():
        s = re.sub(pat, val, s, flags=re.I)
    return s
