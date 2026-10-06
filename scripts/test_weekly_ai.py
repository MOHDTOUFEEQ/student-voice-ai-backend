import asyncio

from app.services.academic_week_service import get_current_academic_week
from app.services.issue_service import get_public_weekly_issues, sync_issues_for_week


async def main() -> None:
    week = await get_current_academic_week()
    await sync_issues_for_week(week)
    result = await get_public_weekly_issues(week)
    print("week", result["academic_week"], "cached", result.get("cached"))
    for i, point in enumerate(result["most_frequent"], 1):
        print(f"{i}. {point['title']}")
        print(f"   {point['summary']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
