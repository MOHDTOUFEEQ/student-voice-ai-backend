from datetime import date

from app.services.academic_week_service import get_academic_week


CALENDAR = {
    "current_academic_week": 2,
    "week_3_start_date": "2026-10-05",
    "total_academic_weeks": 11,
}


def test_week_before_october_5_is_week_2():
    assert get_academic_week(date(2026, 9, 29), CALENDAR) == 2


def test_october_5_is_week_3():
    assert get_academic_week(date(2026, 10, 5), CALENDAR) == 3


def test_october_12_is_week_4():
    assert get_academic_week(date(2026, 10, 12), CALENDAR) == 4


def test_november_30_is_week_11():
    assert get_academic_week(date(2026, 11, 30), CALENDAR) == 11
