from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_admin
from app.schemas.admin import (
    AgendaRequest,
    AIQueryRequest,
    ClassReportRequest,
    IssueUpdate,
    MeetingUpdateCreate,
    MeetingUpdatePatch,
    ReportRequest,
    SettingsUpdate,
    TeacherSummaryRequest,
)
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.feedback import FeedbackCategoryUpdate
from app.auth.security import create_access_token
from app.services import ai_service
from app.services.academic_week_service import get_calendar_settings, update_calendar_settings
from app.services.admin_user_service import authenticate
from app.services.analytics_service import (
    build_admin_ai_context,
    full_analytics,
    overview_stats,
    suggestions_by_theme,
)
from app.services.audit_service import log_action
from app.services.feedback_service import delete_submission, list_admin, update_submission_admin
from app.services.issue_service import list_issues, update_issue
from app.services.meeting_service import create as create_meeting, list_admin as list_meetings_admin, update as update_meeting
from app.services.report_service import build_academic_report, build_weekly_report, report_to_csv, report_to_pdf
from app.services.retention_service import purge_expired_feedback
from app.services.settings_service import get_retention_settings, update_retention_settings
from app.services.weekly_service import get_or_generate_weekly_insights
from app.database import get_database

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    user = await authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["username"])
    await log_action("admin_login", {"username": user["username"]}, user["username"])
    return LoginResponse(
        access_token=token,
        display_name=user["display_name"],
        role=user["role"],
    )


@router.post("/logout")
async def logout(admin: str = Depends(get_current_admin)):
    await log_action("admin_logout", {}, admin)
    return {"success": True}


@router.get("/overview")
async def overview(admin: str = Depends(get_current_admin)):
    del admin
    return await overview_stats()


@router.get("/feedback")
async def feedback_list(week: int | None = None, type: str | None = None, admin: str = Depends(get_current_admin)):
    del admin
    return {"items": await list_admin(week=week, submission_type=type)}


@router.delete("/feedback/{feedback_id}")
async def feedback_delete(feedback_id: str, admin: str = Depends(get_current_admin)):
    ok = await delete_submission(feedback_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    await log_action("feedback_deleted", {"feedback_id": feedback_id}, admin)
    return {"success": True}


@router.patch("/feedback/{feedback_id}")
async def feedback_patch(feedback_id: str, payload: FeedbackCategoryUpdate, admin: str = Depends(get_current_admin)):
    doc = await update_submission_admin(feedback_id, payload.model_dump(exclude_none=True))
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    await log_action("feedback_updated", {"feedback_id": feedback_id}, admin)
    return doc


@router.get("/analytics")
async def analytics(admin: str = Depends(get_current_admin)):
    del admin
    return await full_analytics()


@router.get("/weekly")
async def weekly_insights(week: int, admin: str = Depends(get_current_admin)):
    del admin
    return await get_or_generate_weekly_insights(week)


@router.get("/issues")
async def issues(week: int | None = None, admin: str = Depends(get_current_admin)):
    del admin
    return {"items": await list_issues(week)}


@router.patch("/issues/{issue_id}")
async def issue_patch(issue_id: str, payload: IssueUpdate, admin: str = Depends(get_current_admin)):
    doc = await update_issue(issue_id, payload.model_dump(exclude_none=True))
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    await log_action("issue_updated", {"issue_id": issue_id}, admin)
    return doc


@router.get("/suggestions/themes")
async def suggestion_themes(admin: str = Depends(get_current_admin)):
    del admin
    return {"items": await suggestions_by_theme()}


@router.get("/meeting-updates")
async def meeting_updates_admin(admin: str = Depends(get_current_admin)):
    del admin
    return {"items": await list_meetings_admin()}


@router.post("/meeting-updates")
async def meeting_create(payload: MeetingUpdateCreate, admin: str = Depends(get_current_admin)):
    doc = await create_meeting(payload.model_dump())
    await log_action("meeting_update_created", {"id": doc["id"]}, admin)
    return doc


@router.put("/meeting-updates/{meeting_id}")
async def meeting_update(meeting_id: str, payload: MeetingUpdatePatch, admin: str = Depends(get_current_admin)):
    doc = await update_meeting(meeting_id, payload.model_dump(exclude_none=True))
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.published is True:
        await log_action("meeting_update_published", {"id": meeting_id}, admin)
    return doc


@router.post("/ai/query")
async def ai_query(payload: AIQueryRequest, admin: str = Depends(get_current_admin)):
    ctx = await build_admin_ai_context()
    try:
        answer = ai_service.answer_admin_question(payload.question, ctx)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AI assistant unavailable") from exc
    await log_action("ai_query", {"question": payload.question[:200]}, admin)
    return {"answer": answer, "disclaimer": "AI-generated from aggregated data only."}


@router.post("/reports/weekly")
async def report_weekly(payload: ReportRequest, admin: str = Depends(get_current_admin)):
    from app.services.academic_week_service import get_current_academic_week

    week = payload.academic_week or await get_current_academic_week()
    report = await build_weekly_report(week)
    await log_action("report_weekly", {"week": week}, admin)
    return report


@router.post("/reports/academic")
async def report_academic(admin: str = Depends(get_current_admin)):
    report = await build_academic_report()
    await log_action("report_academic", {}, admin)
    return report


@router.get("/reports/weekly/export")
async def export_weekly_pdf(week: int, format: str = "pdf", admin: str = Depends(get_current_admin)):
    report = await build_weekly_report(week)
    await log_action("report_export", {"week": week, "format": format}, admin)
    if format == "csv":
        return Response(content=report_to_csv(report), media_type="text/csv")
    pdf = report_to_pdf(report, f"Week {week} Report")
    return StreamingResponse(iter([pdf]), media_type="application/pdf")


@router.post("/agenda")
async def agenda(payload: AgendaRequest, admin: str = Depends(get_current_admin)):
    from app.services.academic_week_service import get_current_academic_week

    week = payload.academic_week or await get_current_academic_week()
    issues = await list_issues(week)
    items = ai_service.generate_meeting_agenda(week, issues[:8])
    return {"week": week, "agenda_items": items}


@router.post("/teacher-summary")
async def teacher_summary(payload: TeacherSummaryRequest, admin: str = Depends(get_current_admin)):
    from app.services.academic_week_service import get_current_academic_week

    week = payload.academic_week or await get_current_academic_week()
    issues = await list_issues(week)
    match = next((i for i in issues if i.get("title") == payload.issue_title), None)
    evidence = match.get("ai_summary", "") if match else "Aggregated student submissions."
    summary = ai_service.generate_teacher_summary(payload.issue_title, evidence)
    return summary


@router.post("/class-report")
async def class_report(payload: ClassReportRequest, admin: str = Depends(get_current_admin)):
    report = await build_academic_report()
    return report


@router.get("/settings")
async def get_settings_api(admin: str = Depends(get_current_admin)):
    del admin
    calendar = await get_calendar_settings()
    retention = await get_retention_settings()
    return {"academic_calendar": calendar, "data_retention": retention}


@router.put("/settings")
async def put_settings(payload: SettingsUpdate, admin: str = Depends(get_current_admin)):
    cal_updates = {}
    if payload.current_academic_week is not None:
        cal_updates["current_academic_week"] = payload.current_academic_week
    if payload.week_3_start_date is not None:
        cal_updates["week_3_start_date"] = payload.week_3_start_date
    if payload.total_academic_weeks is not None:
        cal_updates["total_academic_weeks"] = payload.total_academic_weeks
    calendar = await update_calendar_settings(cal_updates) if cal_updates else await get_calendar_settings()
    retention = await get_retention_settings()
    if payload.data_retention_mode:
        retention = await update_retention_settings(
            payload.data_retention_mode, payload.data_retention_days
        )
    elif payload.data_retention_days is not None:
        retention = await update_retention_settings("custom", payload.data_retention_days)
    await log_action("settings_updated", {"calendar": calendar, "retention": retention}, admin)
    return {"academic_calendar": calendar, "data_retention": retention}


@router.get("/audit-logs")
async def audit_logs(admin: str = Depends(get_current_admin)):
    del admin
    db = get_database()
    docs = await db["AuditLogs"].find({}).sort("created_at", -1).limit(100).to_list(100)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return {"items": docs}


@router.post("/maintenance/purge-retention")
async def maintenance_purge(admin: str = Depends(get_current_admin)):
    deleted = await purge_expired_feedback()
    await log_action("retention_purge", {"deleted": deleted}, admin)
    return {"deleted": deleted}
