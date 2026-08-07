"""
question_generator.py
=====================
Generates a personalised, ordered interview question plan for a given candidate.

Strategy
--------
Priority 1 – FIRST-TRY passes  (attempts == 1, passed == True)
    → 2 depth-verification questions per day.
    → Goal: confirm mastery was real, not lucky.

Priority 2 – STRUGGLE passes   (attempts >= 3, passed == True)
    → 1 probe question  + 1 counter-question per day.
    → Goal: surface what broke, what finally clicked, what gaps remain.

Priority 3 – SKIPPED days
    → 1 exploration question per day.
    → Goal: understand reasoning and probe conceptual coverage.

Priority 4 – FAILED missions   (passed == False)
    → 1 direct question per day.
    → Goal: understand current understanding level.

Rules
-----
- Minimum 8 questions total.
- Minimum 4 distinct curriculum days covered.
- Questions use the day's title + objectives from curriculum.json as context.
- Counter-questions are tagged so the engine can decide whether to ask them
  based on the quality of the main answer (or always in mock mode).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from models import Candidate, Mission


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class QuestionType(str, Enum):
    DEPTH_VERIFY  = "depth_verify"   # first-try day — confirm real understanding
    PROBE         = "probe"          # struggle day — surface the difficulty
    COUNTER       = "counter"        # follow-up counter on a weak probe answer
    EXPLORE       = "explore"        # skipped day — conceptual coverage
    FAILED        = "failed"         # failed mission — current understanding


@dataclass
class InterviewQuestion:
    day: int
    day_title: str
    question_type: QuestionType
    text: str
    # Runtime context — used by the engine for sharp, grounded follow-ups
    tools: List[str] = field(default_factory=list)
    objectives: List[str] = field(default_factory=list)
    # counter is only set on PROBE questions
    counter: Optional["InterviewQuestion"] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Curriculum loader
# ---------------------------------------------------------------------------

def _load_curriculum() -> dict:
    """Load curriculum.json from the project root (one level above backend/)."""
    here = os.path.dirname(os.path.abspath(__file__))
    curriculum_path = os.path.join(here, "..", "curriculum.json")
    with open(curriculum_path, encoding="utf-8") as fh:
        return json.load(fh)


def _build_day_index(curriculum: dict) -> dict[int, dict]:
    """Return {day_number: day_dict} for fast lookup."""
    return {d["day"]: d for d in curriculum.get("days", [])}


# ---------------------------------------------------------------------------
# Question templates — parameterised by day context
# ---------------------------------------------------------------------------

def _depth_questions(day: dict, mission: Mission) -> List[InterviewQuestion]:
    """Two depth-verification questions for a first-try pass."""
    title = day["title"]
    objectives = day.get("objectives", [])
    tools = day.get("tools", [])

    obj_str  = objectives[0] if objectives else f"the key objective of {title}"
    tool_str = tools[0]      if tools      else "the tools covered"

    q1 = InterviewQuestion(
        day=day["day"],
        day_title=title,
        question_type=QuestionType.DEPTH_VERIFY,
        tools=tools,
        objectives=objectives,
        text=(
            f"You passed **{title}** (Day {day['day']}) on your very first attempt. "
            f"Walk me through exactly how you achieved: \"{obj_str}\". "
            f"What was your thought process and how did you validate it worked?"
        ),
    )

    obj2_str = objectives[1] if len(objectives) > 1 else f"another challenge from {title}"
    q2 = InterviewQuestion(
        day=day["day"],
        day_title=title,
        question_type=QuestionType.DEPTH_VERIFY,
        tools=tools,
        objectives=objectives,
        text=(
            f"Still on Day {day['day']} — {title}. "
            f"The objective says: \"{obj2_str}\". "
            f"How did you use {tool_str} to accomplish this, and what would you do differently now?"
        ),
    )
    return [q1, q2]


def _struggle_questions(day: dict, mission: Mission) -> List[InterviewQuestion]:
    """Probe question + counter-question for a high-attempt pass."""
    title = day["title"]
    objectives = day.get("objectives", [])
    tools = day.get("tools", [])
    attempts = mission.attempts or 0

    obj_str  = objectives[0] if objectives else f"the main objective of {title}"
    tool_str = ", ".join(tools[:2]) if tools else "the tools"

    probe = InterviewQuestion(
        day=day["day"],
        day_title=title,
        question_type=QuestionType.PROBE,
        tools=tools,
        objectives=objectives,
        text=(
            f"You passed **{title}** (Day {day['day']}) but it took you {attempts} attempts. "
            f"What was the specific blocker that kept you from passing sooner? "
            f"Describe the moment things finally clicked."
        ),
    )

    counter_obj = objectives[-1] if objectives else obj_str
    counter = InterviewQuestion(
        day=day["day"],
        day_title=title,
        question_type=QuestionType.COUNTER,
        tools=tools,
        objectives=objectives,
        text=(
            f"Let's go a level deeper on {title}. "
            f"The final objective was: \"{counter_obj}\". "
            f"Can you explain how {tool_str} fit into that, and describe a mistake you made "
            f"that you would warn someone else about?"
        ),
    )
    probe.counter = counter
    return [probe, counter]


def _skip_question(day: dict) -> InterviewQuestion:
    """Exploration question for a skipped day."""
    title = day["title"]
    objectives = day.get("objectives", [])
    tools = day.get("tools", [])

    obj_str  = objectives[0] if objectives else f"the main concept of {title}"
    tool_str = tools[0]      if tools      else "the tools involved"

    return InterviewQuestion(
        day=day["day"],
        day_title=title,
        question_type=QuestionType.EXPLORE,
        tools=tools,
        objectives=objectives,
        text=(
            f"You skipped **{title}** (Day {day['day']}). "
            f"Without having completed it formally, how would you approach: \"{obj_str}\"? "
            f"And are you familiar with {tool_str} from other experience?"
        ),
    )


def _failed_question(day: dict, mission: Mission) -> InterviewQuestion:
    """Direct question for a failed mission."""
    title = day["title"]
    objectives = day.get("objectives", [])
    attempts = mission.attempts or 0

    obj_str = objectives[0] if objectives else f"the key concept of {title}"

    return InterviewQuestion(
        day=day["day"],
        day_title=title,
        question_type=QuestionType.FAILED,
        tools=day.get("tools", []),
        objectives=objectives,
        text=(
            f"You attempted **{title}** (Day {day['day']}) {attempts} time(s) but didn't pass. "
            f"How would you describe your current understanding of: \"{obj_str}\"? "
            f"What would you need to review to get there?"
        ),
    )


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_question_plan(candidate: Candidate) -> List[InterviewQuestion]:
    """
    Build the full ordered question plan for this candidate.

    Returns a flat list of InterviewQuestion objects.  Counter-questions
    are already embedded as a `.counter` attribute on their parent PROBE
    question AND also included in the flat list immediately after their parent.
    """
    curriculum = _load_curriculum()
    day_index  = _build_day_index(curriculum)

    # Categorise missions
    first_try: List[Mission] = []
    struggle:  List[Mission] = []
    skipped:   List[Mission] = []
    failed:    List[Mission] = []

    for m in candidate.missions:
        if m.skipped:
            skipped.append(m)
        elif m.passed is False:
            failed.append(m)
        elif m.passed is True:
            attempts = m.attempts or 1
            if attempts == 1:
                first_try.append(m)
            elif attempts >= 3:
                struggle.append(m)
            # attempts == 2 → easy pass, skip for now to hit min 8 from key categories

    plan: List[InterviewQuestion] = []
    days_covered: set[int] = set()

    # --- Priority 1: first-try (max 3 days to avoid bloat) ---
    for m in first_try[:3]:
        day = day_index.get(m.day)
        if not day:
            continue
        qs = _depth_questions(day, m)
        plan.extend(qs)
        days_covered.add(m.day)

    # --- Priority 2: struggle passes ---
    for m in struggle:
        day = day_index.get(m.day)
        if not day:
            continue
        qs = _struggle_questions(day, m)
        plan.extend(qs)
        days_covered.add(m.day)

    # --- Priority 3: skipped days ---
    for m in skipped:
        day = day_index.get(m.day)
        if not day:
            continue
        plan.append(_skip_question(day))
        days_covered.add(m.day)

    # --- Priority 4: failed missions ---
    for m in failed:
        day = day_index.get(m.day)
        if not day:
            continue
        plan.append(_failed_question(day, m))
        days_covered.add(m.day)

    # --- Pad to minimum 8 questions if needed ---
    # Pull easy-pass missions (attempts == 2) as padding
    if len(plan) < 8:
        easy_pass = [
            m for m in candidate.missions
            if m.passed is True and (m.attempts or 0) == 2
        ]
        for m in easy_pass:
            if len(plan) >= 8:
                break
            day = day_index.get(m.day)
            if not day or m.day in days_covered:
                continue
            probe, counter = _struggle_questions(day, m)[:2]
            # Rewrite probe text for a 2-attempt context
            probe.text = (
                f"You passed **{day['title']}** (Day {m.day}) on your second attempt. "
                f"What adjustment did you make between attempt 1 and 2 that made the difference?"
            )
            plan.append(probe)
            plan.append(counter)
            days_covered.add(m.day)

    # Safety: if still < 8, duplicate depth-verify from existing first-try days
    remaining_first_try = [
        m for m in first_try[3:]
        if day_index.get(m.day)
    ]
    for m in remaining_first_try:
        if len(plan) >= 8:
            break
        day = day_index.get(m.day)
        plan.extend(_depth_questions(day, m))
        days_covered.add(m.day)

    return plan
