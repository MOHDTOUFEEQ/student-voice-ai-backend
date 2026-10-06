from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services.academic_week_service import get_current_academic_week
from app.services.issue_service import sync_issues_for_week


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def create_submission(
    submission_type: str,
    message: str,
    category: str,
    importance: str,
) -> dict[str, Any]:
    """Store anonymous feedback in the Issues collection."""
    db = get_database()
    week = await get_current_academic_week()
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "type": submission_type,
        "message": message.strip(),
        "category": category,
        "importance": importance,
        "academic_week": week,
        "processing_status": "stored",
        "created_at": now,
    }
    result = await db["Issues"].insert_one(doc)
    doc["_id"] = result.inserted_id
    # New feedback should refresh the AI weekly themes on next public request.
    await sync_issues_for_week(week)
    return _serialize(doc)


async def list_admin(
    week: int | None = None,
    submission_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    db = get_database()
    query: dict[str, Any] = {}
    if week is not None:
        query["academic_week"] = week
    if submission_type:
        query["type"] = submission_type
    cursor = db["Issues"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    return [_serialize(d) for d in docs]


async def delete_submission(feedback_id: str) -> bool:
    db = get_database()
    result = await db["Issues"].delete_one({"_id": ObjectId(feedback_id)})
    return result.deleted_count > 0


async def update_submission_admin(feedback_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    db = get_database()
    allowed = {k: updates[k] for k in ("ai_category", "admin_priority_override", "category", "importance") if k in updates}
    if not allowed:
        doc = await db["Issues"].find_one({"_id": ObjectId(feedback_id)})
        return _serialize(doc) if doc else None
    await db["Issues"].update_one({"_id": ObjectId(feedback_id)}, {"$set": allowed})
    doc = await db["Issues"].find_one({"_id": ObjectId(feedback_id)})
    return _serialize(doc) if doc else None


async def count_by_week(week: int, submission_type: str | None = None) -> int:
    db = get_database()
    query: dict[str, Any] = {"academic_week": week}
    if submission_type:
        query["type"] = submission_type
    return await db["Issues"].count_documents(query)


async def retry_pending(limit: int = 20) -> int:
    del limit
    return 0
