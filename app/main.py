import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.utils.rate_limit import limiter
from app.database import close_database, ensure_indexes
from app.routes import admin, public, submissions
from app.services.admin_user_service import ensure_admin_user

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Student Voice API", version="1.0.0")
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [settings.frontend_url, "https://www.studentvoice.uk",
    "https://studentvoice.uk","http://localhost:5173", "http://127.0.0.1:5173"]
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys(origins)),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    async def startup() -> None:
        await ensure_indexes()
        await ensure_admin_user()

    @application.on_event("shutdown")
    async def shutdown() -> None:
        await close_database()

    @application.get("/api/health")
    async def health():
        return {"status": "ok"}

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        del request
        logger.exception("Unhandled error: %s", exc)
        if settings.environment == "development":
            return JSONResponse(status_code=500, content={"detail": str(exc)})
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})

    application.include_router(submissions.router)
    application.include_router(public.router)
    application.include_router(admin.router)
    return application


app = create_app()
