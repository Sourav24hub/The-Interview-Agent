"""
AI Interview Agent — FastAPI Backend
=====================================
Single endpoint: POST /api/interview

Flow (mirrors technical-spec.md):
  1. Start  → { sessionId, candidate }   → { reply, done: false }
  2. Turn   → { sessionId, message }     → { reply, done: false }
  3. End    → last turn                  → { reply, done: true, feedback: {...} }
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from models import InterviewRequest, InterviewResponse, MockAnswerRequest
from session_store import (
    create_session,
    get_session,
    get_current_question,
    append_history,
    mark_done,
)
from question_generator import generate_question_plan
from interview_engine import (
    build_welcome,
    process_turn,
    build_feedback,
    MOCK_MODE,
)
from groq_service import generate_candidate_mock_answer


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("interview_agent")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = "MOCK" if MOCK_MODE else "LIVE"
    log.info("AI Interview Agent starting up — mode: %s", mode)
    yield
    log.info("AI Interview Agent shutting down.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Interview Agent",
    description=(
        "FastAPI backend for the ABTalks hackathon AI Interview Agent. "
        "Exposes POST /api/interview to conduct structured AI-cohort debriefs."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health_check():
    return {
        "status": "ok",
        "service": "AI Interview Agent",
        "mock_mode": MOCK_MODE,
        "version": "0.2.0",
    }


@app.get("/api/candidates", tags=["candidates"], summary="Get all available candidate profiles")
async def get_candidates():
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    candidates_path = os.path.join(here, "candidates.json")
    if not os.path.exists(candidates_path):
        candidates_path = os.path.join(here, "..", "candidates.json")
    if os.path.exists(candidates_path):
        with open(candidates_path, encoding="utf-8") as fh:
            data = json.load(fh)
            return data.get("candidates", [])
    raise HTTPException(status_code=404, detail="candidates.json not found")



# ---------------------------------------------------------------------------
# Core endpoint: POST /api/interview
# ---------------------------------------------------------------------------
@app.post(
    "/api/interview",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    tags=["interview"],
    summary="Conduct an interview session turn",
    description=(
        "**Start**: Send `sessionId` + `candidate` to initialise a session and receive Q1.\n\n"
        "**Turn**: Send `sessionId` + `message` (candidate's answer) to receive the next question.\n\n"
        "**End**: When `done` is `true`, the `feedback` field contains the structured debrief.\n\n"
        "In **MOCK_MODE** each question response also includes a simulated candidate reply "
        "so you can drive the full flow without manually typing answers."
    ),
)
async def interview(body: InterviewRequest) -> InterviewResponse:
    session_id = body.sessionId
    session    = get_session(session_id)

    # ------------------------------------------------------------------
    # Branch A — START: no existing session; candidate payload required
    # ------------------------------------------------------------------
    if session is None:
        if body.candidate is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Session '{session_id}' does not exist. "
                    "Provide a 'candidate' object to start a new interview."
                ),
            )

        log.info(
            "Starting session %s  candidate=%s  role=%s",
            session_id,
            body.candidate.member.id,
            body.candidate.member.jobRole,
        )

        # Generate the full question plan for this candidate
        plan = generate_question_plan(body.candidate)
        log.info(
            "Generated %d questions across %d days for session %s",
            len(plan),
            len({q.day for q in plan}),
            session_id,
        )

        create_session(session_id, body.candidate, plan)

        # The first question is already at index 0 — pass it to build_welcome
        first_q = get_current_question(session_id)
        welcome = build_welcome(body.candidate, first_q)
        append_history(session_id, "interviewer", welcome)

        log.info("[%s] Session started. Q1 day=%d type=%s", session_id, first_q.day, first_q.question_type)
        return InterviewResponse(reply=welcome, done=False)

    # ------------------------------------------------------------------
    # Branch B — Session already exists
    # ------------------------------------------------------------------
    if session["done"]:
        feedback = session.get("feedback") or build_feedback(session_id)
        session["feedback"] = feedback
        closing_reply = session["history"][-1]["text"] if session.get("history") else "Interview completed."
        log.info("[%s] Returning feedback for completed session.", session_id)
        return InterviewResponse(
            reply=closing_reply,
            done=True,
            feedback=feedback,
        )

    if body.message is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Session '{session_id}' already exists. "
                "Provide a 'message' to continue the conversation."
            ),
        )

    log.info("[%s] candidate message: %.80s", session_id, body.message)

    reply_text, is_done = process_turn(session_id, body.message)

    if is_done:
        feedback = build_feedback(session_id)
        session["feedback"] = feedback
        log.info("[%s] Interview complete. Feedback generated.", session_id)
        return InterviewResponse(reply=reply_text, done=True, feedback=feedback)

    return InterviewResponse(reply=reply_text, done=False)


# ---------------------------------------------------------------------------
# Mock Answer Generator: POST /api/mock-answer
# ---------------------------------------------------------------------------
@app.post(
    "/api/mock-answer",
    tags=["interview"],
    summary="Generate an AI-powered mock candidate answer for a given question",
    description=(
        "Judges use this endpoint during demos to generate realistic candidate answers "
        "in 4 distinct styles (detailed / unsure / wrong / vague) "
        "for any specific question the interviewer has just asked. "
        "The LLM adopts the candidate's persona from their profile in the active session."
    ),
)
async def mock_answer(body: MockAnswerRequest):
    session = get_session(body.sessionId)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{body.sessionId}' not found. Start an interview first.",
        )

    valid_styles = {"detailed", "unsure", "wrong", "vague"}
    if body.answerStyle not in valid_styles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid answerStyle '{body.answerStyle}'. Must be one of: {valid_styles}",
        )

    candidate = session["candidate"]
    log.info(
        "[%s] Generating mock answer — style=%s candidate=%s",
        body.sessionId, body.answerStyle, candidate.member.id
    )

    answer = generate_candidate_mock_answer(
        candidate=candidate,
        question_text=body.question,
        answer_style=body.answerStyle,
    )

    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mock answer generation failed — Groq API unavailable. Please retry.",
        )

    return {"answer": answer, "style": body.answerStyle, "candidateId": candidate.member.id}

