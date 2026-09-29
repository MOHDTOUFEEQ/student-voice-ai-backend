from typing import Any

from app.database import get_database


async def get_retention_settings() -> dict[str, Any]:
    db = get_database()
    doc = await db["Settings"].find_one({"key": "data_retention"})
    if doc and "value" in doc:
        return doc["value"]
    return {"mode": "90", "custom_days": 90}


async def update_retention_settings(mode: str, custom_days: int | None = None) -> dict[str, Any]:
    db = get_database()
    value = {"mode": mode, "custom_days": custom_days or int(mode) if mode.isdigit() else 90}
    await db["Settings"].update_one(
        {"key": "data_retention"},
        {"$set": {"key": "data_retention", "value": value}},
        upsert=True,
    )
    return value
