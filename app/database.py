from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.database_name]


async def close_database() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def ensure_indexes() -> None:
    db = get_database()
    feedback = db["Feedback"]
    await feedback.create_index("academic_week")
    await feedback.create_index("category")
    await feedback.create_index("created_at")
    await feedback.create_index("type")
    await feedback.create_index("ai_priority")
    await feedback.create_index("processing_status")
    await feedback.create_index([("academic_week", 1), ("type", 1)])

    issues = db["Issues"]
    await issues.create_index("academic_week")
    await issues.create_index("status")
    await issues.create_index("title")
    await issues.create_index("issue_key")
    await issues.create_index([("academic_week", 1), ("issue_key", 1)])

    meeting = db["MeetingUpdates"]
    await meeting.create_index([("academic_week", 1), ("published", 1)])

    audit = db["AuditLogs"]
    await audit.create_index("created_at")
