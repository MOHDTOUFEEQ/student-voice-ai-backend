from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services import ai_service


async def get_public_weekly_issues(week: int) -> dict[str, Any]:
    """
    Build public Weekly Issues from the Issues collection.
    Uses ChatGPT to consolidate raw feedback into up to 5 specific main points.
    Results are cached in WeeklyInsights so we do not call AI on every page load.
    """
    db = get_database()

    submissions = (
        await db["Issues"]
        .find(
            {
                "academic_week": week,
                "$or": [{"type": "feedback"}, {"type": {"$exists": False}}],
                "message": {"$exists": True, "$ne": ""},
            }
        )
        .sort("created_at", -1)
        .to_list(100)
    )

    if not submissions:
        return {"academic_week": week, "most_frequent": []}

    submission_count = len(submissions)
    cache = await db["WeeklyInsights"].find_one({"key": "public_weekly_issues", "academic_week": week})
    if (
        cache
        and cache.get("submission_count") == submission_count
        and isinstance(cache.get("most_frequent"), list)
        and cache["most_frequent"]
    ):
        return {
            "academic_week": week,
            "most_frequent": cache["most_frequent"][:5],
            "cached": True,
        }

    points = ai_service.summarize_weekly_feedback_themes(submissions, max_points=5)
    most_frequent = [{"title": p["title"], "summary": p["summary"]} for p in points[:5]]

    await db["WeeklyInsights"].update_one(
        {"key": "public_weekly_issues", "academic_week": week},
        {
            "$set": {
                "key": "public_weekly_issues",
                "academic_week": week,
                "submission_count": submission_count,
                "most_frequent": most_frequent,
                "generated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    return {
        "academic_week": week,
        "most_frequent": most_frequent,
        "cached": False,
    }


async def list_issues(week: int | None = None) -> list[dict[str, Any]]:
    db = get_database()
    query: dict[str, Any] = {}
    if week is not None:
        query["academic_week"] = week
    docs = await db["Issues"].find(query).sort("created_at", -1).to_list(200)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


async def update_issue(issue_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    db = get_database()
    await db["Issues"].update_one({"_id": ObjectId(issue_id)}, {"$set": updates})
    doc = await db["Issues"].find_one({"_id": ObjectId(issue_id)})
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def sync_issues_for_week(week: int) -> None:
    """Invalidate cached public weekly themes after new feedback arrives."""
    db = get_database()
    await db["WeeklyInsights"].delete_one({"key": "public_weekly_issues", "academic_week": week})
