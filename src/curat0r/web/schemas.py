"""Request and response models. Same discipline as Fantasy_Blackjack:
response models document the API and drop anything not declared."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Imported at runtime, not under TYPE_CHECKING: this module uses postponed
# annotations, and Pydantic resolves them at model-build time.
from curat0r.types import Block


class SourceOut(BaseModel):
    key: str
    label: str
    method: str
    auto_fetchable: bool
    guidance: str


class IngestRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)


class DraftOut(BaseModel):
    id: str
    kind: str
    title: str
    dates: str = ""
    tags: list[str] = []
    bullets: list[str] = []
    verified: bool = False


class CurateRequest(BaseModel):
    blocks: list[Block] = Field(min_length=1)
    posting: str = Field(min_length=20, max_length=50_000)
    budget: int = Field(default=30, ge=8, le=80)


class GapPromptOut(BaseModel):
    requirement: str
    kind: str
    question: str
    recoverable: bool
    near: str | None = None


class CurateResponse(BaseModel):
    resume: str
    score: float
    shown: list[str]
    missed: list[str]
    gaps: list[str]
    prompts: list[GapPromptOut]
    lines_used: int
    budget: int


class AnswerIn(BaseModel):
    requirement: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=10, max_length=2000)
    tags: list[str] = []


class CloseGapsRequest(BaseModel):
    blocks: list[Block]
    posting: str
    answers: list[AnswerIn]
    budget: int = Field(default=30, ge=8, le=80)


class TwoDocumentsOut(BaseModel):
    supported_now: CurateResponse
    after_answers: CurateResponse
    closed: int
    still_open: list[str]
    note: str


class ErrorOut(BaseModel):
    error: str
    detail: str
