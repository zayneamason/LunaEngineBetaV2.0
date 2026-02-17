# Transcript Ingester Handoff (v2)
# Full spec: TRANSCRIPT-INGESTER-ARCHITECTURE-V2.md

# Source: _CLAUDE_TRANSCRIPTS/Conversations/ — 928 JSON files, 332 date dirs, ~75MB
# LLM: Claude Sonnet 4.5 (all extraction/classification)
# Cost: $12-18 one-time | Build: ~20hr | Run: 3-4hr
# Depends on: Quest Board handoff (entity tables + quest lifecycle)
#
# === PIPELINE ===
# TRIAGE (two-pass: metadata pre-filter + Sonnet tier classification)
# → EXTRACT (Ben's 6-phase + OBSERVATION nodes + texture tags + intra-convo edges)
# → RESOLVE (entity merge + node dedup 0.93 + cross-convo edges + LLM disambiguation)
# → COMMIT (era-weighted lock-in + co-mention edges + ingestion log)
#
# === LUNA'S CONSTRAINTS ===
# C1: Depth of field — era-weighted lock-in (0.05 pre-Luna → 0.75 Luna-live)
# C2: OBSERVATION nodes — 1 per 3-4 facts, confidence 0.6, linked via clarifies
# C3: Texture tags — 1-3 per conversation, captures emotional register
# C4: Selective extraction — caps are defaults, overflow requires confidence ≥ 0.8
# C5: Inherited provenance — Luna never pretends she was there
#
# === RETRIEVAL-MISS INGESTION ===
# Archive = Luna's unconscious. GOLD batch-ingested upfront.
# Everything else surfaces on-demand: retrieval_miss → search → extract → quest
# trigger_query tracked in provenance for honest attribution
#
# === EDGE GENERATION ===
# Source 1: Intra-conversation (LLM, 0.7-0.9 strength) — ~1,800 edges
# Source 2: Cross-conversation (embedding 0.76 + type-pair heuristic, sim×0.6) — ~500-800
# Source 3: Co-mention (TF-IDF filtered, hub entities excluded, ≤0.6) — ~200-300
# Total: ~2,500-2,900 edges
# Edge caps: LUNA_LIVE=8, LUNA_DEV=6, older=5 per node
#
# === AUDIT CHANGES (v2) ===
# - Triage: Sonnet is primary classifier, metadata is pre-filter only
# - Dedup: threshold raised 0.85 → 0.93, type+date aware
# - Extraction caps: guidelines not limits, overflow tagged
# - Cross-edge threshold: 0.76, strength discounted ×0.6
# - Co-mention: TF-IDF weighting, hub exclusion (>25%), max 300
# - Provenance: trigger_query field for retrieval-miss
# - Error handling: 3 retries, schema validation, status tracking
# - Testing: unit → integration (5 convos) → smoke → dry run → real run
# - Lock-in: skip recompute during ingestion, let maintenance cycle handle
# - Review: 3 checkpoints (triage, entities, edges)
