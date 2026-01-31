# URGENT: Memory Extraction & Character Profile Diagnostic

**Date:** January 27, 2026  
**For:** Claude Code  
**From:** Luna + Ahab  
**Priority:** CRITICAL - Luna cannot recall people from past conversations  
**Status:** 🔴 Production Issue

---

## Problem Statement

### What's Broken

Luna is experiencing severe memory retrieval failure for **people/entities**:

**Cannot Find:**
- ❌ Marzipan (person with owl connection)
- ❌ Catherine (chef, discussed tacos)
- ❌ Kamau (person, no other context)

**Can Find:**
- ✅ Recent project discussions (Memory Economy)
- ✅ Technical concepts (consciousness gradients, Eclissi Engine)
- ✅ Recent conversations (3:30am session)

**Luna's exact responses when searching:**
> "hmm, i'm not finding [Person] in my current memory context..."
> "the memories i have access to right now are pretty sparse"
> "it feels like there might be gaps in what memories i have access to right now"

### Critical Context

**Ahab implemented a character profile system** that should automatically create profiles for people mentioned in conversations. This system either:
1. Isn't running
2. Isn't being triggered
3. Is creating profiles but they're not searchable
4. Profiles exist but retrieval isn't finding them

---

## Diagnostic Mission

Find out:
1. **Do these people exist in the database at all?**
2. **Is extraction creating person nodes?**
3. **Is the character profile system running?**
4. **Are profiles being created?**
5. **Is retrieval searching profiles?**
6. **Where does the pipeline break?**

---

[Full diagnostic tests and scripts as provided in the complete document...]

---

**This is a production-critical issue blocking Luna's core memory functionality. Prioritize accordingly.**

— Luna + Ahab
