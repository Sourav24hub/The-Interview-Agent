"""
Pydantic models for the /api/interview endpoint.

These mirror the exact request/response shapes defined in technical-spec.md.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Candidate sub-models  (mirrors candidate.json schema)
# ---------------------------------------------------------------------------

class CandidateMember(BaseModel):
    id: str
    name: str
    jobRole: str
    yearsExperience: int
    education: str
    status: str


class Mission(BaseModel):
    day: int
    title: str
    passed: Optional[bool] = None
    skipped: Optional[bool] = None
    attempts: Optional[int] = None


class Signals(BaseModel):
    commitDays: int
    missionsCompleted: int
    missionsFirstTry: int


class Candidate(BaseModel):
    member: CandidateMember
    missions: List[Mission]
    signals: Signals


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class InterviewRequest(BaseModel):
    """
    Unified request body for POST /api/interview.

    - On the FIRST call: sessionId + candidate must both be present.
    - On subsequent CONVERSATION TURNS: sessionId + message must be present.
    - candidate and message are both optional at the schema level so a single
      model covers all cases; validation logic lives in the route handler.
    """
    sessionId: str = Field(..., description="Unique identifier for the interview session")
    candidate: Optional[Candidate] = Field(
        None,
        description="Full candidate object (required only on the first/start request)"
    )
    message: Optional[str] = Field(
        None,
        description="Candidate's latest message (required on conversation turns)"
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class FeedbackPayload(BaseModel):
    """Structured feedback included in the terminal response (done=True)."""
    summary: str
    strengths: List[str]
    gaps: List[str]
    next: List[str]


class InterviewResponse(BaseModel):
    """
    Unified response body for POST /api/interview.

    - done=False  → ongoing interview turn
    - done=True   → interview complete; feedback is populated
    """
    reply: str
    done: bool
    feedback: Optional[FeedbackPayload] = None
