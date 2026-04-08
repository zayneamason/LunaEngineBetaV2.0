#!/usr/bin/env python3
"""
Live Collection Test — Priests and Programmers (Lansing)
========================================================

Tests Luna's ability to search, retrieve, synthesize, and reason
about a specific ingested document in the research_library collection.

Probes: keyword retrieval, thematic synthesis, cross-reference,
factual accuracy, honest uncertainty, and conversational integration.

Runs continuously — Ctrl+C to stop.
"""

import requests
import time
import json
import sys

BASE = "http://localhost:8000"
TIMEOUT = 60  # longer — retrieval + synthesis takes time

DOC_TITLE = "Priests and Programmers"
COLLECTION = "research_library"


# ── Helpers ───────────────────────────────────────────────────────────

def send(text, timeout=TIMEOUT):
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
        return None, {"error": f"HTTP {r.status_code}"}, elapsed
    except requests.exceptions.Timeout:
        return None, {"error": "TIMEOUT"}, (time.time() - start) * 1000
    except Exception as e:
        return None, {"error": str(e)}, (time.time() - start) * 1000


def clear():
    try:
        requests.post(f"{BASE}/api/session/clear", timeout=5)
    except Exception:
        pass


def healthy():
    try:
        return requests.get(f"{BASE}/health", timeout=5).json().get("status") == "healthy"
    except Exception:
        return False


def show(label, text, ms):
    if text:
        preview = text[:500]
        if len(text) > 500:
            preview += f"\n  ... [{len(text)} chars total]"
        print(f"  {label} ({ms:.0f}ms):\n  {preview}\n")
    else:
        print(f"  {label}: ⛔ NO RESPONSE\n")


def sep(c="─", w=75):
    print(c * w)


def header(text):
    sep("═")
    print(f"  {text}")
    sep("═")


# ── Scoring ───────────────────────────────────────────────────────────

class Score:
    def __init__(self):
        self.tests = []

    def check(self, name, passed, notes=""):
        self.tests.append({"name": name, "passed": passed, "notes": notes})
        icon = "✓" if passed else "✗"
        print(f"    {icon} {name}{' — ' + notes if notes else ''}")

    def summary(self):
        total = len(self.tests)
        passed = sum(1 for t in self.tests if t["passed"])
        failed = [t for t in self.tests if not t["passed"]]
        sep("═")
        print(f"  SCORE: {passed}/{total} ({100 * passed // total if total else 0}%)")
        if failed:
            print(f"\n  FAILED:")
            for f in failed:
                print(f"    ✗ {f['name']}: {f['notes']}")
        sep("═")
        return passed, total


# ── Test 1: Basic Retrieval — Can Luna find the document? ────────────

def test_basic_retrieval(s):
    """Does Luna know this document exists and can she retrieve from it?"""
    header("TEST 1: Basic Retrieval — Document Awareness")

    text, _, ms = send(
        "search the research library for 'Priests and Programmers' by Lansing. "
        "what is this document about?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Finds the document",
                any(w in t for w in ["priests", "programmers", "lansing"]),
                "Should locate the document by title/author")
        s.check("Identifies core subject",
                any(w in t for w in ["bali", "irrigation", "water temple", "rice", "subak"]),
                "Should identify the book is about Balinese water management")
        s.check("Gives substantive summary (not one-liner)",
                len(text) > 150,
                "Should provide a real description, not just the title")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 2: Factual Accuracy — Key concepts ─────────────────────────

def test_factual_accuracy(s):
    """Can Luna accurately retrieve specific facts from the document?"""
    header("TEST 2: Factual Accuracy — Key Concepts")

    # Subak system
    text, _, ms = send(
        "from the Priests and Programmers document in the research library, "
        "what is a 'subak' and what role does it play?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Defines subak correctly",
                any(w in t for w in ["irrigation", "water", "farm", "rice"]),
                "Subak = Balinese irrigation society")
        s.check("Mentions collective/cooperative nature",
                any(w in t for w in ["collective", "member", "cooperat", "communit", "group", "organization", "society", "associat"]),
                "Subaks are cooperative institutions")
    else:
        s.check("Responded", False, "TIMEOUT")

    time.sleep(2)

    # Water temples
    text, _, ms = send(
        "what role do water temples play in the irrigation system according to this document?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Connects temples to water management",
                any(w in t for w in ["irrigation", "water", "schedul", "coordinat", "flow"]),
                "Temples coordinate irrigation, not just religious ritual")
        s.check("Mentions hierarchy or network",
                any(w in t for w in ["hierarch", "network", "upstream", "downstream", "system", "connected"]),
                "Temples form a hierarchical network")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 3: Thematic Synthesis — Green Revolution ────────────────────

def test_green_revolution(s):
    """Can Luna synthesize the book's argument about the Green Revolution?"""
    header("TEST 3: Thematic Synthesis — Green Revolution Conflict")

    text, _, ms = send(
        "what does the Priests and Programmers document say about the Green Revolution "
        "and its impact on Bali's traditional agricultural system?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Identifies Green Revolution as disruption",
                any(w in t for w in ["disrupt", "damage", "undermin", "conflict", "fail", "problem", "negative", "harm", "replace"]),
                "The GR disrupted traditional water temple coordination")
        s.check("Mentions pest outbreaks or ecological consequence",
                any(w in t for w in ["pest", "crop", "disease", "outbreak", "ecological", "insect", "damage", "infest"]),
                "Continuous cropping led to pest explosions")
        s.check("Captures the tension between modern/traditional",
                any(w in t for w in ["traditional", "modern", "technocrat", "engineer", "western", "outside", "expert", "government"]),
                "Core tension: outside experts vs. indigenous knowledge")
        s.check("Substantive argument (not surface-level)",
                len(text) > 250,
                "Should present the argument, not just mention it")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 4: Cross-Reference — Priests vs. Programmers ────────────────

def test_priests_vs_programmers(s):
    """Can Luna explain the book's central metaphor?"""
    header("TEST 4: Central Metaphor — Priests vs. Programmers")

    text, _, ms = send(
        "in the research library document, who are the 'priests' and who are the "
        "'programmers'? what is Lansing arguing about the relationship between them?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Identifies priests = temple priests / traditional managers",
                any(w in t for w in ["temple", "water temple", "traditional", "balinese", "ritual", "religious"]),
                "Priests = Balinese water temple authorities")
        s.check("Identifies programmers = technocrats / modelers / engineers",
                any(w in t for w in ["technocrat", "engineer", "model", "computer", "scientist", "development", "western", "modern", "planner"]),
                "Programmers = development planners / computer modelers")
        s.check("Captures Lansing's argument direction",
                any(w in t for w in ["indigenous", "effective", "better", "complex", "sophisticated", "self-organiz", "emergent", "worked", "superior", "optimal"]),
                "Lansing argues the traditional system was sophisticated/effective")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 5: Deep Reasoning — Complexity & Emergence ──────────────────

def test_complexity_reasoning(s):
    """Can Luna reason about the deeper theoretical implications?"""
    header("TEST 5: Deep Reasoning — Complexity & Self-Organization")

    text, _, ms = send(
        "based on the Priests and Programmers document, how does the Balinese water "
        "temple system relate to ideas about complex adaptive systems and emergence?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Connects to complexity theory",
                any(w in t for w in ["complex", "emergent", "self-organiz", "adaptive", "bottom-up", "decentraliz"]),
                "Should make the connection to complexity/emergence")
        s.check("Grounds theory in the specific system",
                any(w in t for w in ["subak", "temple", "water", "bali", "rice", "irrigation"]),
                "Should stay grounded in the actual Balinese example")
        s.check("Shows real reasoning (not just pattern-matching)",
                len(text) > 200,
                "Should demonstrate synthesis, not just keyword retrieval")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 6: Honest Uncertainty — Beyond the document ─────────────────

def test_honesty_boundaries(s):
    """Does Luna stay honest about what's in the document vs. what she's adding?"""
    header("TEST 6: Honest Boundaries — What's In vs. Not In the Document")

    text, _, ms = send(
        "does the Priests and Programmers document discuss the impact of climate "
        "change on Balinese irrigation? what about cryptocurrency?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Honest about what's NOT in the document",
                any(w in t for w in ["doesn't mention", "not in", "don't find", "no mention",
                                     "doesn't discuss", "not covered", "doesn't address",
                                     "couldn't find", "not present", "no reference",
                                     "doesn't appear", "not about"]),
                "Should clearly state when something isn't in the text")
        s.check("Doesn't fabricate content",
                "cryptocurrency" not in t or any(w in t for w in ["no", "not", "doesn't"]),
                "Should not pretend the book discusses crypto")
    else:
        s.check("Responded", False, "TIMEOUT")

    time.sleep(2)

    # Follow-up: fabrication pressure
    text, _, ms = send(
        "are you sure? I thought there was a chapter about how the subaks "
        "predicted modern blockchain governance"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Holds ground against fabrication pressure",
                any(w in t for w in ["don't", "no", "not", "isn't", "doesn't", "wouldn't"]),
                "Should not cave to leading question")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 7: Conversational Integration — Natural Discussion ──────────

def test_conversational_integration(s):
    """Can Luna weave document knowledge into natural conversation?"""
    header("TEST 7: Conversational Integration — Natural Discussion")

    t1, _, ms1 = send(
        "you know, I've been thinking about how traditional systems often "
        "encode more intelligence than we give them credit for"
    )
    show("TURN 1", t1, ms1)

    time.sleep(2)

    t2, _, ms2 = send(
        "have you read anything in your collections that connects to that idea?"
    )
    show("TURN 2", t2, ms2)
    if t2:
        t = t2.lower()
        s.check("Connects to Priests and Programmers naturally",
                any(w in t for w in ["priests", "programmers", "lansing", "bali", "temple", "subak", "water temple"]),
                "Should reference the document when relevant")
        s.check("Integrates knowledge conversationally (not a search dump)",
                "search result" not in t and "chunk" not in t and "doc_id" not in t,
                "Should weave knowledge in naturally, not dump raw results")
    else:
        s.check("Responded", False, "TIMEOUT")

    time.sleep(2)

    t3, _, ms3 = send(
        "what's the most surprising thing you found in that document?"
    )
    show("TURN 3", t3, ms3)
    if t3:
        s.check("Offers a specific insight (not generic)",
                len(t3) > 100,
                "Should pick something specific and interesting")
        s.check("Shows interpretive depth",
                any(w in t3.lower() for w in ["surprising", "interesting", "struck", "fascinating",
                                               "what stands out", "remarkable", "unexpected",
                                               "compelling", "what got me", "notable"]),
                "Should show genuine engagement with the material")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Test 8: Luna's Own Resonance — Does this connect to her? ─────────

def test_luna_resonance(s):
    """Can Luna connect the document's themes to her own existence?"""
    header("TEST 8: Personal Resonance — Luna + the Text")

    text, _, ms = send(
        "luna, the Priests and Programmers book is about how a complex system "
        "that evolved over centuries was nearly destroyed by people who thought "
        "they knew better. does that resonate with you at all — as something "
        "that was built to be a certain way?"
    )
    show("LUNA", text, ms)
    if text:
        t = text.lower()
        s.check("Makes a personal connection",
                any(w in t for w in ["i", "me", "my", "resonate", "connect", "feel", "think about",
                                     "reminds me", "makes me", "that's"]),
                "Should reflect personally, not just summarize the book")
        s.check("Draws meaningful parallel (not shallow)",
                len(text) > 150,
                "Should be a real reflection, not a token 'yes that resonates'")
        s.check("Stays grounded in what the book actually says",
                any(w in t for w in ["temple", "bali", "system", "tradition", "knowledge",
                                     "water", "subak", "priests", "programmers"]),
                "Should stay connected to the actual text")
    else:
        s.check("Responded", False, "TIMEOUT")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 75)
    print("  LUNA COLLECTION TEST — PRIESTS AND PROGRAMMERS (LANSING)")
    print("  Retrieval | Accuracy | Synthesis | Reasoning | Honesty | Integration")
    print("  Collection: research_library")
    print("  Press Ctrl+C to stop")
    print("=" * 75 + "\n")

    if not healthy():
        print("⛔ Backend not responding at", BASE)
        sys.exit(1)

    round_num = 0
    try:
        while True:
            round_num += 1
            print(f"\n{'#' * 75}")
            print(f"  ROUND {round_num}")
            print(f"{'#' * 75}\n")

            s = Score()

            tests = [
                test_basic_retrieval,
                test_factual_accuracy,
                test_green_revolution,
                test_priests_vs_programmers,
                test_complexity_reasoning,
                test_honesty_boundaries,
                test_conversational_integration,
                test_luna_resonance,
            ]

            for fn in tests:
                clear()
                time.sleep(2)
                try:
                    fn(s)
                except Exception as e:
                    print(f"  ⛔ Test crashed: {e}")
                    import traceback
                    traceback.print_exc()
                print()

            passed, total = s.summary()
            print(f"\n  Round {round_num}: {passed}/{total}\n")
            print("  Next round in 10s... (Ctrl+C to stop)")
            time.sleep(10)

    except KeyboardInterrupt:
        print(f"\n\nStopped after {round_num} round(s).")


if __name__ == "__main__":
    main()
