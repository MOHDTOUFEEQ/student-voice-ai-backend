from datetime import date, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.database import get_database


async def get_calendar_settings() -> dict[str, Any]:
    db = get_database()
    doc = await db["Settings"].find_one({"key": "academic_calendar"})
    settings = get_settings()
    if doc and "value" in doc:
        return doc["value"]
    return {
        "current_academic_week": settings.academic_current_week,
        "week_3_start_date": settings.academic_week_3_start_date,
        "total_academic_weeks": settings.academic_total_weeks,
    }


async def update_calendar_settings(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_database()
    current = await get_calendar_settings()
    current.update({k: v for k, v in payload.items() if v is not None})
    await db["Settings"].update_one(
        {"key": "academic_calendar"},
        {"$set": {"key": "academic_calendar", "value": current}},
        upsert=True,
    )
    return current


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_week_start_date(week_number: int, calendar: dict[str, Any]) -> date | None:
    total = int(calendar["total_academic_weeks"])
    if week_number < 1 or week_number > total:
        return None
    week3_start = _parse_date(calendar["week_3_start_date"])
    if week_number == 3:
        return week3_start
    if week_number > 3:
        return week3_start + timedelta(weeks=week_number - 3)
    # Weeks 1–2: count back from week 3 start
    return week3_start - timedelta(weeks=3 - week_number)


def get_academic_week(for_date: date | datetime, calendar: dict[str, Any] | None = None) -> int:
    if calendar is None:
        settings = get_settings()
        calendar = {
            "current_academic_week": settings.academic_current_week,
            "week_3_start_date": settings.academic_week_3_start_date,
            "total_academic_weeks": settings.academic_total_weeks,
        }
    if isinstance(for_date, datetime):
        for_date = for_date.date()
    total = int(calendar["total_academic_weeks"])
    week3_start = _parse_date(calendar["week_3_start_date"])
    if for_date < week3_start:
        weeks_before = (week3_start - for_date).days // 7
        if (week3_start - for_date).days % 7:
            weeks_before += 1
        week = 3 - weeks_before
        return max(1, min(week, total))
    days_after = (for_date - week3_start).days
    week = 3 + days_after // 7
    return max(1, min(week, total))


async def get_current_academic_week() -> int:
    calendar = await get_calendar_settings()
    week3_start = _parse_date(calendar["week_3_start_date"])
    today = date.today()
    if today < week3_start:
        return int(calendar.get("current_academic_week", 2))
    return get_academic_week(today, calendar)


async def get_week_label(week: int) -> str:
    return f"Week {week}"
