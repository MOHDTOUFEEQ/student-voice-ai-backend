from datetime import datetime, timezone
from typing import Any

from app.database import get_database
from app.services import ai_service


def _effective_priority(doc: dict[str, Any]) -> str:
    return doc.get("admin_priority_override") or doc.get("ai_priority") or doc.get("importance") or "medium"


def _limit_public_clusters(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(clusters, key=lambda c: (c.get("frequency", 0), c.get("strength", 0)), reverse=True)
    if len(ranked) <= 3:
        return ranked
    top = ranked[:4]
    if len(top) == 4 and top[3].get("frequency", 0) < 2 and top[2].get("frequency", 0) >= 2:
        return top[:3]
    return top[:4]


async def sync_issues_for_week(week: int) -> None:
    db = get_database()
    submissions = (
        await db["Feedback"]
        .find(
            {
                "academic_week": week,
                "type": "feedback",
                "processing_status": "processed",
                "is_spam": False,
            }
        )
        .to_list(200)
    )
    if not submissions:
        await db["Issues"].delete_many({"academic_week": week})
        return

    clusters = ai_service.cluster_weekly_issues(submissions)
    seen_keys: set[str] = set()
    for cluster in clusters:
        issue_key = cluster["issue_key"]
        seen_keys.add(issue_key)
        existing = await db["Issues"].find_one({"issue_key": issue_key, "academic_week": week})
        freq = cluster.get("frequency", 1)
        priority = ai_service.calculate_priority(
            freq,
            [s.get("importance", "medium") for s in submissions],
            1,
            "negative",
        )
        trend = "Stable"
        if existing:
            prev_freq = existing.get("frequency", 0)
            if freq > prev_freq:
                trend = "Increasing"
            elif freq < prev_freq:
                trend = "Decreasing"
        payload = {
            "issue_key": issue_key,
            "title": cluster["title"],
            "description": cluster["ai_summary"],
            "frequency": freq,
            "priority": priority,
            "trend": trend,
            "status": existing.get("status", "New") if existing else "New",
            "ai_summary": cluster["ai_summary"],
            "localized_titles": cluster.get("localized_titles", {}),
            "localized_summaries": cluster.get("localized_summaries", {}),
            "strength": cluster.get("strength", 0.5),
            "academic_week": week,
            "last_detected": datetime.now(timezone.utc),
            "first_detected": existing.get("first_detected") if existing else datetime.now(timezone.utc),
        }
        await db["Issues"].update_one(
            {"issue_key": issue_key, "academic_week": week},
            {"$set": payload},
            upsert=True,
        )
    await db["Issues"].delete_many({"academic_week": week, "issue_key": {"$nin": list(seen_keys)}})


def _pick_localized(issue: dict[str, Any], lang: str) -> tuple[str, str]:
    lang = lang if lang in ai_service.PUBLIC_LANGS else "en"
    titles = issue.get("localized_titles") or {}
    summaries = issue.get("localized_summaries") or {}
    title = titles.get(lang) or issue.get("title", "")
    summary = summaries.get(lang) or issue.get("ai_summary") or issue.get("description", "")
    return str(title), str(summary)


async def get_public_weekly_issues(week: int, lang: str = "en") -> dict[str, Any]:
    db = get_database()
    issues = (
        await db["Issues"]
        .find({"academic_week": week})
        .sort([("frequency", -1), ("strength", -1)])
        .to_list(20)
    )
    limited = _limit_public_clusters(
        [
            {
                "frequency": i.get("frequency", 0),
                "strength": i.get("strength", 0.5),
                **i,
            }
            for i in issues
        ]
    )
    frequent = []
    for issue in limited:
        title, summary = _pick_localized(issue, lang)
        frequent.append({"title": title, "summary": summary})
    return {
        "academic_week": week,
        "most_frequent": frequent,
    }


async def list_issues(week: int | None = None) -> list[dict[str, Any]]:
    db = get_database()
    query: dict[str, Any] = {}
    if week is not None:
        query["academic_week"] = week
    docs = await db["Issues"].find(query).sort("frequency", -1).to_list(200)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


async def update_issue(issue_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    from bson import ObjectId

    db = get_database()
    await db["Issues"].update_one({"_id": ObjectId(issue_id)}, {"$set": updates})
    doc = await db["Issues"].find_one({"_id": ObjectId(issue_id)})
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
