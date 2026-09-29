from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    current_academic_week: int | None = None
    week_3_start_date: str | None = None
    total_academic_weeks: int | None = None
    data_retention_days: int | None = None
    data_retention_mode: str | None = None


class MeetingUpdateCreate(BaseModel):
    academic_week: int
    meeting_date: date | None = None
    issue: str
    summary: str
    decision: str | None = None
    action: str | None = None
    status: str = "Discussed"
    published: bool = False


class MeetingUpdatePatch(BaseModel):
    academic_week: int | None = None
    meeting_date: date | None = None
    issue: str | None = None
    summary: str | None = None
    decision: str | None = None
    action: str | None = None
    status: str | None = None
    published: bool | None = None


class IssueUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    admin_priority_override: str | None = None
    trend: str | None = None
    status: str | None = None
    admin_notes: str | None = None
    recommended_action: str | None = None


class AIQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class ReportRequest(BaseModel):
    academic_week: int | None = None


class AgendaRequest(BaseModel):
    academic_week: int | None = None


class TeacherSummaryRequest(BaseModel):
    issue_title: str
    academic_week: int | None = None


class ClassReportRequest(BaseModel):
    start_week: int = 1
    end_week: int | None = None


class AuditLogItem(BaseModel):
    action: str
    details: dict[str, Any] = {}
    created_at: datetime
