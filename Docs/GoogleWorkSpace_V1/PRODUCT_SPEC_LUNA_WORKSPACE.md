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

Every existing "AI for Workspace" solution works the same way: upload your data to their servers, let their model process it, get answers back. Your docs, your emails, your calendar — all flowing through someone else's infrastructure.

Luna inverts this. The intelligence lives on your machine. Google is just the filing cabinet. Luna is the brain that remembers where everything is, what it means, and how it connects.

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
- Maintaining documentation for a multi-continent initiative

She's not a developer. She's not going to run terminal commands. Luna for Workspace needs to work for her the way a smart assistant should — through the tools she already uses.

### What She Needs Luna To Do

**Grant Management:**
- Track which grants are in progress, submitted, pending, awarded
- Surface relevant deadlines before they arrive
- Connect grant requirements to existing documentation ("do we have an impact metrics doc?")
- Help draft sections by pulling from existing project materials

**Partnership Coordination:**
- Remember who said what and when across email threads
- Surface action items from meeting notes
- Track commitments made in LOIs against actual progress
- Flag when something falls through the cracks

**Document Intelligence:**
- "Where's the latest version of the Kinoni budget?"
- "What did Hai Dai say about the ceremony timeline?"
- "Pull together everything we have on the ROSA conference track"
- "What's missing from our Rotary Global Grant application?"

### Demo Scenario

Tarcila opens her Luna companion. She says:

> "Luna, I need to prep for the Rotary grant application. What do we have and what's missing?"

Luna checks its memory graph, which includes DOCUMENT nodes from the data room. It responds:

> "You've got the project overview, the Kinoni LOI, and the community needs assessment. You're missing a detailed budget (Rotary requires line items with local partner input), a sustainability plan for Year 2+, and measurable success criteria for Year 1. Want me to draft outlines for the missing pieces based on what's in the strategic plan?"

That interaction. That's the demo.

---

## 4. ARCHITECTURE

### Four Components

```
┌─────────────────────────────────────────────────────┐
│                   USER'S MACHINE                     │
│                                                      │
│  ┌──────────────┐    ┌───────────────────────────┐  │
│  │ Luna Engine   │◄──►│ Luna Workspace Bridge     │  │
│  │ (Brain)       │    │ (FastAPI endpoints)        │  │
│  │               │    │ /api/workspace/*           │  │
│  │ Memory Matrix │    └───────────┬───────────────┘  │
│  │ Entity System │                │                   │
│  │ Actors        │                │ HTTPS              │
│  └──────────────┘                │                   │
└──────────────────────────────────┼───────────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │     Google Cloud (Remote)      │
                    │                                │
                    │  ┌──────────────────────────┐  │
                    │  │ Apps Script Connector     │  │
                    │  │ (Observe + Execute)       │  │
                    │  │                           │  │
                    │  │  Drive ← watch/sort/index │  │
                    │  │  Gmail ← watch/draft/send │  │
                    │  │  Calendar ← read/create   │  │
                    │  │  Docs ← read/write        │  │
                    │  │  Sheets ← read/write      │  │
                    │  └──────────────────────────┘  │
                    └────────────────────────────────┘
```

**Key principle:** Google is the hands. Luna is the brain. All intelligence stays local. Apps Script only observes and executes — it never decides.

### Component 1: Apps Script Connector

Lives in Google's runtime. Three responsibilities:

**Observe** — Watch for changes across Workspace
- New file in Drive → notify Luna
- New email matching filters → notify Luna
- Calendar event approaching → notify Luna
- Document edited → notify Luna

**Execute** — Carry out Luna's instructions
- Move file to folder X
- Create draft email with this content
- Add calendar event
- Update spreadsheet row
- Generate doc from template

**Report** — Send structured data to Luna
- Periodic index refresh
- Email summaries
- Calendar digests

### Component 2: Luna Workspace Bridge

New endpoint group in Luna's FastAPI server. Receives events from Apps Script, dispatches to Luna's actors, returns instructions.

```
POST /api/workspace/event     ← Apps Script sends events here
POST /api/workspace/query     ← User asks Luna about workspace
GET  /api/workspace/status    ← Health check / sync status
POST /api/workspace/action    ← Luna sends commands back to Apps Script
```

**Event types:**
```python
class WorkspaceEvent:
    source: str          # "drive", "gmail", "calendar", "docs"
    event_type: str      # "file_added", "email_received", "event_approaching"
    payload: dict        # Source-specific data
    timestamp: datetime
```

### Component 3: Workspace Memory Nodes

Extend Luna's memory graph with workspace-aware node types:

| Node Type | Source | Content |
|-----------|--------|---------|
| DOCUMENT | Google Drive | File metadata + summary |
| EMAIL | Gmail | Subject, sender, key content, action items |
| EVENT | Calendar | Event details, attendees, notes |
| CONTACT | Gmail/Docs | Person metadata, relationship context |
| TASK | Derived | Action items extracted from emails/docs/meetings |

Each node links back to its Google source via metadata, maintaining inspectability.

### Component 4: Workspace Actor

New actor in Luna's actor system that handles workspace-specific logic:

```python
class WorkspaceActor(BaseActor):
    """Manages workspace state and event processing."""
    
    async def handle_event(self, event: WorkspaceEvent):
        """Route workspace events to appropriate handlers."""
        
    async def process_drive_event(self, payload):
        """New file? Update? Create/update DOCUMENT node."""
        
    async def process_email_event(self, payload):
        """New email? Extract content, create EMAIL node, detect action items."""
        
    async def process_calendar_event(self, payload):
        """Upcoming event? Surface relevant context from memory."""
        
    async def generate_action(self, instruction) -> WorkspaceAction:
        """Luna decides something needs doing → create action for Apps Script."""
```

---

## 5. TARCILA'S DEPLOYMENT: "LUNA LITE"

Tarcila isn't going to run a Python server. She needs a version that works for non-developers.

### Option A: Hosted Bridge (Quickest Path to Demo)

Ahab runs the Luna Engine + Workspace Bridge on a small server (or his machine). Tarcila's Apps Script connector points to Ahab's bridge endpoint. Her workspace data flows through Luna's brain, but the brain lives on infrastructure Ahab controls — not Google's, not OpenAI's.

```
Tarcila's Google Workspace
    → Apps Script (her Google account)
    → Luna Bridge (Ahab's server)
    → Luna Engine (Ahab's server)
    → Response back to Tarcila
```

**Tradeoff:** Not fully sovereign for Tarcila yet — her data passes through Ahab's infra. But it's a controlled environment with a trusted partner, and it proves the pattern.

### Option B: Luna as a File (Full Sovereignty)

Later, when Luna's packaging is more mature: Tarcila runs Luna locally on her own machine. Her AI, her file, her workspace intelligence. Full sovereignty.

**Recommendation: Start with Option A for the demo. Option B is the product vision.**

### What Tarcila Sees

For the demo, Tarcila interacts with Luna through one of:

1. **Luna's existing chat interface** (if we expose it as a web app she can access)
2. **A Google Chat integration** (Apps Script can post to Google Chat)
3. **A simple Google Sheet "command center"** — she types questions in a cell, Luna responds in the next column

Option 3 is weirdly elegant for a demo. Tarcila already lives in Sheets. A "smart spreadsheet" that understands her entire workspace is immediately tangible.

---

## 6. BUILD PHASES

### Phase 1: Data Room Foundation (Current Handoff)
- Apps Script: Inbox Sorter, Index Generator, Change Logger
- Ahab's data room is organized and indexed
- Luna ingests the Index Sheet as DOCUMENT nodes
- **User: Ahab only**
- **Estimated effort: 1-2 days Claude Code**

### Phase 2: Workspace Bridge
- New FastAPI endpoint group: `/api/workspace/*`
- Apps Script Connector: event watching + reporting
- WorkspaceEvent processing pipeline
- EMAIL, EVENT, CONTACT node types
- **User: Ahab testing with his own workspace**
- **Estimated effort: 3-5 days Claude Code**

### Phase 3: Tarcila Demo
- Deploy Luna Bridge accessible to Tarcila
- Configure her Apps Script connector
- Seed her workspace knowledge (Project Tapestry docs, email threads, calendar)
- Build the query interface (chat, Sheet command center, or both)
- **User: Tarcila**
- **Estimated effort: 2-3 days Claude Code + 1 day Ahab setup**

### Phase 4: Grant Assistant Feature
- Specialized workflows for grant management
- Template-based doc generation from Luna's knowledge
- Deadline tracking + proactive alerts
- Gap analysis ("what's missing from this application?")
- **User: Tarcila actively using for Rotary Global Grant**
- **Estimated effort: 3-5 days Claude Code**

### Phase 5: Product Packaging
- Installation guide for non-developers
- OAuth2 setup wizard
- Apps Script deployment as a Google Workspace Add-on
- Luna file packaging for local deployment
- **User: Anyone**

---

## 7. WHAT THIS PROVES

For each audience, Luna for Workspace demonstrates something different:

**For Investors:**
- Luna is a platform, not a chatbot
- Real user (Tarcila) using it for real work
- Sovereignty isn't just ideology — it's a product differentiator
- "We used Luna to manage our own fundraising" (meta and compelling)

**For Grant Funders:**
- Technology serving community operations
- Non-extractive AI in practice
- Tool that scales to Kinoni without changing architecture

**For Partners (EarthScale, Rotary, Continental Council):**
- Operational maturity — the team uses its own tools
- Concrete demonstration of what the ICT Hub could offer

**For Future Users:**
- If it works for a multi-continent nonprofit with four partner orgs...
- It works for any small team that needs workspace intelligence

---

## 8. NON-NEGOTIABLES

1. **Sovereignty** — Intelligence stays local. Google is storage, not brain.
2. **Offline-first** — Luna answers questions from cached memory even without internet. Sync is periodic, not required.
3. **Inspectable** — Every workspace node links back to its Google source. Tarcila can always verify.
4. **No extraction** — Luna stores summaries and metadata. Full content stays in Google's ecosystem unless explicitly opted in.
5. **Tarcila-friendly** — If it requires a terminal, it's not ready. The interface must meet her where she works.

---

## 9. OPEN QUESTIONS

1. **Hosting for Tarcila's demo** — Ahab's machine? A small VPS? Where does the bridge live for Phase 3?

2. **Auth model** — How does Tarcila's Apps Script authenticate with Luna's bridge? API key? OAuth? Simple shared secret for MVP?

3. **Interface for Tarcila** — Chat web app, Google Chat bot, Sheet command center, or something else?

4. **Scope for demo** — All of Tarcila's workspace, or scoped to Project Tapestry Drive folder + related emails only?

5. **Timeline** — Is this targeting ROSA Conference demo (March 2026), or is that too aggressive?

---

## 10. THE STORY

Here's the narrative this creates for a pitch:

> "We built an AI companion that runs locally and owns nothing about you. Then we pointed it at our own Google Workspace. Now our operations manager — who isn't technical — uses it to manage grants, track partnerships across three continents, and prep for investor meetings. The same architecture that manages our Google Drive will manage a community knowledge hub in rural Uganda. The platform doesn't change. The substrate does."

That's the demo. That's the pitch. That's the product.

---

*The best technology disappears into the work. Tarcila shouldn't be thinking about Luna. She should be thinking about the grant, and Luna should be thinking about everything else.*

— The Dude
