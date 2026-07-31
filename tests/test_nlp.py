from datetime import date

from naturalql.nlp import normalize_time_phrases


def test_normalizes_supported_phrases_case_insensitively():
    today = date(2026, 7, 31)
    result = normalize_time_phrases("This Summer and THIS JULY", today)
    assert result == (
        "between 2026-06-01 and 2026-08-31 and between 2026-07-01 and 2026-07-31"
    )


def test_leaves_other_text_unchanged():
    assert normalize_time_phrases("released in 2024", date(2026, 1, 1)) == (
        "released in 2024"
    )
