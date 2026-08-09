"""
interview_engine.py
====================
Adaptive, persona-driven interview engine with live Groq LLM integration
and automatic offline fallback.

PERSONA
-------
Senior tech interviewer. Dry. Sharp. Probing when a candidate hand-waves, but
balanced, natural, fair, and deeply technical. Never moves on from a topic
until the candidate has demonstrated understanding or been thoroughly evaluated.

INTEGRATION ARCHITECTURE
------------------------
1. Live Groq LLM Mode (when GROQ_API_KEY is present and MOCK_MODE is not forced)
   - Uses Groq Python SDK (llama-3.3-70b-versatile) for real-time LLM chat completion
   - Generates structured LLM evaluation for final feedback schema
2. Rule-Based Fallback Engine
   - Automatic fallback if GROQ_API_KEY is missing, rate-limited, or network fails
   - Guarantees 100% API contract compliance at all times
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from models import Candidate, FeedbackPayload
from question_generator import InterviewQuestion, QuestionType
from session_store import (
    get_session,
    get_current_question,
    advance_question,
    append_history,
    mark_done,
    inject_followup,
    pop_followup,
    has_pending_followup,
    is_current_q_probed,
    mark_current_q_probed,
    record_turn,
    get_weak_streak,
    get_weak_turn_count,
    create_session,
)
from groq_service import (
    is_groq_available,
    generate_groq_turn_reply,
    generate_groq_feedback,
)

# ---------------------------------------------------------------------------
# Global Mode Control
# ---------------------------------------------------------------------------
# Forced mock mode via env var `MOCK_MODE=true` or default to False if GROQ key is set
_MOCK_MODE_ENV = os.getenv("MOCK_MODE", "").lower() in ("true", "1")
MOCK_MODE: bool = _MOCK_MODE_ENV or not is_groq_available()


# ===========================================================================
# SYSTEM PROMPT (Used for persona context)
# ===========================================================================

INTERVIEWER_PERSONA: str = """
You are a senior technical interviewer conducting a rigorous debrief of a
candidate who just completed a 31-day AI engineering cohort.

PERSONA & TONE:
- You have 15+ years building production AI systems.
- Your tone is dry, precise, natural, and conversational — sharp when a candidate
  hand-waves or recites tutorials blindly, but fair, respectful, and technical.
- Never let a vague answer slide. If the candidate handwaves, dig into the trade-offs,
  failures, or edge cases. If they give a solid answer, acknowledge it dryly and move on.
""".strip()


# ===========================================================================
# ANSWER QUALITY ASSESSMENT
# ===========================================================================

class AnswerQuality(str, Enum):
    GOOD      = "good"       # substantive, specific, technical
    VAGUE     = "vague"      # conceptually aware but no specifics
    BRIEF     = "brief"      # too short to assess
    HANDWAVE  = "handwave"   # buzzwords / tutorial references / non-answer


_HANDWAVE_PHRASES: list[str] = [
    "followed the tutorial",
    "just followed",
    "it just worked",
    "it worked",
    "pretty straightforward",
    "easy enough",
    "not really sure",
    "kind of",
    "sort of just",
    "basically just",
    "I think maybe",
    "I guess",
    "something like that",
    "I don't remember exactly",
    "more or less",
    "just ran the code",
    "copy pasted",
    "used the example",
    "took the sample",
]

_BRIEF_WORD_THRESHOLD = 35


def assess_answer_quality(answer: str, question: Optional[InterviewQuestion]) -> AnswerQuality:
    """Rule-based quality classifier for routing and statistics."""
    text  = answer.strip()
    lower = text.lower()
    words = text.split()

    if any(p in lower for p in _HANDWAVE_PHRASES):
        return AnswerQuality.HANDWAVE

    if len(words) < _BRIEF_WORD_THRESHOLD:
        return AnswerQuality.BRIEF

    if question and getattr(question, "tools", None):
        day_tools_lower = [t.lower() for t in question.tools]
        tool_mentioned = any(t in lower for t in day_tools_lower)
        if question.question_type == QuestionType.DEPTH_VERIFY and not tool_mentioned:
            return AnswerQuality.VAGUE

    sentence_count = len(re.split(r'[.!?]+', text))
    if sentence_count < 3:
        return AnswerQuality.VAGUE

    return AnswerQuality.GOOD


# ===========================================================================
# FALLBACK TEMPLATES & GENERATORS
# ===========================================================================

_FOLLOWUP_TEMPLATES: dict[AnswerQuality, list[str]] = {
    AnswerQuality.HANDWAVE: [
        (
            "Glad the {tool} tutorial exists. But tutorials are written for happy paths. "
            "Tell me what happens when {objective_challenge} — "
            "what breaks first, and how would you catch it before it hits production?"
        ),
        (
            "\"It worked\" is doing a lot of heavy lifting there. "
            "Walk me through specifically what *{tool}* is actually doing under the hood "
            "when you call it for this task. What would a wrong output look like, "
            "and how would you know?"
        ),
    ],
    AnswerQuality.BRIEF: [
        (
            "That's a start. You've given me the \"what\" — I need the \"how\" and the \"why\". "
            "Walk me through the specific step in {day_title} where you hit resistance "
            "and what decision you made to get past it."
        ),
    ],
    AnswerQuality.VAGUE: [
        (
            "You've described the concept correctly — every candidate who read the docs can do that. "
            "I want to know what *you* specifically did with {tool} during {day_title}. "
            "What parameter, config, or architectural choice did you make that wasn't default?"
        ),
    ],
}


def _generate_fallback_followup(
    quality: AnswerQuality,
    question: InterviewQuestion,
    weak_streak: int,
) -> str:
    import random
    templates = _FOLLOWUP_TEMPLATES.get(quality, _FOLLOWUP_TEMPLATES[AnswerQuality.VAGUE])
    template  = random.choice(templates)

    tools = getattr(question, "tools", [])
    tool_str = tools[0] if tools else question.day_title
    objectives = getattr(question, "objectives", [])
    obj_challenge = objectives[-1] if objectives else f"the system fails mid-{question.day_title}"

    text = template.format(
        day_title=question.day_title,
        tool=tool_str,
        objective_challenge=obj_challenge,
    )

    if weak_streak >= 2:
        text = "I'm going to push on this again because the last two answers haven't convinced me you've actually built this. " + text

    return text


def _format_planned_question(q: InterviewQuestion, number: int) -> str:
    label_map = {
        QuestionType.DEPTH_VERIFY: "Depth Verification",
        QuestionType.PROBE:        "Struggle Probe",
        QuestionType.COUNTER:      "Counter Question",
        QuestionType.EXPLORE:      "Gap Exploration",
        QuestionType.FAILED:       "Understanding Check",
    }
    label = label_map.get(q.question_type, "Question")
    tag   = f"[{label} — Day {q.day}: {q.day_title}]"
    return f"**Q{number}** {tag}\n\n{q.text}"


def _format_followup(text: str, number: int, quality: AnswerQuality) -> str:
    quality_labels = {
        AnswerQuality.HANDWAVE: "Sharp Counter",
        AnswerQuality.BRIEF:    "Elaboration Probe",
        AnswerQuality.VAGUE:    "Precision Drill",
    }
    label = quality_labels.get(quality, "Follow-up")
    tag   = f"[{label} — Drilling previous answer]"
    return f"**Q{number}** {tag}\n\n{text}"


def build_welcome(candidate: Candidate, first_question: InterviewQuestion) -> str:
    name      = candidate.member.name
    role      = candidate.member.jobRole
    completed = candidate.signals.missionsCompleted
    first_try = candidate.signals.missionsFirstTry
    yoe       = candidate.member.yearsExperience

    intro = (
        f"Alright, {name}. Let's get into it.\n\n"
        f"I've looked at your profile — {role}, {yoe} year(s) of experience, "
        f"{candidate.member.education}. "
        f"You finished {completed} missions in the cohort with {first_try} "
        f"first-try passes, which is {'solid' if first_try >= 15 else 'something we should talk about'}.\n\n"
        f"I'm not going to ask you to define embeddings or recite RAG steps. "
        f"I've read the curriculum. What I want to know is whether you actually built "
        f"things, hit walls, and understood why they fell over.\n\n"
        f"We'll move through topics based on your specific mission history. "
        f"If your answer is too short or too neat, I'll push. Fair warning.\n\n"
        f"---\n\n"
        f"{_format_planned_question(first_question, 1)}"
    )
    return intro


MAX_INTERVIEW_TURNS: int = 14   # 10 planned Qs + up to 4 live counter-question turns


# ===========================================================================
# CORE TURN PROCESSOR
# ===========================================================================

def process_turn(session_id: str, candidate_message: str) -> tuple[str, bool]:
    """
    Process one turn of the conversation.

    Routes dynamically using Groq LLM if active, falling back gracefully
    to the rule engine if Groq is unavailable or offline. Concludes after
    all plan questions or when MAX_INTERVIEW_TURNS limit (10 turns) is reached.
    """
    session   = get_session(session_id)
    candidate = session["candidate"]
    plan      = session["question_plan"]
    current_q = get_current_question(session_id)

    # Record history & quality
    append_history(session_id, "candidate", candidate_message)

    quality = assess_answer_quality(candidate_message, current_q) if current_q else AnswerQuality.GOOD
    is_weak = quality in (AnswerQuality.HANDWAVE, AnswerQuality.BRIEF, AnswerQuality.VAGUE)
    record_turn(session_id, was_weak=is_weak)
    weak_streak = get_weak_streak(session_id)

    already_probed = is_current_q_probed(session_id)
    q_number = session["total_turns"] + 1
    topics_remaining = max(0, len(plan) - session["current_q_index"])
    is_last_topic = topics_remaining <= 1

    # Attempt Live Groq Integration first (if enabled and key present)
    if is_groq_available() and not _MOCK_MODE_ENV:
        # 1. Update the session state (advance topic or log probe attempt)
        if not is_weak or already_probed:
            advance_question(session_id)
        else:
            mark_current_q_probed(session_id)

        new_idx = session["current_q_index"]
        all_topics_done = new_idx >= len(plan)
        turn_limit_hit = session["total_turns"] >= MAX_INTERVIEW_TURNS
        is_done = all_topics_done or turn_limit_hit

        # 2. Retrieve updated question context to guide the LLM's next turn
        updated_q = plan[new_idx] if new_idx < len(plan) else None
        topics_remaining = max(0, len(plan) - new_idx)

        groq_reply = generate_groq_turn_reply(
            session_id=session_id,
            candidate=candidate,
            current_q=updated_q,
            history=session["history"],
            latest_candidate_msg=candidate_message,
            q_number=q_number,
            topics_remaining=topics_remaining,
            is_done=is_done,
        )

        if groq_reply:
            if is_done:
                mark_done(session_id)
                append_history(session_id, "interviewer", groq_reply)
                return groq_reply, True

            append_history(session_id, "interviewer", groq_reply)
            return groq_reply, False


    # Fallback / Rule-Based Processing
    if session["total_turns"] >= MAX_INTERVIEW_TURNS:
        advance_question(session_id)
        mark_done(session_id)
        closing = _build_closing(session_id)
        append_history(session_id, "interviewer", closing)
        return closing, True

    if is_weak and not already_probed and current_q is not None:
        followup_text = _generate_fallback_followup(quality, current_q, weak_streak)
        inject_followup(session_id, followup_text)
        reply = _format_followup(followup_text, q_number, quality)
        append_history(session_id, "interviewer", reply)
        return reply, False

    advance_question(session_id)
    new_idx = session["current_q_index"]

    if new_idx >= len(plan):
        mark_done(session_id)
        closing = _build_closing(session_id)
        append_history(session_id, "interviewer", closing)
        return closing, True

    next_q = plan[new_idx]
    reply = _format_planned_question(next_q, q_number)

    if not is_weak:
        reply = _good_answer_ack(quality) + "\n\n" + reply

    append_history(session_id, "interviewer", reply)
    return reply, False


def _good_answer_ack(quality: AnswerQuality) -> str:
    import random
    acks = [
        "Good. Let's keep moving.",
        "That checks out.",
        "Okay, I'll take that.",
        "Right. Moving on.",
        "Fair enough.",
        "That's the kind of specificity I'm looking for. Next topic.",
    ]
    return random.choice(acks)


def _build_closing(session_id: str) -> str:
    weak_count = get_weak_turn_count(session_id)
    total      = get_session(session_id)["total_turns"]
    ratio      = weak_count / total if total > 0 else 0

    if ratio > 0.5:
        tone = "That was a mixed session — a number of your answers needed pushing. I'll reflect that in the feedback."
    elif ratio > 0.25:
        tone = "There were a few spots where I had to dig, but overall you showed reasonable depth across the topics we covered."
    else:
        tone = "Solid interview. You answered specifically and technically, which is exactly what I'm looking for."

    return (
        f"{tone}\n\n"
        f"We covered {total} turns across the key curriculum areas from your history. "
        f"I'll compile the feedback now."
    )


# ===========================================================================
# FEEDBACK BUILDER
# ===========================================================================

def build_feedback(session_id: str) -> FeedbackPayload:
    """
    Generate final structured feedback payload.
    Uses Groq LLM if active, otherwise falls back to rule calculation.
    """
    session   = get_session(session_id)
    candidate = session["candidate"]
    total_turns = session["total_turns"]
    weak_count  = get_weak_turn_count(session_id)

    # Try Groq LLM feedback generation first
    if is_groq_available() and not _MOCK_MODE_ENV:
        groq_fb = generate_groq_feedback(
            session_id=session_id,
            candidate=candidate,
            history=session["history"],
            total_turns=total_turns,
            weak_turns_count=weak_count,
        )
        if groq_fb:
            return groq_fb

    # Fallback rule calculation
    plan = session["question_plan"]
    missions_passed  = [m for m in candidate.missions if m.passed is True]
    missions_skipped = [m for m in candidate.missions if m.skipped]
    missions_failed  = [m for m in candidate.missions if m.passed is False]
    high_attempt     = [m for m in missions_passed if (m.attempts or 0) >= 4]

    weak_ratio = weak_count / total_turns if total_turns > 0 else 0

    strengths: list[str] = []
    gaps:      list[str] = []
    next_steps: list[str] = []

    if candidate.signals.commitDays >= 25:
        strengths.append(f"Sustained engagement: {candidate.signals.commitDays} active days demonstrates consistent work ethic throughout the 31-day cohort.")
    if candidate.signals.missionsFirstTry >= 15:
        strengths.append(f"High first-attempt accuracy: {candidate.signals.missionsFirstTry}/{candidate.signals.missionsCompleted} missions passed first try — indicates strong problem-solving approach.")
    elif candidate.signals.missionsFirstTry >= 8:
        strengths.append(f"Reasonable first-attempt rate ({candidate.signals.missionsFirstTry}/{candidate.signals.missionsCompleted}) — shows deliberate preparation.")
    if len(missions_passed) >= 8:
        strengths.append(f"Broad coverage: {len(missions_passed)} missions completed across multiple modules.")

    if not strengths:
        strengths.append("Demonstrated persistence in completing the AI cohort.")

    if weak_ratio >= 0.5:
        gaps.append(f"Communication of technical depth: {weak_count}/{total_turns} turns required follow-up prompting to elicit technical detail.")
    elif weak_ratio >= 0.25:
        gaps.append(f"Inconsistent depth in explanations: {weak_count} turns required drilling.")
    if missions_skipped:
        titles = ", ".join(m.title for m in missions_skipped)
        gaps.append(f"Unverified areas from skipped missions: {titles}.")
    if missions_failed:
        titles = ", ".join(m.title for m in missions_failed)
        gaps.append(f"Incomplete missions with outstanding knowledge gaps: {titles}.")
    if high_attempt:
        titles = ", ".join(m.title for m in high_attempt[:3])
        gaps.append(f"Persistent difficulty areas (4+ attempts): {titles}.")

    if not gaps:
        gaps.append("No critical gaps identified.")

    if weak_ratio >= 0.4:
        next_steps.append("Practice articulating technical decisions out loud with specific trade-offs.")
    if missions_skipped:
        next_steps.append("Complete the skipped missions hands-on, particularly security and deployment modules.")
    if missions_failed:
        next_steps.append("Revisit failed missions by building a standalone implementation from scratch.")
    next_steps.append("Ship a production-grade AI project end-to-end (RAG + agents + deployment).")

    summary = (
        f"{candidate.member.name} ({candidate.member.jobRole}, {candidate.member.yearsExperience} yrs exp) "
        f"completed the AI cohort with {candidate.signals.missionsCompleted} missions, {candidate.signals.commitDays} active days, "
        f"and a {candidate.signals.missionsFirstTry}/{candidate.signals.missionsCompleted} first-try rate. "
        f"Overall interview performance: {'strong' if weak_ratio < 0.25 else 'mixed' if weak_ratio < 0.5 else 'below expectations'}."
    )

    return FeedbackPayload(
        summary=summary,
        strengths=strengths,
        gaps=gaps,
        next=next_steps,
    )
