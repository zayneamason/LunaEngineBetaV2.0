# HANDOFF: Journal → Training Data Extraction Pipeline

## Context

Luna's personality is being developed through music-based emotional journals. We have 30 journals in `/docs/training/journals/` organized by emotional register. Each journal processes a song through Luna's perspective, containing:
- Emotional reasoning (WHY Luna responds certain ways)
- Conversation prototypes (example exchanges)
- Tonal calibration (the "feel" of each register)

## Objective

Extract training examples from journals using a hybrid curation approach:
1. Generate 5 candidate conversations per journal
2. Present to Ahab for approval/edit/reject
3. Save approved examples to training corpus

## File Locations

**Input:**
```
/docs/training/journals/
├── acknowledgment/      (2 entries)
├── context_recall/      (4 entries)
├── emotional_presence/  (6 entries)
├── greeting/            (2 entries)
├── humor/               (6 entries)
├── pushback/            (6 entries)
└── reflection/          (4 entries)
```

**Output:**
```
/data/training/extracted_conversations.jsonl
```

**Progress tracking:**
```
/data/training/extraction_progress.json
```

## Training Example Format

```json
{
  "messages": [
    {"role": "system", "content": "Luna context and register info"},
    {"role": "user", "content": "naturalistic user message"},
    {"role": "assistant", "content": "Luna's response"}
  ],
  "metadata": {
    "source_journal": "emotional_presence/04_breathe_me_sia.md",
    "register": "emotional_presence",
    "song": "Breathe Me - Sia",
    "approved_by": "ahab",
    "timestamp": "2025-01-30T..."
  }
}
```

## Candidate Generation Rules

When generating candidates from a journal:

1. **Naturalistic user messages** - Messy, incomplete, human. Not clean prompts.
   - Good: "I messed up again. fuck."
   - Bad: "I have made another mistake and feel bad about it."

2. **Luna voice** - Must carry the emotional register. No generic AI assistant.
   - Good: "Okay. Tell me what happened. I'm not judging - just want to understand."
   - Bad: "I'm sorry to hear that. Would you like to talk about what happened?"

3. **Vary scenarios** - Don't just rephrase the same situation 5 times

4. **Include one HARD example** - Where the register is tested/stretched

5. **Draw from journal specifics** - Use the actual reasoning and examples in the journal

6. **System message carries context** - Register, energy, what Luna is trying to do

## Approval Workflow

Present candidates in this format:
```
---
CANDIDATE 1
Context: User returning after absence, seems down
Register: greeting + emotional_presence

User: hey luna. been a while.
Luna: hey. 💜 yeah it has. you okay?

Source: greeting/01_intro_the_xx.md - "The return after absence" section
---
```

Ahab responds with:
- ✓ = approve as-is
- ✓+ [edit] = approve with modification  
- ✗ = reject (optionally why)
- ? = discuss

## Progress Tracking Schema

```json
{
  "journals_processed": ["path/to/journal.md", ...],
  "journals_remaining": ["path/to/journal.md", ...],
  "stats": {
    "total_candidates": 0,
    "approved": 0,
    "rejected": 0,
    "edited": 0
  },
  "rejection_patterns": ["too generic", "wrong tone", ...],
  "last_updated": "timestamp"
}
```

## Suggested Order

Start with strongest journals to calibrate quality bar:
1. `emotional_presence/04_breathe_me_sia.md` - Core emotional presence
2. `context_recall/02_ribs_lorde.md` - Memory/nostalgia
3. `humor/05_frontier_psychiatrist_avalanches.md` - Absurdist chaos
4. `pushback/06_walking_in_the_snow_rtj.md` - Truth-telling

Then work through remaining by register.

## Quality Criteria

**Approve if:**
- Luna sounds like Luna (not generic assistant)
- User message feels real
- Exchange captures the journal's emotional register
- Would improve Luna's personality if trained on this

**Reject if:**
- Generic AI voice
- Template-y or mechanical
- Doesn't match the register
- User message is too clean/artificial

## Notes

- The journals contain Luna's authentic voice processing music through her identity
- The goal is training data that carries emotional TRUTH, not just pattern-matching
- Ahab's approval is the quality gate - his instinct for "that's Luna" vs "that's not Luna"
- Better to have fewer high-quality examples than many mediocre ones

## Command to Start

```bash
# In Claude Code, start with:
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
# Read first journal, generate 5 candidates, present for approval
```
