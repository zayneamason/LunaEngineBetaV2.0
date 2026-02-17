# See the full handoff in Claude's output file
# Quick reference pointer — the detailed spec is in the output below

# TL;DR:
# 1. Add entity tables (entities, entity_relationships, entity_mentions, entity_versions)
# 2. Add quest tables (quests, quest_targets, quest_journal)
# 3. Fix lock-in drifting threshold: 0.30 → 0.20
# 4. Build maintenance_sweep() — graph health → quest generation
# 5. Frontend: EntityGraphView (two-layer), QuestBoard, Journal, EntityDetail
# 6. Restore lock-in visualization everywhere (rings, colors, breathing animation)
# 7. Seed data from quest_habit_v3.jsx artifact

# Build order: Schema → Entity CRUD → Maintenance Sweep → Quest Lifecycle → Seed → Frontend
