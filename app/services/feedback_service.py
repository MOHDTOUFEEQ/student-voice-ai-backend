from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services import ai_service
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
    db = get_database()
    week = await get_current_academic_week()
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "type": submission_type,
        "message": message.strip(),
        "category": category,
        "importance": importance,
        "academic_week": week,
        "sentiment": None,
        "ai_category": None,
        "ai_priority": None,
        "ai_themes": [],
        "ai_flags": [],
        "is_spam": False,
        "is_toxic": False,
        "is_sensitive": False,
        "processing_status": "pending",
        "created_at": now,
    }
    result = await db["Feedback"].insert_one(doc)
    doc["_id"] = result.inserted_id
    await _process_submission_async(str(result.inserted_id))
    refreshed = await db["Feedback"].find_one({"_id": result.inserted_id})
    return _serialize(refreshed or doc)


async def _process_submission_async(feedback_id: str) -> None:
    db = get_database()
    oid = ObjectId(feedback_id)
    doc = await db["Feedback"].find_one({"_id": oid})
    if not doc:
        return
    try:
        analysis = ai_service.process_submission(
            doc["message"], doc["category"], doc["importance"]
        )
        week = doc["academic_week"]
        recent = (
            await db["Feedback"]
            .find(
                {
                    "academic_week": week,
                    "type": doc["type"],
                    "_id": {"$ne": oid},
                    "processing_status": "processed",
                }
            )
            .sort("created_at", -1)
            .limit(30)
            .to_list(30)
        )
        dup_indices = ai_service.detect_duplicates(
            doc["message"], [r["message"] for r in recent]
        )
        duplicate_of = [str(recent[i]["_id"]) for i in dup_indices if i < len(recent)]

        update = {
            **analysis,
            "processing_status": "processed",
            "duplicate_group_ids": duplicate_of,
        }
        if doc["type"] == "feedback":
            update["sentiment"] = analysis.get("sentiment")
        await db["Feedback"].update_one({"_id": oid}, {"$set": update})
        await sync_issues_for_week(week)
    except Exception:
        await db["Feedback"].update_one(
            {"_id": oid},
            {"$set": {"processing_status": "pending"}},
        )


async def retry_pending(limit: int = 20) -> int:
    db = get_database()
    pending = (
        await db["Feedback"]
        .find({"processing_status": "pending"})
        .sort("created_at", 1)
        .limit(limit)
        .to_list(limit)
    )
    for doc in pending:
        await _process_submission_async(str(doc["_id"]))
    return len(pending)


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
    cursor = db["Feedback"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    return [_serialize(d) for d in docs]


async def delete_submission(feedback_id: str) -> bool:
    db = get_database()
    result = await db["Feedback"].delete_one({"_id": ObjectId(feedback_id)})
    return result.deleted_count > 0


async def update_submission_admin(feedback_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    db = get_database()
    allowed = {k: updates[k] for k in ("ai_category", "admin_priority_override") if k in updates}
    if not allowed:
        doc = await db["Feedback"].find_one({"_id": ObjectId(feedback_id)})
        return _serialize(doc) if doc else None
    await db["Feedback"].update_one({"_id": ObjectId(feedback_id)}, {"$set": allowed})
    doc = await db["Feedback"].find_one({"_id": ObjectId(feedback_id)})
    return _serialize(doc) if doc else None


async def count_by_week(week: int, submission_type: str | None = None) -> int:
    db = get_database()
    query: dict[str, Any] = {"academic_week": week}
    if submission_type:
        query["type"] = submission_type
    return await db["Feedback"].count_documents(query)
