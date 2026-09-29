from fastapi import APIRouter, Request

from app.config import get_settings
from app.schemas.feedback import FeedbackCreate, SuggestionCreate
from app.services.feedback_service import create_submission
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/api", tags=["submissions"])


@router.post("/feedback")
@limiter.limit(lambda: get_settings().rate_limit_feedback)
async def submit_feedback(request: Request, payload: FeedbackCreate):
    del request
    doc = await create_submission("feedback", payload.message, payload.category, payload.importance)
    return {"id": doc["id"], "success": True, "processing_status": doc.get("processing_status")}


@router.post("/suggestions")
@limiter.limit(lambda: get_settings().rate_limit_feedback)
async def submit_suggestion(request: Request, payload: SuggestionCreate):
    del request
    doc = await create_submission("suggestion", payload.message, payload.category, payload.importance)
    return {"id": doc["id"], "success": True, "processing_status": doc.get("processing_status")}
