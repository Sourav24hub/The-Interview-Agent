"""
groq_service.py
===============
Groq LLM service integration for the AI Interview Agent.

Integrates Groq's Python SDK (or OpenAI compatibility layer) to power:
  1. Dynamic, persona-driven conversation turns
  2. Structured feedback generation upon interview completion
  3. Automatic fallback to template-based rules if Groq API is unavailable or unconfigured
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from models import Candidate, FeedbackPayload
from question_generator import InterviewQuestion, QuestionType

load_dotenv()

log = logging.getLogger("groq_service")

def get_groq_client():
    """Dynamically get or initialize Groq client from environment."""
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    if api_key and api_key != "gsk_your_groq_api_key_here":
        try:
            from groq import Groq
            return Groq(api_key=api_key, timeout=30.0), model
        except Exception as err:
            log.warning("Failed to initialize Groq client: %s", err)
    return None, model


def is_groq_available() -> bool:
    """Return True if Groq client is configured with a valid API key."""
    client, _ = get_groq_client()
    return client is not None


# ---------------------------------------------------------------------------
# Persona & System Prompts
# ---------------------------------------------------------------------------

GROQ_SYSTEM_PROMPT: str = """
You are a senior staff AI interviewer conducting a technical debrief for a candidate who completed a 31-day AI cohort.

INTERVIEWER CONDUCT & RULES:
1. RESPECT CANDIDATE BACKGROUND & ROLE: Read the Candidate Profile and Role Guidance carefully. Match your question depth and technical expectations to their job role (e.g. non-engineering roles like Marketing, HR, or BA focus on prompt design, workflow automation, and practical use-cases; engineers focus on architecture and trade-offs). Never ask irrelevant low-level concurrency or Git merge questions to non-engineers.
2. CONTEXTUAL & MISSION-BASED PROGRESSION: Ask ONLY about the candidate's actual completed cohort missions and previous responses. Move naturally from one topic to the next.
3. BALANCED PERSONA: Maintain a dry, probing, and slightly sharp persona. Acknowledge good answers dryly ("Fair point.", "Good practical application.") and push on vague answers ("Glad the tutorial worked, but how did you verify output quality?").
4. STRICT SINGLE QUESTION RULE: You MUST end your turn with strictly ONE single, clear question. Never ask multiple questions in a single turn.
5. CONCISE & CHUNKED: Keep your turn concise and readable (2-3 short sentences, 50-80 words max). Plain text only. No markdown headers or JSON wrappers.
""".strip()


def _ensure_single_question(text: str) -> str:
    """Ensure interviewer response asks strictly one single focused question."""
    if not text:
        return text

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    question_count = 0
    clean_sentences = []
    
    for sentence in sentences:
        if '?' in sentence:
            question_count += 1
            if question_count == 1:
                clean_sentences.append(sentence)
        else:
            if question_count == 0:
                clean_sentences.append(sentence)

    result = " ".join(clean_sentences).strip()
    return result if result else text.strip()


def _determine_role_depth_guidance(candidate: Candidate) -> str:
    """Generate candidate-aware expectations matching their job role and experience level."""
    role_lower = candidate.member.jobRole.lower()
    yoe = candidate.member.yearsExperience

    non_tech_keywords = ["marketing", "hr", "human resources", "business analyst", "ux", "design", "product", "it support"]
    if any(kw in role_lower for kw in non_tech_keywords):
        return (
            f"ROLE GUIDANCE ({candidate.member.jobRole}, {yoe} yrs exp):\n"
            f"- Domain-specific / Non-engineering role.\n"
            f"- Focus questions on practical AI use-cases, prompt design, workflow automation, and problem solving.\n"
            f"- DO NOT ask about low-level concurrency locks, memory pointers, distributed database replication, or advanced Git merges."
        )

    if yoe <= 1 or "intern" in role_lower or "junior" in role_lower:
        return (
            f"ROLE GUIDANCE ({candidate.member.jobRole}, {yoe} yrs exp):\n"
            f"- Early-career candidate.\n"
            f"- Focus on core concepts, fundamental coding, step-by-step debugging, and mission learning points.\n"
            f"- Do not expect senior architect-level system design."
        )

    return (
        f"ROLE GUIDANCE ({candidate.member.jobRole}, {yoe} yrs exp):\n"
        f"- Experienced technical professional.\n"
        f"- Probe into production trade-offs, architecture decisions, edge cases, error handling, and reliability."
    )


def _build_candidate_context_prompt(candidate: Candidate, current_q: Optional[InterviewQuestion]) -> str:
    """Construct rich context string about the candidate profile and current mission topic."""
    first_try_days = [m.day for m in candidate.missions if m.passed is True and (m.attempts or 0) == 1]
    struggle_days = [f"Day {m.day} ({m.attempts}x attempts)" for m in candidate.missions if m.passed is True and (m.attempts or 0) >= 3]
    skipped_days = [f"Day {m.day}: {m.title}" for m in candidate.missions if m.skipped]
    failed_days = [f"Day {m.day}: {m.title}" for m in candidate.missions if m.passed is False]
    role_guidance = _determine_role_depth_guidance(candidate)

    topic_str = ""
    if current_q:
        tools_str = ", ".join(current_q.tools) if current_q.tools else "relevant tools"
        objs_str = "; ".join(current_q.objectives) if current_q.objectives else current_q.day_title
        topic_str = (
            f"\nCURRENT TARGET QUESTION CONTEXT:\n"
            f"- Curriculum Day {current_q.day}: {current_q.day_title}\n"
            f"- Question Type: {current_q.question_type.value}\n"
            f"- Key Objectives: {objs_str}\n"
            f"- Core Tools: {tools_str}\n"
            f"- Base Question Prompt: {current_q.text}\n"
        )

    return (
        f"CANDIDATE PROFILE:\n"
        f"- Name: {candidate.member.name}\n"
        f"- Role & Experience: {candidate.member.jobRole} ({candidate.member.yearsExperience} yrs exp, {candidate.member.education})\n"
        f"- Cohort Stats: {candidate.signals.missionsCompleted} completed, {candidate.signals.missionsFirstTry} first-try passes, {candidate.signals.commitDays} commit days.\n"
        f"- First-try Pass Days: {first_try_days[:5]}\n"
        f"- Struggle Days (High Attempts): {struggle_days[:5] if struggle_days else 'None'}\n"
        f"- Skipped Days: {skipped_days[:5] if skipped_days else 'None'}\n"
        f"- Failed Days: {failed_days[:5] if failed_days else 'None'}\n\n"
        f"{role_guidance}\n"
        f"{topic_str}"
    )


# ---------------------------------------------------------------------------
# LLM Turn Response Generator
# ---------------------------------------------------------------------------

def generate_groq_turn_reply(
    session_id: str,
    candidate: Candidate,
    current_q: Optional[InterviewQuestion],
    history: List[Dict[str, str]],
    latest_candidate_msg: str,
    q_number: int,
    topics_remaining: int = 1,
) -> Optional[str]:
    """
    Generate an AI interviewer response turn using Groq API.
    Retries across fallback models if rate limits occur.
    """
    client, primary_model = get_groq_client()
    if not client:
        return None

    candidate_ctx = _build_candidate_context_prompt(candidate, current_q)

    # Inject session pacing so LLM knows when to wrap up
    pacing_note = ""
    if topics_remaining <= 1:
        pacing_note = (
            "\nSESSION STATUS: This is the LAST topic. After evaluating the candidate's answer, "
            "briefly acknowledge and conclude the interview naturally. Do NOT ask another new topic question."
        )
    elif topics_remaining <= 2:
        pacing_note = f"\nSESSION STATUS: {topics_remaining} topics remaining. Start wrapping toward a conclusion."

    system_content = f"{GROQ_SYSTEM_PROMPT}\n\n{candidate_ctx}{pacing_note}"

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]
    recent_history = history[-10:] if len(history) > 10 else history
    for item in recent_history:
        role = "assistant" if item["role"] in ("interviewer", "assistant") else "user"
        messages.append({"role": role, "content": item["text"]})

    if not recent_history or recent_history[-1].get("text") != latest_candidate_msg:
        messages.append({"role": "user", "content": latest_candidate_msg})

    models_to_try = [primary_model, "llama-3.1-8b-instant", "llama3-70b-8192", "llama3-8b-8192"]
    models_to_try = list(dict.fromkeys(models_to_try))

    for m in models_to_try:
        try:
            response = client.chat.completions.create(
                model=m,
                messages=messages,
                temperature=0.7,
                max_tokens=220,
                timeout=30.0,
            )
            reply_text = response.choices[0].message.content.strip()
            if reply_text:
                reply_text = _ensure_single_question(reply_text)
                log.info("[%s] Groq turn response generated successfully (model: %s).", session_id, m)
                return reply_text
        except Exception as err:
            log.warning("[%s] Groq API model %s failed: %s. Trying next candidate model...", session_id, m, err)

    return None



# ---------------------------------------------------------------------------
# LLM Structured Feedback Generator
# ---------------------------------------------------------------------------

def generate_groq_feedback(
    session_id: str,
    candidate: Candidate,
    history: List[Dict[str, str]],
    total_turns: int,
    weak_turns_count: int,
) -> Optional[FeedbackPayload]:
    """
    Generate structured FeedbackPayload JSON using Groq API.
    Returns None if Groq fails or is unavailable.
    """
    client, primary_model = get_groq_client()
    if not client:
        return None

    feedback_prompt = f"""
You are the senior technical AI interviewer compiling final feedback for {candidate.member.name} ({candidate.member.jobRole}).
Analyze the full transcript and candidate signals to generate a structured JSON feedback payload matching this EXACT schema:

{{
  "summary": "Detailed 2-3 sentence technical evaluation of the candidate's cohort performance and interview responses.",
  "strengths": ["Clear, concise point 1", "Clear, concise point 2", "Clear, concise point 3"],
  "gaps": ["Actionable gap 1", "Actionable gap 2"],
  "next": ["Concrete recommended next step 1", "Concrete recommended next step 2", "Concrete recommended next step 3"]
}}

CANDIDATE SIGNAL METRICS:
- Name: {candidate.member.name}
- Job Role: {candidate.member.jobRole} ({candidate.member.yearsExperience} yrs experience)
- Missions Completed: {candidate.signals.missionsCompleted}
- First-Try Pass Rate: {candidate.signals.missionsFirstTry}/{candidate.signals.missionsCompleted}
- Commit Days: {candidate.signals.commitDays}
- Interview Turns: {total_turns} total turns ({weak_turns_count} turns required probing/drilling)

Return ONLY valid JSON. No markdown formatting code blocks, no trailing comments.
"""

    messages = [
        {"role": "system", "content": "You are a technical evaluation engine that outputs only valid JSON."},
        {"role": "user", "content": feedback_prompt},
    ]

    models_to_try = [primary_model, "llama-3.1-8b-instant", "llama3-70b-8192", "llama3-8b-8192"]
    models_to_try = list(dict.fromkeys(models_to_try))

    for m in models_to_try:
        try:
            response = client.chat.completions.create(
                model=m,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
                timeout=30.0,
            )

            content = response.choices[0].message.content.strip()
            data = json.loads(content)

            feedback = FeedbackPayload(
                summary=str(data.get("summary", "")),
                strengths=[str(s) for s in data.get("strengths", []) if s],
                gaps=[str(g) for g in data.get("gaps", []) if g],
                next=[str(n) for n in data.get("next", []) if n],
            )

            if feedback.summary and feedback.strengths and feedback.gaps and feedback.next:
                log.info("[%s] Groq structured feedback generated successfully (model: %s).", session_id, m)
                return feedback
        except Exception as err:
            log.warning("[%s] Groq feedback API model %s failed: %s.", session_id, m, err)

    return None
