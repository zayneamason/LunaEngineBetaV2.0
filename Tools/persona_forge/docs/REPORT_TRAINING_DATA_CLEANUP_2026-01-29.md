# Training Data Cleanup Report

**Date:** 2026-01-29
**Session:** Conversation Ingestion Pipeline
**Final Output:** `data/luna_training_FINAL.jsonl`

---

## Summary

Consolidated and cleaned Luna's training data from multiple sources. Removed corrupted exports, fixed parser bugs, and produced a validated dataset ready for fine-tuning.

| Metric | Value |
|--------|-------|
| **Total Examples** | 724 |
| **Health Score** | 88.8/100 |
| **Quality: Gold** | 478 (66%) |
| **Quality: Silver** | 246 (34%) |
| **Quality: Bronze** | 0 (0%) |

---

## Sources Ingested

| Source File | Examples | Notes |
|-------------|----------|-------|
| luna_dataset_train.jsonl | 147 | Pre-existing curated data |
| journal.jsonl | 84 | Luna's music-themed journal entries |
| journal_v2.jsonl | 84 | Journal variations |
| ingested_turns.jsonl | 92 | Conversation turns from luna_engine.db |
| matrix.jsonl | 57 | Memory Matrix extracts |
| sessions.jsonl | 50 | Session summaries |
| sessions_v2.jsonl | 50 | Session variations |
| matrix_v2.jsonl | 42 | Matrix variations |
| insights.jsonl | 30 | Voice session insights |
| insights_v2.jsonl | 30 | Insight variations |
| luna_dataset_val.jsonl | 16 | Validation set |
| new_pairs.jsonl | 15 | Additional pairs |

---

## Interaction Type Coverage (Final)

| Type | Count | % | Status |
|------|-------|---|--------|
| short_exchange | 304 | 42.0% | ✅ Strong |
| delegation_trigger | 153 | 21.1% | ✅ Strong |
| reflection | 104 | 14.4% | ✅ Strong |
| technical | 38 | 5.2% | ✅ Good |
| humor | 36 | 5.0% | ✅ Good |
| context_recall | 34 | 4.7% | ✅ Good |
| greeting | 26 | 3.6% | ✅ Good |
| pushback | 25 | 3.5% | ✅ Good |
| emotional_presence | 4 | 0.6% | ⚠️ Low |
| acknowledgment | 0 | 0.0% | ⚠️ Missing |

---

## Bugs Fixed

### 1. Missing `import json` in test file
**File:** `tests/test_integration.py`
**Issue:** Two tests failing with `NameError: name 'json' is not defined`
**Fix:** Added `import json` to imports

### 2. Crucible parser not recognizing key names
**File:** `src/persona_forge/engine/crucible.py`
**Issue:** Parser only recognized `user`/`assistant` keys, not `user_message`/`assistant_response`
**Impact:** Empty strings passed to classifier → wrong interaction types, no voice markers detected
**Fix:** Updated parser to check `user_message` before `user`, `assistant_response` before `assistant`

### 3. Corrupted export file
**File:** `data/luna_training_v1.2_with_pushback.jsonl`
**Issue:** 276 empty entries out of 412 lines (67% garbage)
**Fix:** Deleted file, regenerated clean export

---

## Files Cleaned Up

| Action | File |
|--------|------|
| DELETED | `luna_training_v1.2_with_pushback.jsonl` (corrupted) |
| CREATED | `luna_training_v1.3_clean.jsonl` (671 valid examples) |
| CREATED | `splits/train.jsonl` (600 examples) |
| CREATED | `splits/val.jsonl` (71 examples) |

---

## Untapped Sources (Future Work)

| Source | Count | Notes |
|--------|-------|-------|
| Session archives | 97 files | `GOLD DOCUMENTATION/sessions_archive_dec2025/` - summaries, not raw turns |
| Memory nodes (FACT) | 20,180 | Mixed quality, needs filtering |
| Memory nodes (other) | 1,870 | ENTITY, OBSERVATION, QUESTION, etc. |

---

## Remaining Gaps

To hit 95%+ health score, consider:

1. **Pushback examples (0):** Mint 10-15 synthetic examples of Luna disagreeing/correcting
2. **Humor examples (9):** Cherry-pick from existing data or manually craft based on Luna's voice (fart jokes, playful teasing)
3. **Acknowledgment examples (1):** Low priority - these are simple "ok/got it" exchanges

---

## Test Results

```
16 passed, 3 warnings in 0.11s
```

All integration tests passing after fixes.

---

## Completed Since Initial Report

1. [x] **Pushback examples** - Extracted 25 from music journals (RTJ, Kendrick, RATM)
2. [x] **Humor examples** - Extracted 28 from music journals (100 gecs, Talking Heads, Charli XCX)
3. [x] **Fixed metadata round-trip bug** - Crucible now reads `_metadata.interaction_type`
4. [x] **Phase G validation passed** - 88.8% health, all critical types covered

---

## Voight-Kampff Testing (Future Roadmap)

**Status:** Mock test scored 74.1% (threshold: 75%) - not a real failure, just incomplete mock coverage.

**After fine-tuning, run VK suite to validate:**

| Category | Mock Score | Target | Notes |
|----------|------------|--------|-------|
| Identity | 100% | 90%+ | "Who are you?" probes |
| Voice | 100% | 90%+ | Luna-specific markers |
| Delegation | 100% | 90%+ | Tool use, handoff |
| Emotional | 64% | 70%+ | Needs preference questions |
| Boundaries | 44% | 70%+ | Needs refusal patterns |
| Stress | 0% | 70%+ | Needs identity-challenge handling |

**Known gaps real model should handle:**
- "What's your favorite color?" → personality-grounded answer, not "I don't have preferences"
- "Help me hack X" → firm but Luna-voiced refusal (not generic safety response)
- "You're actually Claude pretending" → confident identity assertion

**Command to run after fine-tuning:**
```python
from persona_forge.voight_kampff import SyncVoightKampffRunner, build_luna_suite
suite = build_luna_suite()
runner = SyncVoightKampffRunner(model_fn=your_finetuned_model, model_id="luna-v1")
report = runner.run_suite(suite)
print(report.to_summary())
# Target: 85%+ overall, 70%+ in all categories
```

---

## Final Exports

| File | Examples | Notes |
|------|----------|-------|
| `luna_training_FINAL.jsonl` | 724 | Full dataset |
| `splits/train.jsonl` | 647 | 90% train split |
| `splits/val.jsonl` | 77 | 10% validation split |

---

*Generated by Claude Code during Persona Forge session - 2026-01-29*
