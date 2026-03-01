# Luna -- How It Works

## Architecture in One Paragraph

Zero-custodian AI. Every user's data lives in a local SQLite file. On-device FaceNet handles facial recognition -- no biometrics leave the device. No telemetry. No analytics callbacks. No cloud dependency for any core function. The architecture makes extraction structurally impossible, not just policy-prohibited.

## The Eclipse Model

Three sovereign layers:

- **Eclissi (the Sun):** Community knowledge. Governance protocols, elder teachings, land records, institutional memory. Owned by the community.
- **Luna (the Moon):** The AI mediator. Reflects knowledge to whoever needs it, when they need it. Doesn't own what it carries.
- **User (the Earth):** The individual. Their personal memories, conversations, relationships. Sovereign over their own data.

Each layer is independent. The Moon doesn't consume the Sun's light. It carries it.

## Key Components

**Memory Matrix** -- The substrate. SQLite database with memory nodes (FACT, INSIGHT, DECISION, ACTION, MILESTONE), weighted edges, and semantic search. Every node has a confidence score, importance weight, and lock-in coefficient that strengthens with corroboration.

**The Scribe** -- Extraction layer. Processes raw conversation into structured knowledge. Identifies entities, relationships, emotional content, and factual claims. Runs every conversational turn.

**The Librarian** -- Curation layer. Merges duplicate knowledge, resolves contradictions, strengthens connections between related nodes. Maintains the graph's coherence over time. Periodic background process.

**Director LLM** -- The language model layer. Receives curated context from the Memory Matrix, generates responses. The LLM is treated as a GPU -- a processing resource, not the brain. The memory is the brain. The LLM is the voice.

**Guardian** -- Community stewardship interface. Manages scope boundaries (personal, community, governance), consent protocols for knowledge sharing, and Traditional Knowledge labels. Ensures community knowledge stays under community authority.

## Sovereignty Guarantee

Three properties that cannot be removed without rebuilding from scratch:

1. **Local-first:** The SQLite file is the source of truth. Cloud is guest, not host.
2. **Inspectable:** Open the file. Read every memory. See every connection. No black boxes.
3. **Vendor-independent:** If we disappear tomorrow, the file still works. No license check. No phone-home. Permissive open-source.

## Deeper Detail

The Luna Engine Bible contains 13 chapters covering every layer in depth -- from philosophical foundations through system architecture, memory design, extraction protocols, performance benchmarks, and the sovereignty model. Available in the Luna Engine Bible subfolder.
