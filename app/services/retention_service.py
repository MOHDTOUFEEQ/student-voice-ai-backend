from datetime import datetime, timedelta, timezone

from app.database import get_database
from app.services.settings_service import get_retention_settings


async def purge_expired_feedback() -> int:
    settings = await get_retention_settings()
    mode = str(settings.get("mode", "90"))
    days = int(settings.get("custom_days", 90))
    if mode.isdigit():
        days = int(mode)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = get_database()
    result = await db["Issues"].delete_many({"created_at": {"$lt": cutoff}})
    return int(result.deleted_count)
