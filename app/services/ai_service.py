"""Centralized OpenAI integration for feedback intelligence."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.constants import FEEDBACK_CATEGORIES, IMPORTANCE_LEVELS, SENTIMENTS, TRENDS

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"

SYSTEM_ANALYSIS = (
    "You analyze anonymous MSc student feedback in English. "
    "Never infer or mention who wrote feedback. "
    "Negative criticism is legitimate; only mark toxic for abuse, harassment, threats, or hate. "
    "Respond with valid JSON only."
)


def _client() -> OpenAI:
    settings = get_settings()
    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def _chat_json(system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
    settings = get_settings()
    try:
        response = _client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as exc:
        logger.exception("OpenAI call failed: %s", exc)
        raise


def classify_feedback(message: str, category: str, importance: str) -> dict[str, Any]:
    user = (
        f"Classify this anonymous submission.\n"
        f"Student category: {category}\nStudent importance: {importance}\n"
        f"Message: {message}\n\n"
        "Return JSON keys: ai_category (one of "
        + json.dumps(FEEDBACK_CATEGORIES)
        + "), sentiment (positive|neutral|negative), ai_priority (low|medium|high|critical), "
        "ai_themes (string array, max 5), is_spam (bool), is_toxic (bool), is_sensitive (bool), "
        "ai_flags (string array, e.g. safeguarding if sensitive)."
    )
    data = _chat_json(SYSTEM_ANALYSIS, user)
    return _normalize_classification(data)


def _normalize_classification(data: dict[str, Any]) -> dict[str, Any]:
    ai_category = data.get("ai_category") or "Other"
    if ai_category not in FEEDBACK_CATEGORIES:
        ai_category = "Other"
    sentiment = (data.get("sentiment") or "neutral").lower()
    if sentiment not in SENTIMENTS:
        sentiment = "neutral"
    ai_priority = (data.get("ai_priority") or "medium").lower()
    if ai_priority not in IMPORTANCE_LEVELS:
        ai_priority = "medium"
    themes = data.get("ai_themes") or []
    if not isinstance(themes, list):
        themes = []
    flags = data.get("ai_flags") or []
    if not isinstance(flags, list):
        flags = []
    return {
        "ai_category": ai_category,
        "sentiment": sentiment,
        "ai_priority": ai_priority,
        "ai_themes": [str(t) for t in themes[:5]],
        "is_spam": bool(data.get("is_spam")),
        "is_toxic": bool(data.get("is_toxic")),
        "is_sensitive": bool(data.get("is_sensitive")),
        "ai_flags": [str(f) for f in flags[:10]],
    }


def process_submission(message: str, category: str, importance: str) -> dict[str, Any]:
    """Full pipeline for a new submission."""
    return classify_feedback(message, category, importance)


def detect_sentiment(message: str) -> str:
    data = classify_feedback(message, "Other", "medium")
    return data["sentiment"]


def detect_themes(message: str) -> list[str]:
    data = classify_feedback(message, "Other", "medium")
    return data["ai_themes"]


def detect_toxicity(message: str) -> bool:
    data = classify_feedback(message, "Other", "medium")
    return data["is_toxic"]


def detect_spam(message: str) -> bool:
    data = classify_feedback(message, "Other", "medium")
    return data["is_spam"]


def detect_sensitive_content(message: str) -> bool:
    data = classify_feedback(message, "Other", "medium")
    return data["is_sensitive"]


def summarize_feedback(messages: list[str]) -> str:
    if not messages:
        return "No feedback available for summarization."
    sample = "\n---\n".join(messages[:40])
    user = f"Summarize themes in these anonymous submissions (aggregated, no quotes that identify individuals):\n{sample}"
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=400)
    return data.get("summary") or data.get("text") or str(data)


def detect_duplicates(new_message: str, existing_snippets: list[str]) -> list[int]:
    if not existing_snippets:
        return []
    numbered = "\n".join(f"{i}: {s[:200]}" for i, s in enumerate(existing_snippets[:30]))
    user = (
        f"New message: {new_message}\n\nExisting messages (indexed):\n{numbered}\n\n"
        "Return JSON: duplicate_indices (int array of indices describing the same underlying issue)."
    )
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=200)
    indices = data.get("duplicate_indices") or []
    return [int(i) for i in indices if isinstance(i, (int, float))]


def detect_recurring_issues(issue_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user = "Given weekly issue counts JSON, identify recurring issues:\n" + json.dumps(issue_history)
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=600)
    return data.get("recurring_issues") or []


def detect_trends(weekly_counts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user = (
        "For each issue title with counts per week, assign trend: "
        + json.dumps(TRENDS)
        + f". Input: {json.dumps(weekly_counts)}"
    )
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=600)
    return data.get("trends") or []


def calculate_priority(
    frequency: int,
    importance_scores: list[str],
    recurrence_weeks: int,
    sentiment: str,
) -> str:
    score = frequency * 2 + recurrence_weeks * 3
    if sentiment == "negative":
        score += 2
    for imp in importance_scores:
        if imp == "critical":
            score += 4
        elif imp == "high":
            score += 3
        elif imp == "medium":
            score += 1
    if score >= 12:
        return "critical"
    if score >= 8:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


def generate_action_recommendations(context: str) -> list[str]:
    user = (
        "Based on aggregated anonymous feedback context, suggest 3 actionable steps for the MSc rep. "
        "Label each as practical and neutral.\nContext:\n"
        + context
    )
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=500)
    actions = data.get("actions") or data.get("recommendations") or []
    if isinstance(actions, list):
        return [str(a) for a in actions[:5]]
    return [str(actions)]


def generate_weekly_summary(week: int, stats: dict[str, Any]) -> dict[str, Any]:
    user = f"Generate a weekly summary JSON for academic week {week}. Stats:\n{json.dumps(stats)}"
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=900)
    data["academic_week"] = week
    data["prompt_version"] = PROMPT_VERSION
    return data


def generate_meeting_agenda(week: int, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user = f"Week {week} agenda from issues:\n{json.dumps(issues)}"
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=800)
    return data.get("agenda_items") or []


def generate_teacher_summary(issue_title: str, evidence: str) -> dict[str, Any]:
    user = (
        f"Issue: {issue_title}\nEvidence (aggregated):\n{evidence}\n"
        "Return JSON: student_concern, evidence, suggested_discussion (professional neutral tone)."
    )
    return _chat_json(SYSTEM_ANALYSIS, user, max_tokens=500)


def generate_report(report_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    user = f"Generate {report_type} report JSON from:\n{json.dumps(payload)}"
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=1200)
    data["report_type"] = report_type
    data["ai_generated"] = True
    return data


def answer_admin_question(question: str, context: dict[str, Any]) -> str:
    user = f"Question: {question}\n\nApplication data (aggregated only):\n{json.dumps(context)}"
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=700)
    return data.get("answer") or data.get("response") or json.dumps(data)


def suggest_feedback_example(category: str | None = None) -> str:
    cat = category or "Student Experience"
    user = (
        f"Generate one realistic anonymous MSc student feedback example about {cat}. "
        "Write in English. Plain text only, 1-3 sentences, no names or identifying details. Return JSON: message"
    )
    data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=150)
    return data.get("message") or "The balance between lectures and independent study could be clearer this week."


def summarize_weekly_feedback_themes(submissions: list[dict[str, Any]], max_points: int = 5) -> list[dict[str, Any]]:
    """
    Use AI to consolidate anonymous feedback into a small set of specific main points.
    Each point should clearly state what students are actually trying to say.
    """
    if not submissions:
        return []

    payload = [
        {
            "message": str(s.get("message") or "")[:500],
            "category": s.get("category") or "Other",
            "importance": s.get("importance") or "medium",
        }
        for s in submissions[:80]
        if str(s.get("message") or "").strip()
    ]
    if not payload:
        return []

    user = (
        f"You are summarizing anonymous MSc student feedback for a public weekly issues page.\n"
        f"Read the submissions carefully and consolidate them into at most {max_points} main points.\n\n"
        "Rules:\n"
        "- Each point must capture a specific issue or common theme students are actually raising.\n"
        "- Merge similar feedback into one point (e.g. printer availability + more printers needed → Printing Facilities).\n"
        "- Prefer fewer strong points over many weak ones. Use fewer than "
        f"{max_points} if there are not that many distinct themes.\n"
        "- Do NOT invent issues that are not supported by the submissions.\n"
        "- Do NOT quote individual students or include identifying details.\n"
        "- Titles should be short and specific (e.g. 'Printing Facilities', not just 'Facilities').\n"
        "- Summaries should clearly rephrase what students are trying to say in 1–2 sentences.\n\n"
        "Return JSON with key 'points' (array). Each item:\n"
        "  title (string), summary (string), frequency (int estimate of how many submissions relate).\n\n"
        f"Submissions:\n{json.dumps(payload)}"
    )
    try:
        data = _chat_json(SYSTEM_ANALYSIS, user, max_tokens=1200)
        points = data.get("points") or data.get("clusters") or []
        normalized: list[dict[str, Any]] = []
        for raw in points:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            summary = str(raw.get("summary") or "").strip()
            if not title or not summary:
                continue
            normalized.append(
                {
                    "title": title[:120],
                    "summary": summary[:500],
                    "frequency": int(raw.get("frequency") or 1),
                }
            )
        return normalized[:max_points]
    except Exception:
        logger.exception("Weekly theme summarization failed, using fallback")
        return _fallback_clusters(submissions)[:max_points]


def cluster_weekly_issues(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backward-compatible wrapper — prefer summarize_weekly_feedback_themes."""
    points = summarize_weekly_feedback_themes(submissions, max_points=5)
    return [
        {
            "issue_key": p["title"].lower().replace(" ", "-")[:40],
            "frequency": p.get("frequency", 1),
            "strength": 0.5,
            "title": p["title"],
            "ai_summary": p["summary"],
        }
        for p in points
    ]


def _fallback_clusters(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for s in submissions:
        key = s.get("category") or (s.get("ai_themes") or ["general"])[0]
        buckets.setdefault(str(key), []).append(s)
    clusters = []
    for key, items in sorted(buckets.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        title = str(key).replace("_", " ").title()
        # Prefer a short rephrasing from the first message when AI is unavailable.
        sample = str(items[0].get("message") or "").strip()
        if sample:
            summary = sample if len(sample) <= 180 else sample[:177].rstrip() + "..."
        else:
            summary = f"Students have raised concerns related to {title.lower()}."
        clusters.append(
            {
                "title": title,
                "summary": summary,
                "frequency": len(items),
                "issue_key": key,
                "strength": min(1.0, len(items) / 3),
                "ai_summary": summary,
            }
        )
    return clusters
