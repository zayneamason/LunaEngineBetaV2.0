#!/usr/bin/env python3
"""
Live Conversation Test — Full multi-turn flow with diagnostics.

Sends a realistic conversation to Luna and reports:
- Response time (TTFT proxy)
- Provider/route used
- Whether Luna asked questions (curiosity buffer validation)
- Full response text
- Diagnostics at each checkpoint

Runs continuously — Ctrl+C to stop.
"""

import requests
import time
import json
import sys

BASE = "http://localhost:8000"
TIMEOUT = 45  # seconds per message

# ── Diagnostic Checkpoints ────────────────────────────────────────────

def check_health():
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        d = r.json()
        return d.get("status") == "healthy", d
    except Exception as e:
        return False, {"error": str(e)}

def check_status():
    try:
        r = requests.get(f"{BASE}/status", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def send_message(text, timeout=TIMEOUT):
    """Send a message and return (response_text, metadata, elapsed_ms) or (None, error, elapsed_ms)."""
    start = time.time()
    try:
        r = requests.post(
            f"{BASE}/message",
            json={"message": text, "timeout": timeout},
            timeout=timeout + 5,
        )
        elapsed = (time.time() - start) * 1000
        if r.status_code == 200:
            d = r.json()
            return d.get("text", ""), d, elapsed
        else:
            return None, {"error": f"HTTP {r.status_code}: {r.text[:200]}"}, elapsed
    except requests.exceptions.Timeout:
        elapsed = (time.time() - start) * 1000
        return None, {"error": f"TIMEOUT after {elapsed:.0f}ms"}, elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return None, {"error": str(e)}, elapsed

# ── Conversation Scripts ──────────────────────────────────────────────

CONVERSATIONS = [
    {
        "name": "Casual Greeting Flow",
        "turns": [
            "hey luna",
            "how are you doing today?",
            "I've been working on something cool — a new lighting system for a booth",
            "it uses teensy 4.0 microcontrollers with LED strips",
            "what do you think about that kind of project?",
            "thanks luna, talk later",
        ],
    },
    {
        "name": "Knowledge + Memory Flow",
        "turns": [
            "luna do you remember the oracle booth project?",
            "tell me about the LED configuration we decided on",
            "and what about the teensy pins — which ones did we map?",
            "cool, I might change the strip count. what would you suggest?",
        ],
    },
    {
        "name": "Voice-Style Short Turns",
        "turns": [
            "hey",
            "what's up",
            "tell me something interesting",
            "nice",
            "ok bye",
        ],
    },
]

# ── Analysis ──────────────────────────────────────────────────────────

def count_questions(text):
    """Count question marks in response."""
    return text.count("?") if text else 0

def print_separator(char="─", width=70):
    print(char * width)

def print_header(text):
    print_separator("═")
    print(f"  {text}")
    print_separator("═")

# ── Main Loop ─────────────────────────────────────────────────────────

def run_conversation(conv, conv_index):
    name = conv["name"]
    turns = conv["turns"]

    print_header(f"CONVERSATION {conv_index + 1}: {name}")

    # Pre-flight health check
    healthy, health_data = check_health()
    if not healthy:
        print(f"  ⛔ HEALTH CHECK FAILED: {health_data}")
        return False
    print(f"  ✓ Health: OK | Pipeline: {'connected' if health_data.get('pipeline', {}).get('connected') else 'DISCONNECTED'}")

    questions_per_turn = []
    total_questions = 0
    total_time = 0
    failures = 0

    for i, user_msg in enumerate(turns):
        turn_num = i + 1
        print_separator()
        print(f"  TURN {turn_num}/{len(turns)}")
        print(f"  USER: {user_msg}")
        print()

        text, meta, elapsed = send_message(user_msg)
        total_time += elapsed

        if text is None:
            print(f"  ⛔ FAILED: {meta.get('error', 'unknown')}")
            print(f"  ⏱  {elapsed:.0f}ms")
            failures += 1

            # Diagnostic dump on failure
            print(f"\n  ── FAILURE DIAGNOSTICS ──")
            status = check_status()
            if isinstance(status, dict) and "error" not in status:
                print(f"  State: {status.get('state')}")
                print(f"  Uptime: {status.get('uptime_seconds', 0):.0f}s")
                ag = status.get("agentic", {})
                print(f"  Agentic: processing={ag.get('is_processing')} goal={ag.get('current_goal', 'none')[:40]}")
                print(f"  Tasks: started={ag.get('tasks_started')} completed={ag.get('tasks_completed')} aborted={ag.get('tasks_aborted')}")
            else:
                print(f"  Status endpoint: {status}")

            # Check server logs for errors
            print(f"  ── Check server terminal for errors ──")
            continue

        q_count = count_questions(text)
        questions_per_turn.append(q_count)
        total_questions += q_count

        # Response info
        model = meta.get("model", "unknown")
        delegated = meta.get("delegated", False)
        local = meta.get("local", False)
        latency = meta.get("latency_ms", 0)

        route = "delegated" if delegated else ("local" if local else "unknown")

        print(f"  LUNA: {text[:500]}")
        if len(text) > 500:
            print(f"  ... [{len(text)} chars total]")
        print()
        print(f"  ⏱  {elapsed:.0f}ms | model={model} | route={route} | questions={q_count}")

        # Curiosity buffer validation
        if q_count > 1:
            print(f"  ⚠  MULTIPLE QUESTIONS ({q_count}) — curiosity buffer may not be suppressing")
        elif q_count == 0:
            print(f"  ✓  No questions asked (buffer holding)")
        else:
            print(f"  ℹ  1 question asked")

        # Brief pause between turns (realistic conversation pacing)
        if i < len(turns) - 1:
            time.sleep(1.5)

    # ── Conversation Summary ──────────────────────────────────────
    print_separator("═")
    print(f"  SUMMARY: {name}")
    print(f"  Turns: {len(turns)} | Failures: {failures} | Avg latency: {total_time / len(turns):.0f}ms")
    print(f"  Total questions Luna asked: {total_questions}")
    print(f"  Questions per turn: {questions_per_turn}")

    if total_questions == 0:
        print(f"  ✓ CURIOSITY BUFFER: Perfect — zero questions across all turns")
    elif total_questions <= 2:
        print(f"  ✓ CURIOSITY BUFFER: Good — {total_questions} questions (low frequency)")
    else:
        print(f"  ⚠ CURIOSITY BUFFER: {total_questions} questions — may need tuning")

    print_separator("═")
    print()
    return failures == 0


def main():
    print("\n" + "=" * 70)
    print("  LUNA LIVE CONVERSATION TEST")
    print("  Press Ctrl+C to stop")
    print("=" * 70 + "\n")

    # Initial health check
    healthy, health_data = check_health()
    if not healthy:
        print(f"⛔ Server not responding: {health_data}")
        print("Start the backend first: PYTHONPATH=src python3 scripts/run.py --server --host 0.0.0.0 --port 8000")
        sys.exit(1)

    print(f"✓ Backend healthy: {json.dumps(health_data, indent=2)}\n")

    round_num = 0
    try:
        while True:
            round_num += 1
            print(f"\n{'#' * 70}")
            print(f"  ROUND {round_num}")
            print(f"{'#' * 70}\n")

            all_passed = True
            for i, conv in enumerate(CONVERSATIONS):
                success = run_conversation(conv, i)
                if not success:
                    all_passed = False

                # Clear session between conversations
                try:
                    requests.post(f"{BASE}/api/session/clear", timeout=5)
                    print("  [Session cleared]\n")
                except Exception:
                    print("  [Session clear failed — continuing]\n")

                time.sleep(2)

            if all_passed:
                print(f"\n✓ ROUND {round_num} COMPLETE — ALL CONVERSATIONS PASSED\n")
            else:
                print(f"\n⚠ ROUND {round_num} COMPLETE — SOME FAILURES\n")

            print("Starting next round in 5 seconds... (Ctrl+C to stop)")
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n\nStopped after {round_num} round(s).")

        # Final status dump
        print("\n── FINAL STATUS ──")
        status = check_status()
        if isinstance(status, dict) and "error" not in status:
            print(f"State: {status.get('state')}")
            print(f"Uptime: {status.get('uptime_seconds', 0):.0f}s")
            ag = status.get("agentic", {})
            print(f"Total tasks: started={ag.get('tasks_started')} completed={ag.get('tasks_completed')}")
            print(f"Direct: {ag.get('direct_responses')} | Planned: {ag.get('planned_responses')}")


if __name__ == "__main__":
    main()
