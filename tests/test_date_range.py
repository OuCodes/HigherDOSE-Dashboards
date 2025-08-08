from datetime import date, timedelta
from growthkit.reports.executive import PRESET_RANGES


def test_preset_ranges():
    today = date(2025, 8, 6)

    # Month-to-Date
    start, end = PRESET_RANGES["1"][1](today)
    assert start == date(2025, 8, 1)
    assert end == date(2025, 8, 5)

    # Year-to-Date
    start, end = PRESET_RANGES["2"][1](today)
    assert start == date(2025, 1, 1)
    assert end == date(2025, 8, 5)

    # Last 7 days
    start, end = PRESET_RANGES["3"][1](today)
    assert start == today - timedelta(days=7)
    assert end == today - timedelta(days=1)

    # Last 30 days
    start, end = PRESET_RANGES["4"][1](today)
    assert start == today - timedelta(days=30)
    assert end == today - timedelta(days=1)
