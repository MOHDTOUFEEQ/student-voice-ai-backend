from collections import Counter
from typing import Any

from app.database import get_database
from app.services.academic_week_service import get_calendar_settings, get_current_academic_week
from app.services import ai_service


async def overview_stats() -> dict[str, Any]:
    db = get_database()
    week = await get_current_academic_week()
    feedback_count = await db["Feedback"].count_documents({"academic_week": week, "type": "feedback"})
    suggestion_count = await db["Feedback"].count_documents({"academic_week": week, "type": "suggestion"})
    top_issue = await db["Issues"].find_one({"academic_week": week}, sort=[("frequency", -1)])
    priority_issue = await db["Issues"].find_one(
        {"academic_week": week, "priority": {"$in": ["high", "critical"]}},
        sort=[("frequency", -1)],
    )
    sentiments = await db["Feedback"].aggregate(
        [
            {"$match": {"academic_week": week, "type": "feedback", "sentiment": {"$ne": None}}},
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
        ]
    ).to_list(10)
    sentiment_map = {s["_id"]: s["count"] for s in sentiments}
    total_s = sum(sentiment_map.values()) or 1
    dominant = max(sentiment_map, key=sentiment_map.get) if sentiment_map else "neutral"
    return {
        "current_week": week,
        "feedback_count": feedback_count,
        "suggestion_count": suggestion_count,
        "top_issue": top_issue["title"] if top_issue else None,
        "priority_issue": priority_issue["title"] if priority_issue else None,
        "sentiment_overview": dominant,
        "sentiment_breakdown": {k: round(v / total_s * 100, 1) for k, v in sentiment_map.items()},
    }


async def full_analytics() -> dict[str, Any]:
    db = get_database()
    calendar = await get_calendar_settings()
    total_weeks = int(calendar["total_academic_weeks"])
    volume = []
    for w in range(1, total_weeks + 1):
        c = await db["Feedback"].count_documents({"academic_week": w})
        volume.append({"week": w, "count": c})

    by_category = await db["Feedback"].aggregate(
        [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
    ).to_list(20)

    sentiment_trends = await db["Feedback"].aggregate(
        [
            {"$match": {"type": "feedback", "sentiment": {"$ne": None}}},
            {"$group": {"_id": {"week": "$academic_week", "sentiment": "$sentiment"}, "count": {"$sum": 1}}},
        ]
    ).to_list(200)

    priority_dist = await db["Feedback"].aggregate(
        [{"$group": {"_id": "$ai_priority", "count": {"$sum": 1}}}]
    ).to_list(10)

    themes = await db["Feedback"].aggregate(
        [
            {"$unwind": "$ai_themes"},
            {"$group": {"_id": "$ai_themes", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 15},
        ]
    ).to_list(15)

    recurring = await _recurring_issues()
    emerging = await _emerging_issues()

    return {
        "volume_by_week": volume,
        "by_category": [{"category": x["_id"], "count": x["count"]} for x in by_category],
        "sentiment_trends": [
            {"week": x["_id"]["week"], "sentiment": x["_id"]["sentiment"], "count": x["count"]}
            for x in sentiment_trends
        ],
        "priority_distribution": [{"priority": x["_id"] or "unknown", "count": x["count"]} for x in priority_dist],
        "common_themes": [{"theme": x["_id"], "count": x["count"]} for x in themes],
        "recurring_issues": recurring,
        "emerging_issues": emerging,
    }


async def _recurring_issues() -> list[dict[str, Any]]:
    db = get_database()
    pipeline = [
        {"$group": {"_id": "$title", "weeks": {"$addToSet": "$academic_week"}, "total": {"$sum": "$frequency"}}},
        {"$match": {"weeks.2": {"$exists": True}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
    ]
    docs = await db["Issues"].aggregate(pipeline).to_list(10)
    return [
        {"title": d["_id"], "weeks_active": len(d["weeks"]), "total_mentions": d["total"]}
        for d in docs
    ]


async def _emerging_issues() -> list[dict[str, Any]]:
    db = get_database()
    week = await get_current_academic_week()
    docs = (
        await db["Issues"]
        .find({"academic_week": week, "trend": "Newly emerging"})
        .sort("frequency", -1)
        .limit(10)
        .to_list(10)
    )
    return [{"title": d["title"], "frequency": d.get("frequency", 0)} for d in docs]


async def suggestions_by_theme() -> list[dict[str, Any]]:
    db = get_database()
    pipeline = [
        {"$match": {"type": "suggestion", "processing_status": "processed"}},
        {"$unwind": {"path": "$ai_themes", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": {"$ifNull": ["$ai_themes", "$category"]},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
    ]
    groups = await db["Feedback"].aggregate(pipeline).to_list(50)
    return [{"theme": g["_id"] or "General", "count": g["count"], "status": "New"} for g in groups]


async def build_admin_ai_context(week: int | None = None) -> dict[str, Any]:
    week = week or await get_current_academic_week()
    db = get_database()
    issues = await db["Issues"].find({"academic_week": week}).sort("frequency", -1).limit(10).to_list(10)
    prev_issues = await db["Issues"].find({"academic_week": week - 1}).sort("frequency", -1).limit(10).to_list(10)
    feedback_count = await db["Feedback"].count_documents({"academic_week": week})
    return {
        "week": week,
        "submission_count": feedback_count,
        "top_issues": [{"title": i["title"], "frequency": i.get("frequency", 0)} for i in issues],
        "previous_week_issues": [{"title": i["title"], "frequency": i.get("frequency", 0)} for i in prev_issues],
        "recurring": await _recurring_issues(),
    }


async def generate_insight_sentence(week: int) -> str:
    ctx = await build_admin_ai_context(week)
    try:
        return ai_service.answer_admin_question(
            "Give one meaningful insight about this week's feedback compared to patterns.",
            ctx,
        )
    except Exception:
        return "Feedback insights will appear once submissions are processed."
