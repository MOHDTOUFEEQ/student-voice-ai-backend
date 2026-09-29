from app.auth.security import hash_password, verify_password
from app.config import get_settings
from app.database import get_database


async def ensure_admin_user() -> None:
    db = get_database()
    settings = get_settings()
    existing = await db["AdminUsers"].find_one({"username": settings.admin_username})
    if existing:
        return
    if not settings.admin_password:
        return
    await db["AdminUsers"].insert_one(
        {
            "username": settings.admin_username,
            "password_hash": hash_password(settings.admin_password),
            "display_name": "Toufeeq Mohammed",
            "role": "MSc Representative",
        }
    )


async def authenticate(username: str, password: str) -> dict | None:
    db = get_database()
    user = await db["AdminUsers"].find_one({"username": username})
    if not user:
        settings = get_settings()
        if username == settings.admin_username and settings.admin_password and password == settings.admin_password:
            await ensure_admin_user()
            user = await db["AdminUsers"].find_one({"username": username})
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {
        "username": user["username"],
        "display_name": user.get("display_name", "Toufeeq Mohammed"),
        "role": user.get("role", "MSc Representative"),
    }
