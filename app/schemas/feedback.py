from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.constants import FEEDBACK_CATEGORIES, IMPORTANCE_LEVELS


class FeedbackCreate(BaseModel):
    message: str = Field(..., min_length=10, max_length=5000)
    category: str
    importance: Literal["low", "medium", "high", "critical"]

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in FEEDBACK_CATEGORIES:
            raise ValueError("Invalid category")
        return v

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: str) -> str:
        if v not in IMPORTANCE_LEVELS:
            raise ValueError("Invalid importance")
        return v


class SuggestionCreate(BaseModel):
    message: str = Field(..., min_length=10, max_length=5000)
    category: str
    importance: Literal["low", "medium", "high", "critical"] = "medium"

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in FEEDBACK_CATEGORIES:
            raise ValueError("Invalid category")
        return v


class FeedbackPublicResponse(BaseModel):
    id: str
    message: str
    success: bool = True


class FeedbackAdminItem(BaseModel):
    id: str
    type: str
    message: str
    category: str
    importance: str
    academic_week: int
    sentiment: str | None = None
    ai_category: str | None = None
    ai_priority: str | None = None
    ai_themes: list[str] = []
    ai_flags: list[str] = []
    is_spam: bool = False
    is_toxic: bool = False
    is_sensitive: bool = False
    processing_status: str
    created_at: datetime
    admin_priority_override: str | None = None


class FeedbackCategoryUpdate(BaseModel):
    ai_category: str | None = None
    admin_priority_override: str | None = None


class AISuggestFeedbackRequest(BaseModel):
    category: str | None = None
