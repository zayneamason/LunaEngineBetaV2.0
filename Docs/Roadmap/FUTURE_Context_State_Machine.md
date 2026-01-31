# FUTURE: Context State Machine & LoRA Hot-Swap System

> **Status:** Archived for Future Implementation  
> **Phase:** Post-Persona Forge (Phase 3+)  
> **Dependencies:** Base personality LoRA, training data pipeline, local inference at 50+ tok/s  
> **Archived:** January 29, 2026

---

## Executive Summary

Context-aware state machine that hot-swaps LoRA adapters to modulate Luna's personality based on detected life context (professional, personal, creative, learning, deep work).

## Why This Is Archived (Not Abandoned)

**The architecture is sound.** The design correctly identifies:
- State-specific personality parameters via LoRA
- Memory scoping per context
- Tool availability filtering
- Delegation strategy variation

**But dependencies aren't ready:**
1. Local inference is 3 tok/s (need 50+)
2. Base personality LoRA doesn't exist yet
3. Training data pipeline (Persona Forge) not built
4. Can't modulate personality that doesn't exist

## What Can Be Extracted Now

If needed before full implementation:
- **Context detection logic** → Tag conversations by context
- **Memory scoping** → Filter Memory Matrix by context tags
- **Delegation strategies** → System prompt variation per context

This gets ~60% of value via prompt engineering before LoRA infrastructure exists.

## When To Revisit

After:
- [ ] Persona Forge ships (training data collection)
- [ ] Base Luna personality LoRA trained and validated
- [ ] Local inference hitting 50+ tok/s
- [ ] Mars College demo complete

## Quick Reference

**5 Context States:**
- Professional (efficient, technical, direct)
- Personal (warm, supportive, casual)
- Creative (playful, exploratory, encouraging)
- Learning (patient, clear, educational)
- Deep Work (ultra-brief, focus-preserving)

**Detection Signals:**
- Keywords (40%)
- Time of day (20%)
- Conversation history (20%)
- Active projects (10%)
- Explicit commands (100% override)

**Key Performance Targets:**
- Context detection: <50ms
- LoRA swap: <500ms
- Memory scope filter: <20ms

---

## Full Design Document

**See:** `STUDY_Luna_Context_State_Machine_Design.md` in project files (2253 lines)

Contains:
- Complete state definitions with personality configs
- Detection algorithm implementation
- LoRA training strategy & data collection
- Project Pipeline Manager design
- All 4 delegation strategy implementations
- Memory scoping architecture
- UI/UX mockups (React components)
- 10-week implementation roadmap
- Performance specs & storage requirements
- Research questions & experiments
- Future extensions (subcontexts, blending, location-aware)

