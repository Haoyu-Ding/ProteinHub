from __future__ import annotations

from proteinhub.ui.support import format_datetime_minute


def test_format_datetime_minute_hides_microseconds_and_timezone() -> None:
    assert format_datetime_minute("2026-08-25 14:20:31.520007+08") == "2026-08-25 14:20"
    assert format_datetime_minute("2026-08-25T14:20:31Z") == "2026-08-25 14:20"
    assert format_datetime_minute("") == ""
