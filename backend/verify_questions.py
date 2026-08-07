"""
verify_questions.py  (v2 — Adaptive Persona Verification)
==========================================================
Runs the full adaptive interview engine in-process with REALISTIC MESSY
candidate responses. Tests whether the new interviewer persona:
  - Catches hand-waving and responds with sarcasm + a sharp drill
  - Escalates when answers stay weak across multiple turns
  - Moves on fairly when an answer is genuinely good
  - Produces correct structured feedback at the end

Answer types injected per turn (deliberately varied):
  HANDWAVE  — "I just followed the tutorial and it worked"
  BRIEF     — 3-word non-answers
  VAGUE     — right buzzwords, zero specifics
  OFF_TOPIC — answers a different question entirely
  DEFENSIVE — "I mean, it worked, I can show you the code if you want"
  GOOD      — occasionally solid answers to verify the engine moves forward

Usage:
    $env:PYTHONUTF8=1; python verify_questions.py [CAND_ID]

    CAND-002  → backend eng, struggle-heavy (lots of probes)
    CAND-003  → near-perfect (mostly first-try depth checks)
    CAND-010  → skips + failures (all 4 question types)
    CAND-011  → heavy skips (explore-heavy)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Candidate
from question_generator import generate_question_plan, QuestionType
from interview_engine import (
    build_welcome,
    process_turn,
    build_feedback,
    assess_answer_quality,
    AnswerQuality,
    _format_planned_question,
    MOCK_MODE,
)
from session_store import (
    create_session,
    get_session,
    get_current_question,
    append_history,
)

# ---------------------------------------------------------------------------
# Messy candidate answer pools
# ---------------------------------------------------------------------------

HANDWAVE_ANSWERS = [
    "Yeah I just followed the tutorial and it worked out fine.",
    "It was pretty straightforward honestly, I just ran the code and it passed.",
    "I kind of just figured it out as I went, more or less.",
    "I used the tool they recommended, it basically just worked.",
    "I guess I followed the steps in the docs and it was done.",
    "Yeah it was easy enough, nothing too complicated.",
]

BRIEF_ANSWERS = [
    "It worked.",
    "I used the library.",
    "Completed it fine.",
    "Understood it.",
    "Done it before.",
    "I remember doing that.",
]

VAGUE_ANSWERS = [
    "So basically embeddings are vector representations of text that capture semantic meaning, and I used that to build the retrieval pipeline.",
    "The whole point is that the model can understand context better when you structure the data properly as vectors.",
    "I set up the database and configured it to store the vectors, then queried against it.",
    "Agents are basically systems that can use tools to reason through tasks, which is what I implemented.",
    "The retrieval system works by matching queries to the most similar documents using cosine similarity.",
    "I connected all the components together and it produced the right output.",
]

OFF_TOPIC_ANSWERS = [
    "Actually the part I found most interesting was the frontend integration, I spent a lot of time making the UI look good.",
    "I think the most important lesson from the cohort was time management — showing up every day matters.",
    "I preferred working with Python for this because I already knew it well from my previous job.",
    "The cohort was really well structured, I liked how they split it into modules.",
]

DEFENSIVE_ANSWERS = [
    "I mean it worked, I can show you the code if you want, I still have it.",
    "I did it, I'm not sure what more detail you're looking for.",
    "I passed it, so I must have understood it at the time.",
    "I completed all the objectives, I don't know what else to say.",
]

GOOD_ANSWERS = [
    (
        "For the retrieval engine I built a query router that first classifies the intent — "
        "SQL for structured plan data, vector search for semantic questions — using a simple "
        "classifier on top of the query. ChromaDB handled the semantic side with "
        "all-MiniLM-L6-v2 embeddings. The trickiest part was deduplication when both "
        "retrieval paths returned overlapping chunks; I ended up using document ID as the "
        "merge key and taking the higher-scoring result when there was a conflict."
    ),
    (
        "The blocker on function calling was that I kept getting the tool schema wrong — "
        "specifically the parameter types. OpenAI's function calling is strict about JSON "
        "Schema conformance and the error messages aren't helpful. What finally worked was "
        "writing a Pydantic model first, generating the schema from that, then validating "
        "every tool definition against the schema before passing it to the model. "
        "I'd warn anyone to do schema validation before any API calls, not after."
    ),
    (
        "Multi-agent orchestration with CrewAI — the main gotcha is state sharing between "
        "agents. By default each agent has no memory of what the other did, so if agent A "
        "retrieves a document and agent B needs to cite it, you have to explicitly pass the "
        "context through the task output. I ended up serialising the shared context as JSON "
        "in the task description, which isn't elegant but it worked reliably. "
        "LangGraph would have been cleaner for state management but we didn't have time."
    ),
    (
        "For streaming I used FastAPI's StreamingResponse with server-sent events. "
        "The tricky part is that when the LLM connection drops mid-stream you get a "
        "partial response in the client buffer. I handled this by sending a special "
        "done:false sentinel every token and a done:true at the end — if the client "
        "never receives done:true it knows to show an error and retry. "
        "Tested this by killing the uvicorn process mid-stream."
    ),
]

# ---------------------------------------------------------------------------
# Sequenced messy scenario
# Per-turn answer type assignment — designed to test every engine behaviour
# ---------------------------------------------------------------------------
#
# Pattern:
#   Turn 1  → HANDWAVE          (expect: sarcastic counter drill)
#   Turn 2  → BRIEF             (same topic — expect: elaboration probe)
#   Turn 3  → GOOD              (expect: advance + dry ack)
#   Turn 4  → VAGUE             (expect: precision drill)
#   Turn 5  → GOOD              (expect: advance)
#   Turn 6  → OFF_TOPIC         (treated as VAGUE — expect: drill)
#   Turn 7  → DEFENSIVE         (treated as BRIEF/VAGUE — expect: drill)
#   Turn 8  → GOOD              (advance)
#   Turn 9+ → alternate VAGUE / GOOD for remaining questions
#
# This exercises: handwave catch, escalation, good-answer advancement,
# weak-streak escalation, recovery path.

TURN_SEQUENCE = [
    HANDWAVE_ANSWERS[0],
    BRIEF_ANSWERS[0],       # still same topic — engine already probed, so advance
    GOOD_ANSWERS[0],
    VAGUE_ANSWERS[0],
    GOOD_ANSWERS[1],
    OFF_TOPIC_ANSWERS[0],
    DEFENSIVE_ANSWERS[0],
    GOOD_ANSWERS[2],
    VAGUE_ANSWERS[1],
    GOOD_ANSWERS[3],
    HANDWAVE_ANSWERS[1],
    BRIEF_ANSWERS[1],
    GOOD_ANSWERS[0],
    VAGUE_ANSWERS[2],
    GOOD_ANSWERS[1],
    HANDWAVE_ANSWERS[2],
    GOOD_ANSWERS[2],
    VAGUE_ANSWERS[3],
]


def _get_turn_answer(turn_index: int) -> str:
    """Cycle through the messy sequence."""
    return TURN_SEQUENCE[turn_index % len(TURN_SEQUENCE)]


# ---------------------------------------------------------------------------
# Load candidates
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "..", "candidates.json"), encoding="utf-8") as fh:
    ALL_CANDIDATES = json.load(fh)["candidates"]

TARGET_ID = sys.argv[1] if len(sys.argv) > 1 else "CAND-002"
raw = next((c for c in ALL_CANDIDATES if c["member"]["id"] == TARGET_ID), None)
if not raw:
    print(f"ERROR: '{TARGET_ID}' not found. Available: {[c['member']['id'] for c in ALL_CANDIDATES]}")
    sys.exit(1)

candidate = Candidate.model_validate(raw)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
SEP = "=" * 72
SEP2 = "-" * 72

print(SEP)
print("ADAPTIVE INTERVIEW ENGINE VERIFICATION  (messy candidate simulation)")
print(SEP)
print(f"Candidate  : {candidate.member.name} ({candidate.member.id})")
print(f"Role       : {candidate.member.jobRole} | {candidate.member.yearsExperience} yrs")
print(f"Signals    : {candidate.signals.missionsCompleted} completed | "
      f"{candidate.signals.missionsFirstTry} first-try | "
      f"{candidate.signals.commitDays} commit days")

# Mission breakdown
first_try = [m for m in candidate.missions if m.passed is True and (m.attempts or 0) == 1]
struggle  = [m for m in candidate.missions if m.passed is True and (m.attempts or 0) >= 3]
skipped   = [m for m in candidate.missions if m.skipped]
failed    = [m for m in candidate.missions if m.passed is False]

print("\nMission Breakdown:")
print(f"  First-try ({len(first_try)}): " + ", ".join(f"Day {m.day}" for m in first_try))
print(f"  Struggle  ({len(struggle)}): " + ", ".join(f"Day {m.day} ({m.attempts}x)" for m in struggle))
print(f"  Skipped   ({len(skipped)}): " + ", ".join(f"Day {m.day}" for m in skipped))
print(f"  Failed    ({len(failed)}): "  + ", ".join(f"Day {m.day}" for m in failed))

# ---------------------------------------------------------------------------
# Generate plan
# ---------------------------------------------------------------------------
plan = generate_question_plan(candidate)
days_covered = sorted(set(q.day for q in plan))

print(f"\nPlan: {len(plan)} questions across {len(days_covered)} days {days_covered}")
print(f"Min checks: 8+ questions={'PASS' if len(plan) >= 8 else 'FAIL'}  "
      f"4+ days={'PASS' if len(days_covered) >= 4 else 'FAIL'}")

# ---------------------------------------------------------------------------
# Start session
# ---------------------------------------------------------------------------
SESSION_ID = f"verify-{TARGET_ID}"
create_session(SESSION_ID, candidate, plan)

first_q = get_current_question(SESSION_ID)
welcome = build_welcome(candidate, first_q)
append_history(SESSION_ID, "interviewer", welcome)

print(f"\n{SEP}")
print("INTERVIEW TRANSCRIPT")
print(SEP)
print("\n[INTERVIEWER - WELCOME + Q1]\n")
print(welcome)

# ---------------------------------------------------------------------------
# Turn loop
# ---------------------------------------------------------------------------
turn_index   = 0
q_label      = 2     # Q1 already asked in welcome
drills_fired = 0
advances     = 0

while True:
    session = get_session(SESSION_ID)
    if session["done"]:
        break

    # Pick messy answer
    candidate_answer = _get_turn_answer(turn_index)

    # Assess quality BEFORE submitting (so we can annotate in the transcript)
    current_q = get_current_question(SESSION_ID)
    quality = assess_answer_quality(candidate_answer, current_q) if current_q else AnswerQuality.GOOD

    quality_tag = {
        AnswerQuality.GOOD:     "[GOOD]    ",
        AnswerQuality.VAGUE:    "[VAGUE]   ",
        AnswerQuality.BRIEF:    "[BRIEF]   ",
        AnswerQuality.HANDWAVE: "[HANDWAVE]",
    }.get(quality, "[?]")

    print(f"\n{SEP2}")
    print(f"[CANDIDATE ANSWER] {quality_tag}  Turn {turn_index + 1}")
    print(f"\n  \"{candidate_answer}\"")

    # Submit to engine
    reply_text, is_done = process_turn(SESSION_ID, candidate_answer)

    # Detect what the engine did — match labels from _format_followup()
    was_drill = any(tag in reply_text for tag in [
        "Sharp Counter",
        "Elaboration Probe",
        "Precision Drill",
    ])
    if was_drill:
        drills_fired += 1
        action_tag = ">>> DRILL FIRED (same topic)"
    else:
        advances += 1
        action_tag = "--- Advanced to next topic"

    print(f"\n{SEP2}")
    print(f"[INTERVIEWER] {action_tag}")
    print(f"\n{reply_text}")

    if is_done:
        break

    turn_index += 1

    # Safety cap — prevent infinite loops in verification
    if turn_index > 30:
        print("\n[VERIFIER] Turn cap reached (30). Ending.")
        break

# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------
final_session = get_session(SESSION_ID)
total_turns   = final_session["total_turns"]
weak_turns    = final_session["weak_turns"]

print(f"\n{SEP}")
print("TRANSCRIPT STATISTICS")
print(SEP)
print(f"Total turns    : {total_turns}")
print(f"Drills fired   : {drills_fired}")
print(f"Advances       : {advances}")
print(f"Weak turns     : {len(weak_turns)} (turns: {weak_turns})")
print(f"Weak ratio     : {len(weak_turns)/total_turns:.0%}" if total_turns else "n/a")

# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
if final_session["done"]:
    fb = build_feedback(SESSION_ID)
    print(f"\n{SEP}")
    print("GENERATED FEEDBACK")
    print(SEP)
    print(f"\nSummary:\n  {fb.summary}")
    print(f"\nStrengths ({len(fb.strengths)}):")
    for s in fb.strengths:
        print(f"  + {s}")
    print(f"\nGaps ({len(fb.gaps)}):")
    for g in fb.gaps:
        print(f"  - {g}")
    print(f"\nNext Steps ({len(fb.next)}):")
    for n in fb.next:
        print(f"  > {n}")

print(f"\n{SEP}")
print("Verification complete.")
print("Key things to check in the transcript above:")
print("  1. HANDWAVE answers triggered '[Sharp Counter]' drills with sarcasm")
print("  2. BRIEF/VAGUE answers triggered '[Elaboration Probe]' or '[Precision Drill]'")
print("  3. GOOD answers triggered 'Advanced to next topic' with a dry ack line")
print("  4. Engine never drilled the same topic more than once")
print("  5. Feedback weak_ratio is reflected in summary and gaps")
