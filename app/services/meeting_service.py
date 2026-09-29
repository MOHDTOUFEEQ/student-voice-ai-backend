from datetime import date, datetime, timezone
from typing import Any

from bson import ObjectId

from app.database import get_database


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    doc["id"] = str(doc.pop("_id"))
    if isinstance(doc.get("meeting_date"), datetime):
        doc["meeting_date"] = doc["meeting_date"].date().isoformat()
    elif isinstance(doc.get("meeting_date"), date):
        doc["meeting_date"] = doc["meeting_date"].isoformat()
    return doc


async def list_public(week: int | None = None) -> list[dict[str, Any]]:
    db = get_database()
    query: dict[str, Any] = {"published": True}
    if week is not None:
        query["academic_week"] = week
    docs = await db["MeetingUpdates"].find(query).sort("academic_week", -1).to_list(100)
    return [_serialize(d) for d in docs]


async def list_admin() -> list[dict[str, Any]]:
    db = get_database()
    docs = await db["MeetingUpdates"].find({}).sort("created_at", -1).to_list(200)
    return [_serialize(d) for d in docs]


async def create(data: dict[str, Any]) -> dict[str, Any]:
    db = get_database()
    doc = {**data, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
    result = await db["MeetingUpdates"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def update(meeting_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    db = get_database()
    data["updated_at"] = datetime.now(timezone.utc)
    await db["MeetingUpdates"].update_one({"_id": ObjectId(meeting_id)}, {"$set": data})
    doc = await db["MeetingUpdates"].find_one({"_id": ObjectId(meeting_id)})
    return _serialize(doc) if doc else None
