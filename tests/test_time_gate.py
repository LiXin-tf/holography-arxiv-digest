from datetime import datetime
from zoneinfo import ZoneInfo

from holo_arxiv.time_gate import is_allowed_time


BEIJING = ZoneInfo("Asia/Shanghai")


def test_scheduled_run_is_allowed_during_daytime_window():
    assert is_allowed_time(datetime(2026, 8, 28, 13, 45, tzinfo=BEIJING))
    assert is_allowed_time(datetime(2026, 8, 28, 19, 59, tzinfo=BEIJING))


def test_scheduled_run_is_blocked_at_night_and_early_morning():
    assert not is_allowed_time(datetime(2026, 8, 28, 20, 0, tzinfo=BEIJING))
    assert not is_allowed_time(datetime(2026, 8, 29, 0, 49, tzinfo=BEIJING))
    assert not is_allowed_time(datetime(2026, 8, 28, 12, 0, tzinfo=BEIJING))
