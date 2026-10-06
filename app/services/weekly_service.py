from datetime import datetime, timezone
from typing import Any

from app.database import get_database
from app.services import ai_service
from app.services.analytics_service import overview_stats
from app.services.issue_service import get_public_weekly_issues


async def get_or_generate_weekly_insights(week: int) -> dict[str, Any]:
    db = get_database()
    existing = await db["WeeklyInsights"].find_one({"academic_week": week})
    if existing and existing.get("generated_at"):
        existing["id"] = str(existing.pop("_id"))
        return existing

    stats = await overview_stats()
    issues = await get_public_weekly_issues(week)
    feedback_count = await db["Issues"].count_documents({"academic_week": week, "type": "feedback"})
    suggestion_count = await db["Issues"].count_documents({"academic_week": week, "type": "suggestion"})

    themes = await db["Issues"].aggregate(
        [
            {"$match": {"academic_week": week}},
            {"$unwind": "$ai_themes"},
            {"$group": {"_id": "$ai_themes", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8},
        ]
    ).to_list(8)

    payload = {
        "total_submissions": feedback_count + suggestion_count,
        "total_feedback": feedback_count,
        "total_suggestions": suggestion_count,
        "themes": [t["_id"] for t in themes],
        "top_issues": issues.get("most_frequent", [])[:5],
        "priority_issues": [],
        "sentiment": stats.get("sentiment_overview"),
    }

    try:
        ai_summary = ai_service.generate_weekly_summary(week, payload)
    except Exception:
        ai_summary = {"summary": "Weekly summary pending AI processing.", **payload}

    doc = {
        "academic_week": week,
        "total_feedback": feedback_count,
        "total_suggestions": suggestion_count,
        "top_themes": [t["_id"] for t in themes],
        "top_issues": issues.get("most_frequent", []),
        "priority_issues": issues.get("priority_issues", []),
        "sentiment": stats.get("sentiment_overview"),
        "recurring_issues": [],
        "emerging_issues": [],
        "recommended_actions": ai_summary.get("recommended_actions") or [],
        "changes_from_previous_week": ai_summary.get("changes_from_previous_week"),
        "ai_summary": ai_summary,
        "generated_at": datetime.now(timezone.utc),
    }
    await db["WeeklyInsights"].update_one(
        {"academic_week": week},
        {"$set": doc},
        upsert=True,
    )
    doc["id"] = "generated"
    return doc
