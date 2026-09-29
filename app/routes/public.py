from fastapi import APIRouter, HTTPException

from app.constants import FEEDBACK_CATEGORIES
from app.schemas.feedback import AISuggestFeedbackRequest
from app.services import ai_service
from app.services.academic_week_service import get_calendar_settings, get_current_academic_week, get_week_start_date
from app.services.issue_service import get_public_weekly_issues
from app.services.meeting_service import list_public

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/current-week")
async def current_week():
    week = await get_current_academic_week()
    calendar = await get_calendar_settings()
    start = get_week_start_date(week, calendar)
    return {
        "academic_week": week,
        "label": f"Week {week}",
        "week_start_date": start.isoformat() if start else None,
        "total_weeks": calendar["total_academic_weeks"],
    }


@router.get("/categories")
async def categories():
    return {"categories": FEEDBACK_CATEGORIES}


@router.get("/weekly/issues")
async def weekly_issues(week: int | None = None, lang: str = "en"):
    w = week or await get_current_academic_week()
    return await get_public_weekly_issues(w, lang=lang)


@router.get("/weekly/updates")
async def weekly_updates(week: int | None = None):
    w = week or await get_current_academic_week()
    updates = await list_public(w)
    return {"academic_week": w, "updates": updates}


@router.post("/ai/suggest-feedback")
async def suggest_feedback(payload: AISuggestFeedbackRequest, lang: str = "en"):
    try:
        message = ai_service.suggest_feedback_example(payload.category, language=lang)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AI suggestion temporarily unavailable") from exc
    return {"message": message}
