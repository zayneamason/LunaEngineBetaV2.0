# HANDOFF: Project Eclipse Data Room — Archive & Fresh Start

**Date:** February 27, 2026
**Author:** Ahab (via creative direction session)
**Priority:** High
**Supersedes:** All prior handoffs (V1 and V2)

---

## What's Happening

We're archiving the entire data room and starting from zero. The existing documents — including the 7 drafts from the last handoff — are built on inconsistent legacy framing. Different documents contradict each other in tone, naming, and vision. Reorganizing won't fix a coherence problem. We need a clean slate.

One document has the right voice: **Calvin's Playbook.** Everything in the rebuilt data room will radiate outward from it. New docs will be created one at a time, in conversation with Ahab, not auto-generated.

---

## Phase 1: Archive Everything

### Archive destination
```
Google Drive folder: currently named "Executive Summary"
ID: 1Y9TY7m5tR_iLQYKd0Q9X6zxRKX2RF8rN
```

Rename this folder to `_ARCHIVE — Pre-Reset (Feb 2026)` before starting.

### What to move into the archive

Move ALL of the following from the data room root into the archive folder:

**Room folders (move entire folders with contents):**
- `0 — Demo/` (contains: 00 — Demo README)
- `1 — What Is Luna/` (contains: 01 — Luna: What Is It)
- `2 — Traction & Partnerships/` (contains: 02 — Traction & Milestones, plus any migrated LOIs)
- `3 — Team/` (contains: 03 — The Team, plus any migrated team docs)
- `4 — Technology/` (contains: 04 — Luna: How It Works, Luna Engine Bible subfolder)
- `5 — Financials/` (contains: 05 — Financial Overview, Cap Table Draft, plus cost breakdowns)
- `6 — What We Need/` (contains: 06 — What We Need)
- `Reference Library/` (contains: any migrated reference docs)

**Stray items:**
- `4. Product/` (old Tapestry folder that survived cleanup)
- `Executive Summary` doc (placeholder)
- Any other loose files in the data room root

**Do NOT move:**
- `_INBOX/`
- `_INDEX/`
- `_CHANGELOG/`

### Create an archive index

After moving everything, create a Google Doc in the archive folder called `ARCHIVE INDEX` that lists every file and folder moved, with the note: "Nothing here is deleted. The 7 draft docs are superseded — do not use them as source material."

---

## Phase 2: Reset the Data Room

After archiving, the data room should contain ONLY:

```
[Project Eclipse] Data Room/
├── _INBOX/
├── _INDEX/
└── _CHANGELOG/
```

### Recreate room folders (empty):

```
0 — Demo
1 — What Is Luna
2 — Proof
3 — Team
4 — How It Works
5 — The Money
6 — What We Need
Deep Cuts
```

Name changes from prior structure:
- "Traction & Partnerships" → **Proof**
- "Technology" → **How It Works**
- "Financials" → **The Money**
- "Reference Library" → **Deep Cuts**

### Update Code.gs

FOLDER_STRUCTURE categories:
```
'0 — Demo', '1 — What Is Luna', '2 — Proof', '3 — Team',
'4 — How It Works', '5 — The Money', '6 — What We Need', 'Deep Cuts'
```

PREFIX_ROUTES:
```
DEMO_ → 0, LUNA_ → 1, PROOF_ → 2, TEAM_ → 3,
TECH_ → 4, MONEY_ → 5, ASK_ → 6, DEEP_ → Deep Cuts
```

Run `setupDataRoom()` then `generateIndex()`.

---

## Phase 3: Rebuild — Section by Section

**DO NOT auto-generate documents.**

Each room gets built in conversation with Ahab. One at a time. Reviewed and approved before it goes in. Calvin's Playbook is the single source of truth.

| Room | Gateway Doc | Playbook Source | Supporting Files (from archive, if approved) |
|------|-------------|-----------------|----------------------------------------------|
| 0 — Demo | What You're Looking At | N/A — demo guide | Kinoni seed database, teaser video |
| 1 — What Is Luna | Luna | "Start Here" + "What Makes Luna Different" | Trust Architecture PDF |
| 2 — Proof | What's Real | "The Proof" | LOIs, Kinoni analytics |
| 3 — Team | The Team | "Who's the team?" | Zayne portfolio, Tarcila & Calvin PDF |
| 4 — How It Works | How It Works | Layer 1 pitch | Luna Engine Bible |
| 5 — The Money | The Money | From cost xlsx files | Cost breakdowns, build proposal |
| 6 — What We Need | What We Need | "The Ask" | Nothing. The close. |
| Deep Cuts | No gateway | N/A | Legacy docs for deep divers |

### Process:
1. Work through content in conversation
2. Ahab reviews and approves
3. Create as Google Doc in target folder
4. Pull supporting files from archive ONLY if approved
5. Run `generateIndex()`

---

## What NOT to Do

- Do not use legacy docs (Strategic Plan, Internal Brief, LUNA Proposal) as source material
- Do not auto-generate all docs at once
- Do not pull files from archive without explicit approval
- Do not add anything that doesn't serve the person reading it
