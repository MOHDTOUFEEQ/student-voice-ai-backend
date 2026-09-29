from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CALENDAR = {
    "current_academic_week": 2,
    "week_3_start_date": "2026-10-05",
    "total_academic_weeks": 11,
}


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_admin_requires_auth():
    res = client.get("/api/admin/overview")
    assert res.status_code == 401


def test_public_current_week():
    with (
        patch("app.routes.public.get_current_academic_week", AsyncMock(return_value=2)),
        patch("app.routes.public.get_calendar_settings", AsyncMock(return_value=CALENDAR)),
        patch("app.routes.public.get_week_start_date", return_value=date(2026, 9, 28)),
    ):
        res = client.get("/api/public/current-week")
    assert res.status_code == 200
    body = res.json()
    assert body["academic_week"] == 2
