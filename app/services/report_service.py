import csv
import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services import ai_service
from app.services.analytics_service import full_analytics, overview_stats
from app.services.weekly_service import get_or_generate_weekly_insights
from app.services.academic_week_service import get_calendar_settings


async def build_weekly_report(week: int) -> dict[str, Any]:
    insights = await get_or_generate_weekly_insights(week)
    stats = await overview_stats()
    payload = {"week": week, "insights": insights, "stats": stats}
    try:
        report = ai_service.generate_report("Weekly", payload)
    except Exception:
        report = {
            "summary": f"Week {week} report",
            "themes": insights.get("top_themes", []),
            "priority_issues": insights.get("priority_issues", []),
            "ai_generated": True,
        }
    report["week"] = week
    return report


async def build_academic_report() -> dict[str, Any]:
    calendar = await get_calendar_settings()
    analytics = await full_analytics()
    payload = {"calendar": calendar, "analytics": analytics}
    try:
        return ai_service.generate_report("Academic Period", payload)
    except Exception:
        return {"summary": "Academic period report", "analytics": analytics, "ai_generated": True}


def report_to_csv(report: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "key", "value"])
    for key, value in report.items():
        if isinstance(value, (list, dict)):
            writer.writerow(["report", key, str(value)[:500]])
        else:
            writer.writerow(["report", key, value])
    return output.getvalue()


def report_to_pdf(report: dict[str, Any], title: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for key, value in report.items():
        if y < 60:
            c.showPage()
            y = height - 50
        line = f"{key}: {str(value)[:120]}"
        c.drawString(50, y, line)
        y -= 14
    c.save()
    buffer.seek(0)
    return buffer.read()
