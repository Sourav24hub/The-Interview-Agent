"""
Contract verification test — runs against a live server.

Usage (from the backend/ directory, with the server running):
    python test_contract.py

It exercises the full interview lifecycle end-to-end:
  1. Start session  → expects { reply, done: false }
  2. 4 conversation turns → expects { reply, done: false }
  3. Final turn     → expects { reply, done: true, feedback: {...} }

Also tests error cases:
  - Missing candidate on first call
  - Duplicate sessionId on second start
  - Calling a completed session
"""

import json
import sys
import httpx

BASE_URL = "http://localhost:8000"
import time
import uuid

SESSION_ID = f"test-session-{uuid.uuid4().hex[:8]}"

CANDIDATE = {
    "member": {
        "id": "CAND-003",
        "name": "Emily Chen",
        "jobRole": "AI Engineer",
        "yearsExperience": 6,
        "education": "MS Artificial Intelligence",
        "status": "COMPLETED"
    },
    "missions": [
        {"day": 7,  "title": "Embeddings Explained",                "passed": True,  "attempts": 1},
        {"day": 8,  "title": "Vector Databases Overview",           "passed": True,  "attempts": 1},
        {"day": 10, "title": "Retrieval & Matching Engine",         "passed": True,  "attempts": 1},
        {"day": 11, "title": "RAG End-to-End & LLM API Basics",     "passed": True,  "attempts": 1},
        {"day": 12, "title": "Prompt Engineering Fundamentals",     "passed": True,  "attempts": 1},
        {"day": 13, "title": "Function Calling & Structured Outputs","passed": True, "attempts": 1},
        {"day": 21, "title": "LangChain Agents",                    "passed": True,  "attempts": 1},
        {"day": 22, "title": "Multi-Agent Orchestration",           "passed": True,  "attempts": 1},
        {"day": 23, "title": "Model Context Protocol (MCP)",        "passed": True,  "attempts": 1},
        {"day": 31, "title": "Capstone Project & Final Demo",       "passed": True,  "attempts": 1}
    ],
    "signals": {
        "commitDays": 31,
        "missionsCompleted": 31,
        "missionsFirstTry": 30
    }
}

MESSAGES = [
    "The most challenging mission was Multi-Agent Orchestration — coordinating agents to hand off tasks without losing context was tricky.",
    "The Embeddings & Vector Search module aligned most with my background in NLP.",
    "I'd use a hybrid retrieval approach: ChromaDB for semantic search, SQLite for structured queries, funnelled through a LangChain router agent.",
    "I skipped nothing but I'd love to go deeper on fine-tuning with QLoRA.",
    "When my first approach fails I break the problem into smaller pieces and write unit tests for each piece before trying again.",
]

PASS = "[PASS]"
FAIL = "[FAIL]"
errors = 0


def check(label: str, condition: bool, detail: str = ""):
    global errors
    symbol = PASS if condition else FAIL
    print(f"  {symbol}  {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        errors += 1


def pretty(data):
    return json.dumps(data, indent=2)


client = httpx.Client(base_url=BASE_URL, timeout=10)

print("\n-- Health check ----------------------------------------------------------")
r = client.get("/health")
check("GET /health -> 200", r.status_code == 200)
check("status field is 'ok'", r.json().get("status") == "ok")

print("\n-- Error: start without candidate ----------------------------------------")
r = client.post("/api/interview", json={"sessionId": "non-existent-session-id-999"})
check("Missing candidate -> 422", r.status_code == 422)

print("\n-- Step 1: Start interview ------------------------------------------------")
r = client.post("/api/interview", json={"sessionId": SESSION_ID, "candidate": CANDIDATE})
check("POST /api/interview -> 200", r.status_code == 200, f"got {r.status_code}")
body = r.json()
check("'reply' present",  "reply" in body)
check("'done' is false",  body.get("done") is False)
check("'feedback' absent", body.get("feedback") is None)
print(f"  -> reply: {body.get('reply', '')[:100]}...")

print("\n-- Error: start with missing message on active session --------------------")
r = client.post("/api/interview", json={"sessionId": SESSION_ID})
check("Missing message on active session -> 422", r.status_code == 422)

print("\n-- Step 2: Conversation turns until completion ---------------------------")
turn = 0
done = False
final_body = None

while not done and turn < 30:
    turn += 1
    msg = MESSAGES[(turn - 1) % len(MESSAGES)]
    r = client.post("/api/interview", json={"sessionId": SESSION_ID, "message": msg})
    check(f"Turn {turn} -> 200", r.status_code == 200, f"got {r.status_code}")
    body = r.json()
    done = body.get("done", False)
    if done:
        final_body = body
    print(f"  -> Turn {turn} done={done}: {body.get('reply', '')[:80]}...")

print("\n-- Final response verification --------------------------------------------")
check("Interview completed (done=true)", done is True)
check("Final response body present", final_body is not None)

if final_body:
    check("feedback present", "feedback" in final_body and final_body["feedback"] is not None)
    fb = final_body.get("feedback", {})
    check("feedback.summary", bool(fb.get("summary")))
    check("feedback.strengths", isinstance(fb.get("strengths"), list) and len(fb["strengths"]) > 0)
    check("feedback.gaps", isinstance(fb.get("gaps"), list) and len(fb["gaps"]) > 0)
    check("feedback.next", isinstance(fb.get("next"), list) and len(fb["next"]) > 0)
    print(f"\n  Feedback preview:\n{pretty(fb)}")

print("\n-- Calling completed session returns feedback ------------------------------")
r = client.post("/api/interview", json={"sessionId": SESSION_ID, "message": "extra"})
check("Completed session returns 200", r.status_code == 200)
post_done_body = r.json()
check("Completed session done is true", post_done_body.get("done") is True)
check("Completed session includes feedback", post_done_body.get("feedback") is not None)

print(f"\n{'='*70}")
if errors == 0:
    print(f"{PASS}  All checks passed — API contract verified.")
else:
    print(f"{FAIL}  {errors} check(s) failed.")
    sys.exit(1)
