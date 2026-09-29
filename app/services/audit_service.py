from datetime import datetime, timezone
from typing import Any

from app.database import get_database


async def log_action(action: str, details: dict[str, Any] | None = None, admin_username: str | None = None) -> None:
    db = get_database()
    await db["AuditLogs"].insert_one(
        {
            "action": action,
            "admin_username": admin_username,
            "details": details or {},
            "created_at": datetime.now(timezone.utc),
        }
    )
