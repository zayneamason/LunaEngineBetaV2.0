# See full spec: output file ENTITY-INGESTER-ARCHITECTURE.md
# This is the companion to CLAUDE-CODE-HANDOFF-QUEST-BOARD.md

# TL;DR: Three-pass pipeline to backfill 4,316 nodes → entities
# Pass 1: Pattern scan → LLM verify → human review
# Pass 2: Gather mentions → LLM synthesize profiles → human review  
# Pass 3: Co-occurrence → LLM classify relationships → human review
# Post: maintenance_sweep() → initial quest batch
# Always run in sandbox first. Never touch production directly.
