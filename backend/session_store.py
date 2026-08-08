"""
session_store.py
================
In-memory session store.

Schema per session:
{
    "candidate":          Candidate,
    "question_plan":      List[InterviewQuestion],   # topic roadmap
    "current_q_index":    int,                       # next planned question
    "dynamic_followup":   Optional[str],             # injected sharp follow-up text
    "current_q_probed":   bool,                      # True once we've drilled this topic once
    "weak_streak":        int,                       # consecutive weak answers
    "total_turns":        int,                       # total turns taken so far
    "weak_turns":         List[int],                 # turn numbers flagged as weak
    "history":            List[{role, text}],
    "done":               bool,
}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

sessions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def create_session(session_id: str, candidate, question_plan: List) -> None:
    sessions[session_id] = {
        "candidate":         candidate,
        "question_plan":     question_plan,
        "current_q_index":   0,
        "dynamic_followup":  None,   # injected by engine when answer is weak
        "current_q_probed":  False,  # have we already drilled this topic?
        "weak_streak":       0,
        "total_turns":       0,
        "weak_turns":        [],
        "history":           [],
        "done":              False,
    }


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return sessions.get(session_id)


# ---------------------------------------------------------------------------
# Question navigation
# ---------------------------------------------------------------------------

def get_current_question(session_id: str):
    """Return the planned question at current_q_index, or None if exhausted."""
    s = sessions[session_id]
    idx = s["current_q_index"]
    plan = s["question_plan"]
    return plan[idx] if idx < len(plan) else None


def advance_question(session_id: str) -> None:
    """Advance to next planned question and reset per-topic probe state."""
    sessions[session_id]["current_q_index"] += 1
    sessions[session_id]["current_q_probed"] = False
    sessions[session_id]["dynamic_followup"] = None


def questions_remaining(session_id: str) -> int:
    s = sessions[session_id]
    return len(s["question_plan"]) - s["current_q_index"]


# ---------------------------------------------------------------------------
# Dynamic follow-up injection
# ---------------------------------------------------------------------------

def inject_followup(session_id: str, followup_text: str) -> None:
    """Store a dynamically generated follow-up to ask on next turn."""
    sessions[session_id]["dynamic_followup"] = followup_text
    sessions[session_id]["current_q_probed"] = True


def pop_followup(session_id: str) -> Optional[str]:
    """Consume and return the pending follow-up (if any)."""
    text = sessions[session_id].get("dynamic_followup")
    sessions[session_id]["dynamic_followup"] = None
    return text


def has_pending_followup(session_id: str) -> bool:
    return bool(sessions[session_id].get("dynamic_followup"))


def is_current_q_probed(session_id: str) -> bool:
    return sessions[session_id]["current_q_probed"]


def mark_current_q_probed(session_id: str) -> None:
    """Mark current question topic as probed so the engine advances on the next turn."""
    if session_id in sessions:
        sessions[session_id]["current_q_probed"] = True


# ---------------------------------------------------------------------------
# Weak-answer tracking
# ---------------------------------------------------------------------------

def record_turn(session_id: str, was_weak: bool) -> None:
    s = sessions[session_id]
    s["total_turns"] += 1
    if was_weak:
        s["weak_streak"] += 1
        s["weak_turns"].append(s["total_turns"])
    else:
        s["weak_streak"] = 0


def get_weak_streak(session_id: str) -> int:
    return sessions[session_id]["weak_streak"]


def get_weak_turn_count(session_id: str) -> int:
    return len(sessions[session_id]["weak_turns"])


# ---------------------------------------------------------------------------
# History & completion
# ---------------------------------------------------------------------------

def append_history(session_id: str, role: str, text: str) -> None:
    sessions[session_id]["history"].append({"role": role, "text": text})


def mark_done(session_id: str) -> None:
    sessions[session_id]["done"] = True
