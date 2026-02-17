# PRODUCT SPEC: Luna for Google Workspace

**Created:** 2026-02-13
**Author:** The Dude (Creative Facilitation)
**For:** Ahab (Architecture), Tarcila (First User), Claude Code (Implementation)
**Status:** Vision + Phase 1 Spec
**Companion Doc:** `HANDOFF_DATAROOM_LUNA_INTEGRATION.md` (implementation details)

---

## 1. WHAT THIS IS

Luna for Google Workspace is a deployment pattern where Luna acts as a sovereign cognitive layer on top of Google's ecosystem. Luna observes, understands, and acts within Drive, Gmail, Calendar, Docs, and Sheets — while keeping all understanding local on the user's machine.

This is not an add-on. This is Luna doing what Luna does — being a companion that knows your world — applied to the workspace where knowledge workers actually live.

**One sentence:** Your AI understands your Google Workspace, runs on your machine, and never sends your data to anyone else's cloud.

---

## 2. WHY THIS MATTERS

Every existing "AI for Workspace" solution works the same way: upload your data to their servers, let their model process it, get answers back. Luna inverts this. The intelligence lives on your machine. Google is just the filing cabinet.

**For Project Tapestry specifically:**
- Proves the platform primitive thesis (Luna adapts to new substrates)
- Creates an immediately demonstrable product for investors
- Gives Tarcila a real tool for managing ops, grants, and partnerships
- Generates a repeatable deployment pattern for nonprofits and small teams

---

## 3. FIRST USER: TARCILA

### Why She's Perfect

Tarcila is an ops/grants manager, community bridge, and executive art director who lives in Google Workspace. Her daily reality:

- Drafting grant applications across multiple funders (Lacuna Fund, Hewlett, Rotary Global Grants)
- Managing partnership communications (Jero Wiku, Continental Council, Rotary Kinoni, EarthScale)
- Tracking deadlines, deliverables, and budgets across Project Tapestry
- Coordinating between technical (Ahab), spiritual (Hai Dai), and community (Kinoni) workstreams

She's not a developer. Luna for Workspace needs to work for her through the tools she already uses.

### What She Needs Luna To Do

**Grant Management:** Track grant status, surface deadlines, connect requirements to existing docs, help draft sections from existing materials.

**Partnership Coordination:** Remember who said what across email threads, surface action items from meeting notes, track LOI commitments against progress, flag gaps.

**Document Intelligence:** Find latest versions, pull together materials by topic, identify what's missing from applications.

### Demo Scenario

Tarcila says: "Luna, I need to prep for the Rotary grant application. What do we have and what's missing?"

Luna responds: "You've got the project overview, the Kinoni LOI, and the community needs assessment. You're missing a detailed budget, a sustainability plan for Year 2+, and measurable success criteria for Year 1. Want me to draft outlines for the missing pieces?"

That's the demo.

---

## 4. ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│                   USER'S MACHINE                     │
│                                                      │
│  ┌──────────────┐    ┌───────────────────────────┐  │
│  │ Luna Engine   │◄──►│ Luna Workspace Bridge     │  │
│  │ (Brain)       │    │ (FastAPI /api/workspace/*) │  │
│  │ Memory Matrix │    └───────────┬───────────────┘  │
│  │ Entity System │                │ HTTPS             │
│  └──────────────┘                │                   │
└──────────────────────────────────┼───────────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │     Google Cloud (Remote)      │
                    │  ┌──────────────────────────┐  │
                    │  │ Apps Script Connector     │  │
                    │  │ Drive/Gmail/Calendar/Docs │  │
                    │  │ Observe + Execute          │  │
                    │  └──────────────────────────┘  │
                    └────────────────────────────────┘
```

**Key principle:** Google is the hands. Luna is the brain. All intelligence stays local.

### New Node Types

| Node Type | Source | Content |
|-----------|--------|---------|
| DOCUMENT | Google Drive | File metadata + summary |
| EMAIL | Gmail | Subject, sender, key content, action items |
| EVENT | Calendar | Event details, attendees, notes |
| CONTACT | Gmail/Docs | Person metadata, relationship context |
| TASK | Derived | Action items extracted from emails/docs/meetings |

### Workspace Bridge Endpoints

```
POST /api/workspace/event     ← Apps Script sends events here
POST /api/workspace/query     ← User asks Luna about workspace
GET  /api/workspace/status    ← Health check / sync status
POST /api/workspace/action    ← Luna sends commands back to Apps Script
```

---

## 5. TARCILA'S DEPLOYMENT

### Phase 1: Hosted Bridge (Demo)

Ahab runs Luna Engine + Workspace Bridge. Tarcila's Apps Script connector points to Ahab's endpoint. Her workspace data flows through Luna's brain on Ahab-controlled infrastructure.

### Phase 2: Luna as a File (Full Sovereignty)

Tarcila runs Luna locally. Her AI, her file, her workspace intelligence.

### Interface Options for Tarcila

1. Luna chat web interface (exposed as web app)
2. Google Chat integration (Apps Script → Chat)
3. Google Sheet "command center" — type questions in cells, Luna responds in adjacent column

Option 3 is elegant for demo. Tarcila lives in Sheets. A smart spreadsheet that understands her workspace is immediately tangible.

---

## 6. BUILD PHASES

### Phase 1: Data Room Foundation (Current)
- Apps Script automation (sort, index, changelog)
- Luna DOCUMENT node ingestion
- User: Ahab only
- Effort: 1-2 days

### Phase 2: Workspace Bridge
- FastAPI `/api/workspace/*` endpoints
- Apps Script event watching + reporting
- EMAIL, EVENT, CONTACT node types
- User: Ahab testing
- Effort: 3-5 days

### Phase 3: Tarcila Demo
- Deploy accessible bridge
- Configure her Apps Script connector
- Seed workspace knowledge
- Build query interface
- User: Tarcila
- Effort: 2-3 days + 1 day setup

### Phase 4: Grant Assistant
- Grant management workflows
- Template-based doc generation
- Deadline tracking + proactive alerts
- Gap analysis
- User: Tarcila actively using
- Effort: 3-5 days

### Phase 5: Product Packaging
- Non-developer installation guide
- OAuth2 setup wizard
- Google Workspace Add-on packaging
- Luna file packaging for local deployment

---

## 7. THE PITCH NARRATIVE

> "We built an AI companion that runs locally and owns nothing about you. Then we pointed it at our own Google Workspace. Now our operations manager — who isn't technical — uses it to manage grants, track partnerships across three continents, and prep for investor meetings. The same architecture that manages our Google Drive will manage a community knowledge hub in rural Uganda. The platform doesn't change. The substrate does."

---

## 8. NON-NEGOTIABLES

1. **Sovereignty** — Intelligence stays local. Google is storage, not brain.
2. **Offline-first** — Luna answers from cached memory. Sync is periodic, not required.
3. **Inspectable** — Every node links back to its Google source.
4. **No extraction** — Summaries and metadata only.
5. **Tarcila-friendly** — If it requires a terminal, it's not ready.

---

## 9. OPEN QUESTIONS

1. Hosting for Tarcila's demo — Ahab's machine or small VPS?
2. Auth model — API key, OAuth, or shared secret for MVP?
3. Interface — Chat, Google Chat bot, or Sheet command center?
4. Scope — All of Tarcila's workspace or Project Tapestry only?
5. Timeline — Targeting ROSA Conference (March 2026)?

---

*The best technology disappears into the work. Tarcila shouldn't be thinking about Luna. She should be thinking about the grant.*

— The Dude
