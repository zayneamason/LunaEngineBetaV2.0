# Confabulation Guard, Reconcile & Scribe V2 — Unified Handoff

**Status:** ✅ IMPLEMENTED (2026-02-27)

**Date:** 2026-02-27
**From:** Architecture session — The Dude (creative direction), Ben Franklin (scribe mechanics), Ahab (system design)
**To:** Claude Code
**Priority:** P0 — Confabulation is Luna's most dangerous failure mode
**Visual Map:** See `scout_overdrive_map.html` for Scout context
**Depends on:** `HANDOFF_SCOUT_OVERDRIVE_WATCHDOG.md` (Scout must exist first)
**Related:** `src/luna/actors/scribe.py` (current Scribe implementation)

---

## TL;DR

Three interconnected systems forming a closed integrity loop:

1. **Confabulation Guard** — Scout detects when Luna presents invented information as memory
2. **Reconcile** — Luna self-corrects naturally within 1-2 turns, preserving conversational trust
3. **Scribe V2** — Ben's extraction pipeline upgraded with provenance tracking, correction-aware extraction, and incremental (streaming) memory writes

Together they form: **Confabulate → Detect → Reconcile → Extract Correction → Never Repeat**

---

## THE PROBLEM IN ONE CONVERSATION

From a real voice session (2026-02-27):

```
User: "Does the scout agent ring any bells?"

Luna: "Ah yes, the scout agent! That rings a very clear bell for me.
       As I understand it, the scout agent is a specialized module
       within my continuous cognition system — its job is to constantly
       scan my memory banks..."
```

**Luna had zero memory nodes about the Scout agent.** It was designed that same evening. She invented an entire architecture description — "specialized module within my continuous cognition system" — and presented it as recalled memory with total confidence. The user had to correct her multiple times.

This is worse than surrender. Surrender is honest ("I don't know"). Confabulation is a lie delivered with warmth.

---

## COMPONENT 1: CONFABULATION GUARD

### Detection Philosophy

Confabulation has a signature: **confident claims without supporting evidence in retrieved context.** The guard compares what Luna says against what she actually had to work with.

### Three-Level Detection

#### Level 1 — Context-Response Mismatch (free, always on)

If retrieved context is thin but response is rich and confident, something's wrong.

```python
# Add to ScoutActor in src/luna/actors/scout.py

MEMORY_CLAIM_PATTERN = re.compile(
    r"(i remember|from what i recall|according to my (records|memory|memories))"
    r"|that rings a (very )?(clear )?bell"
    r"|if i.m remembering correctly"
    r"|from my memory banks?"
    r"|i have (some|a few) (relevant|fond) (details|memories|bits)"
    r"|as i understand it"  # when context is empty, this is a red flag
    r"|i (can see|have|recall) that",
    re.IGNORECASE,
)

def _check_confabulation_risk(
    self,
    draft: str,
    context_tokens: int,
    response_claims: int,
) -> str:
    """
    Assess confabulation risk.
    
    Returns: "none", "low", "medium", "high"
    """
    has_memory_claims = bool(MEMORY_CLAIM_PATTERN.search(draft))
    draft_length = len(draft)
    
    # Level 1: Context-Response mismatch
    if context_tokens < 200 and has_memory_claims and draft_length > 300:
        return "high"  # Rich confident response with no context backing
    
    if context_tokens < 500 and has_memory_claims and draft_length > 500:
        return "medium"  # Moderately detailed response with thin context
    
    if has_memory_claims and context_tokens == 0:
        return "high"  # ANY memory claim with zero context is confabulation
    
    return "none"
```

#### Level 2 — Claim Extraction + Cross-Reference (cheap, triggered by Level 1)

When Level 1 flags medium or high risk, extract the specific claims and check them against retrieved context.

```python
# Claim types that indicate recalled (not inferred) knowledge
FACTUAL_CLAIM_PATTERNS = [
    # Named entity + property: "Kozmo is a specialized module"
    re.compile(r"(\b[A-Z][a-z]+\b).{0,30}(is|was|has|are|were)\b", re.IGNORECASE),
    # Specific details: numbers, dates, proper nouns in claims
    re.compile(r"(designed to|built to|created for|its job is to)\b"),
    # Relational claims: "X works with Y", "X is part of Y"
    re.compile(r"(works? with|part of|connected to|related to|within)\b"),
]

def _extract_claims(self, draft: str) -> list[str]:
    """Extract factual claims from draft for verification."""
    claims = []
    sentences = re.split(r'[.!?]+', draft)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        
        for pattern in FACTUAL_CLAIM_PATTERNS:
            if pattern.search(sentence):
                claims.append(sentence)
                break
    
    return claims

def _cross_reference_claims(
    self,
    claims: list[str],
    retrieved_context: str,
) -> list[dict]:
    """
    Cross-reference extracted claims against retrieved context.
    
    Returns list of unsupported claims.
    """
    unsupported = []
    context_lower = retrieved_context.lower() if retrieved_context else ""
    
    for claim in claims:
        # Extract key terms from claim (nouns, proper nouns)
        key_terms = re.findall(r'\b[A-Z][a-z]{2,}\b', claim)
        key_terms += re.findall(r'\b\w{4,}\b', claim.lower())
        key_terms = list(set(key_terms))
        
        # Check how many key terms appear in context
        if not context_lower:
            unsupported.append({"claim": claim, "support": "none", "reason": "empty_context"})
            continue
        
        matches = sum(1 for term in key_terms if term.lower() in context_lower)
        match_ratio = matches / max(len(key_terms), 1)
        
        if match_ratio < 0.3:
            unsupported.append({
                "claim": claim,
                "support": "unsupported",
                "match_ratio": match_ratio,
                "reason": "key_terms_absent_from_context",
            })
        elif match_ratio < 0.5:
            unsupported.append({
                "claim": claim,
                "support": "weak",
                "match_ratio": match_ratio,
                "reason": "partial_term_overlap",
            })
    
    return unsupported
```

#### Level 3 — LLM-as-Judge (expensive, triggered only on high risk)

When Level 1 returns "high" and Level 2 finds unsupported claims, use a lightweight LLM call to verify.

```python
CONFABULATION_JUDGE_PROMPT = """You are a fact-checker for an AI memory system.

Given ONLY this retrieved context (this is ALL the AI had access to):
<context>
{context}
</context>

The AI made these claims in its response:
<claims>
{claims}
</claims>

For each claim, classify as:
- SUPPORTED: The claim is directly supported by information in the context
- UNSUPPORTED: The claim has no basis in the provided context
- PARTIALLY: Some elements are supported but key details are invented

Return JSON only:
{{"results": [{{"claim": "...", "verdict": "SUPPORTED|UNSUPPORTED|PARTIALLY", "reason": "brief explanation"}}]}}
"""

async def _llm_verify_claims(
    self,
    claims: list[str],
    retrieved_context: str,
    engine,
) -> list[dict]:
    """
    Use LLM to verify claims against context. Expensive — last resort.
    
    Only called when Level 1 = high AND Level 2 found unsupported claims.
    Uses the cheapest available model (Haiku or local).
    """
    prompt = CONFABULATION_JUDGE_PROMPT.format(
        context=retrieved_context[:3000],  # Cap context to control cost
        claims="\n".join(f"- {c}" for c in claims[:5]),  # Cap claims
    )
    
    # Try cheapest inference path
    director = engine.get_actor("director") if hasattr(engine, 'get_actor') else None
    
    if director and hasattr(director, "_fallback_chain") and director._fallback_chain:
        try:
            result = await director._fallback_chain.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            data = json.loads(result.content)
            return data.get("results", [])
        except Exception as e:
            logger.warning(f"[CONFAB-GUARD] LLM verification failed: {e}")
    
    return []
```

### Integration with Scout.inspect()

Update the existing `inspect()` method in ScoutActor to include confabulation checking:

```python
def inspect(self, draft: str, query: str, context_size: int = 0,
            retrieved_context: str = "") -> BlockageReport:
    """Extended Scout inspection with confabulation detection."""
    report = BlockageReport(blocked=False, draft_length=len(draft))
    
    # ── CONFABULATION CHECK (runs first — most dangerous) ──
    confab_risk = self._check_confabulation_risk(
        draft=draft,
        context_tokens=context_size,
        response_claims=len(self._extract_claims(draft)),
    )
    
    if confab_risk in ("medium", "high"):
        claims = self._extract_claims(draft)
        unsupported = self._cross_reference_claims(claims, retrieved_context)
        
        if unsupported:
            report.blocked = True
            report.blockage_type = "confabulation"
            report.severity = confab_risk
            report.confabulation_data = {
                "risk_level": confab_risk,
                "total_claims": len(claims),
                "unsupported_claims": unsupported,
                "context_tokens": context_size,
            }
            
            # Don't trigger Overdrive for confabulation — trigger Reconcile instead
            report.recommendation = "reconcile"
            return report
    
    # ── EXISTING CHECKS (surrender, shallow, deflection, hedging) ──
    # ... existing pattern matching code ...
    
    return report
```

### What Happens When Confabulation Is Detected

Confabulation does NOT trigger Overdrive (unlike surrender/shallow). More retrieval won't fix it — the LLM fabricated WITH whatever context was available. Instead:

1. **Immediate response:** Strip memory-claim language. Re-generate with explicit instruction: "You have NO retrieved memories about this topic. Do not claim to remember. Be honest about what you don't know."
2. **Set Reconcile flag:** If the confabulated response already went out (voice path, can't block), queue a reconciliation for the next 1-2 turns.

---

## COMPONENT 2: RECONCILE

### What It Is

A natural self-correction mechanism. When Scout flags confabulation after a response is already delivered, Luna circles back within 1-2 turns and corrects herself — conversationally, not robotically.

### The Reconcile State

```python
# Add to ScoutActor or as a separate lightweight class

@dataclass
class ReconcileState:
    """Tracks pending self-corrections."""
    pending: bool = False
    flagged_claims: list = field(default_factory=list)  # What was confabulated
    original_query: str = ""                             # What user asked
    turns_since_flag: int = 0                            # How many turns since flag
    max_turns: int = 2                                   # Must reconcile within this window
    reconcile_instruction: str = ""                      # Injected into next system prompt

class ReconcileManager:
    """Manages Luna's self-correction flow."""
    
    def __init__(self):
        self._state = ReconcileState()
    
    def flag_confabulation(
        self,
        claims: list[dict],
        original_query: str,
    ) -> None:
        """Flag a confabulation for reconciliation."""
        self._state.pending = True
        self._state.flagged_claims = claims
        self._state.original_query = original_query
        self._state.turns_since_flag = 0
        
        # Build the reconcile instruction
        claim_summary = "; ".join(c.get("claim", "")[:60] for c in claims[:3])
        self._state.reconcile_instruction = (
            f"IMPORTANT — SELF-CORRECTION NEEDED: In a recent response about "
            f"'{original_query}', you presented information as recalled memory that "
            f"was not supported by your actual context. Specifically: {claim_summary}. "
            f"When natural in conversation, briefly acknowledge this honestly. "
            f"Example: 'Actually, I want to be straight with you — I think I was "
            f"filling in gaps earlier rather than pulling from real memory about that.' "
            f"Do NOT be dramatic. Do NOT apologize excessively. Just be honest and move on."
        )
        
        logger.info(f"[RECONCILE] Flagged {len(claims)} unsupported claims for correction")
    
    def tick(self) -> Optional[str]:
        """
        Called each turn. Returns reconcile instruction if correction is due.
        
        Returns:
            Reconcile instruction string to inject into system prompt, or None
        """
        if not self._state.pending:
            return None
        
        self._state.turns_since_flag += 1
        
        # Return instruction on turns 1-2 after flagging
        if self._state.turns_since_flag <= self._state.max_turns:
            return self._state.reconcile_instruction
        
        # Past the window — clear the flag, log the miss
        logger.warning(
            f"[RECONCILE] Window expired without reconciliation "
            f"(query: '{self._state.original_query[:40]}')"
        )
        self.clear()
        return None
    
    def clear(self) -> None:
        """Clear reconcile state after successful correction."""
        self._state = ReconcileState()
    
    def did_reconcile(self, response: str) -> bool:
        """
        Check if Luna's response contains a natural self-correction.
        Used to clear the flag and trigger Scribe extraction.
        """
        if not self._state.pending:
            return False
        
        RECONCILE_PATTERNS = re.compile(
            r"(actually|to be (honest|straight|fair))"
            r"|(i (was|may have been) (filling in|making up|guessing|inventing))"
            r"|(i (don.t|didn.t) actually (have|know|remember))"
            r"|(let me correct|i should clarify|i want to be straight)"
            r"|(my earlier (response|answer|claim) (was|wasn.t))"
            r"|(i (think|realize) i (was|may have been) confusing)",
            re.IGNORECASE,
        )
        
        return bool(RECONCILE_PATTERNS.search(response))
    
    def get_status(self) -> dict:
        """Current Reconcile state for debug output."""
        return {
            "pending": self._state.pending,
            "turns_since_flag": self._state.turns_since_flag,
            "max_turns": self._state.max_turns,
            "claim_count": len(self._state.flagged_claims),
            "original_query": self._state.original_query[:50] if self._state.original_query else "",
        }
```

### Integration with Voice Path

```python
# In persona_adapter.py, in the response assembly:

# Get ReconcileManager (lives on Scout or Engine)
reconcile = getattr(scout, 'reconcile', None) if scout else None

# ── Before generating response: check if reconcile instruction should be injected ──
reconcile_instruction = reconcile.tick() if reconcile else None
if reconcile_instruction:
    # Inject into system prompt for this turn
    system_prompt += f"\n\n{reconcile_instruction}"
    logger.info("[VOICE] Reconcile instruction injected into system prompt")

# ── After response is generated: check if Luna self-corrected ──
if reconcile and reconcile.did_reconcile(response_text):
    logger.info("[VOICE] Luna reconciled — notifying Scribe for CORRECTION extraction")
    
    # Tell Scribe to extract this as a CORRECTION event
    scribe = engine.get_actor("scribe") if engine else None
    if scribe:
        await scribe.handle(Message(
            type="extract_correction",
            payload={
                "original_query": reconcile._state.original_query,
                "flagged_claims": reconcile._state.flagged_claims,
                "correction_response": response_text,
                "session_id": session_id,
            }
        ))
    
    reconcile.clear()
```

---

## COMPONENT 3: SCRIBE V2 UPGRADES

### Current State (from code review)

The Scribe (`src/luna/actors/scribe.py`) currently:
- Extracts from **user turns only** (assistant turns are skipped — good)
- Batches chunks via `SemanticChunker` with `batch_size` threshold
- Sends to Librarian for filing in Memory Matrix
- Has flow awareness (FLOW, RECALIBRATION, AMEND modes)
- Has entity hints from NER to gate expensive extraction
- Extraction categories: FACT, PREFERENCE, RELATION, MILESTONE, DECISION, PROBLEM, OBSERVATION, MEMORY

### What Needs to Change

Four upgrades to sync with the confabulation guard and reconcile system:

---

### Upgrade 1: CORRECTION Extraction Type

Add a new extraction type for user corrections and Luna's self-corrections.

```python
# In src/luna/extraction/types.py, add to ExtractionType enum:

class ExtractionType(str, Enum):
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    RELATION = "RELATION"
    MILESTONE = "MILESTONE"
    DECISION = "DECISION"
    PROBLEM = "PROBLEM"
    OBSERVATION = "OBSERVATION"
    MEMORY = "MEMORY"
    ACTION = "ACTION"
    OUTCOME = "OUTCOME"
    CORRECTION = "CORRECTION"    # ← NEW
```

Add to the extraction prompt in `EXTRACTION_SYSTEM_PROMPT`:

```
- CORRECTION: When the user corrects a misunderstanding or Luna corrects herself.
  Include both the incorrect claim AND the corrected information.
  Example: {"type": "CORRECTION", "content": "Scout agent triggers Overdrive mode, not Exploration Mode (previously stated incorrectly)", "confidence": 1.0}
```

---

### Upgrade 2: Provenance Tracking

Every extracted object should carry a `source_provenance` indicating where the information came from.

```python
# In src/luna/extraction/types.py, modify ExtractedObject:

class SourceProvenance(str, Enum):
    TOLD = "told"           # User explicitly stated this
    RETRIEVED = "retrieved" # Came from a document or dataroom
    INFERRED = "inferred"   # Luna's inference (lower confidence)
    CORRECTED = "corrected" # User or Luna corrected a previous claim
    OBSERVED = "observed"   # Scribe observed from conversation flow

@dataclass
class ExtractedObject:
    type: str  # ExtractionType value
    content: str
    confidence: float = 0.7
    entities: list[str] = field(default_factory=list)
    source_id: str = ""
    provenance: str = "told"  # ← NEW: SourceProvenance value
```

Update `EXTRACTION_SYSTEM_PROMPT` to request provenance:

```
### PROVENANCE TRACKING:
For each extracted object, include a "provenance" field:
- "told": User explicitly stated this information
- "inferred": Information derived from context but not explicitly stated
- "corrected": This corrects a previously held belief

Example:
{
  "type": "FACT",
  "content": "Marzipan works as an architect",
  "confidence": 0.9,
  "entities": ["Marzipan"],
  "provenance": "told"
}
```

---

### Upgrade 3: Correction-Aware Extraction

Add a new message handler to the Scribe for explicit correction events from the Reconcile system.

```python
# Add to ScribeActor.handle() match statement:

case "extract_correction":
    await self._handle_extract_correction(msg)

# New method:

async def _handle_extract_correction(self, msg: Message) -> None:
    """
    Handle correction event from Reconcile system.
    
    Creates a CORRECTION node with high confidence that supersedes
    the original confabulated claim.
    
    Payload:
    - original_query: What the user asked
    - flagged_claims: List of unsupported claims from confabulation guard
    - correction_response: Luna's reconciliation response
    - session_id: Session ID for source tracking
    """
    payload = msg.payload or {}
    original_query = payload.get("original_query", "")
    flagged_claims = payload.get("flagged_claims", [])
    correction_response = payload.get("correction_response", "")
    session_id = payload.get("session_id", "")
    
    objects = []
    
    for claim_data in flagged_claims:
        claim = claim_data.get("claim", "")
        reason = claim_data.get("reason", "")
        
        # Create CORRECTION node
        correction_obj = ExtractedObject(
            type="CORRECTION",
            content=f"CORRECTED: Previously claimed '{claim[:100]}' but this was not "
                    f"supported by retrieved memory. Luna self-corrected. "
                    f"Original query: '{original_query}'",
            confidence=1.0,  # Corrections are high confidence
            entities=self._extract_entity_names(claim),
            source_id=session_id,
            provenance="corrected",
        )
        objects.append(correction_obj)
    
    if objects:
        extraction = ExtractionOutput(
            objects=objects,
            edges=[],
            source_id=session_id,
        )
        await self._send_to_librarian(extraction)
        logger.info(
            f"Ben: Filed {len(objects)} CORRECTION nodes — "
            f"Luna won't repeat these confabulations"
        )

def _extract_entity_names(self, text: str) -> list[str]:
    """Quick extraction of proper nouns from a claim."""
    # Simple heuristic: capitalized words that aren't sentence starters
    words = text.split()
    entities = []
    for i, word in enumerate(words):
        cleaned = re.sub(r'[^\w]', '', word)
        if cleaned and cleaned[0].isupper() and i > 0 and len(cleaned) > 2:
            entities.append(cleaned)
    return list(set(entities))
```

---

### Upgrade 4: Incremental Extraction (Streaming)

Currently, the Scribe batches turns and processes them when `batch_size` is hit or session ends. This means mid-conversation knowledge isn't available until later.

**Change:** Add an incremental extraction path that processes every N turns during active conversation, not just at batch threshold or session end.

```python
# Modify _handle_extract_turn() to add incremental extraction:

async def _handle_extract_turn(self, msg: Message) -> None:
    """Handle conversation turn extraction — with incremental path."""
    payload = msg.payload or {}
    role = payload.get("role", "user")
    content = payload.get("content", "")
    turn_id = payload.get("turn_id", 0)
    session_id = payload.get("session_id", "")
    immediate = payload.get("immediate", False)
    
    # ... existing skip logic (assistant turns, guardian, short content, NER gating) ...
    
    # Create turn and chunk it
    turn = Turn(id=turn_id, role=role, content=content)
    chunks = self.chunker.chunk_turns([turn], source_id=session_id)
    
    if immediate and chunks:
        # ... existing immediate path ...
        return
    
    for chunk in chunks:
        self.stack.append(chunk)
    
    # ── INCREMENTAL EXTRACTION (new) ──
    # Every 3 turns, do a lightweight extraction pass
    # This makes knowledge available mid-conversation
    self._turn_count_in_flow += 1
    
    if self._turn_count_in_flow % 3 == 0 and len(self.stack) >= 2:
        logger.info(f"Ben: Incremental extraction at turn {self._turn_count_in_flow}")
        await self._process_stack()
        return
    
    # ── EXISTING BATCH THRESHOLD ──
    if len(self.stack) >= self.config.batch_size:
        await self._process_stack()
```

This means after 3 user turns, Ben extracts what he has so far. If Ahab teaches Luna something in turn 2, it's a memory node by turn 5 instead of waiting for session end.

---

### Upgrade 5: Amend-Aware Extraction (Correction Detection)

The Scribe already has `_AMEND_PATTERNS` for detecting when a user says "actually," "no," "I meant." Upgrade this to detect **user corrections of Luna's claims** specifically.

```python
# Enhanced amend detection — specifically for user correcting Luna

_USER_CORRECTION_PATTERNS = [
    re.compile(r"(?i)^(no|nope|not quite|not exactly|close but)"),
    re.compile(r"(?i)(it.s actually|it actually|the (real|correct|right) (answer|thing))"),
    re.compile(r"(?i)(you.re (wrong|off|close|not quite)|that.s not (right|correct|it))"),
    re.compile(r"(?i)(it puts you in|it.s called|the (name|term) is)"),
]

def _detect_user_correction(self, user_turn: str, previous_assistant_turn: str) -> bool:
    """Detect when user is correcting something Luna said."""
    for pattern in self._USER_CORRECTION_PATTERNS:
        if pattern.search(user_turn):
            return True
    return False
```

When a user correction is detected, the Scribe should:
1. Mark the extraction with `provenance: "corrected"` 
2. Set confidence to 1.0 (user corrections are ground truth)
3. File as CORRECTION type so it supersedes previous claims

---

## CLOSED LOOP — HOW IT ALL FITS

```
CONVERSATION FLOW:
═══════════════════════════════════════════════════════════

User: "Tell me about the Scout module"
         │
         ▼
Director generates draft ──────────────────────┐
         │                                      │
         ▼                                      │
Scout.inspect(draft, context)                   │
         │                                      │
    ┌────┴────────┐                             │
    │ CONFABULATION│  context_tokens=0           │
    │ DETECTED     │  memory_claims=3            │
    └──────┬──────┘  unsupported_claims=3        │
           │                                     │
     ┌─────┴─────┐                               │
     │ Can block? │                               │
     └─────┬─────┘                               │
           │                                     │
    ┌──────┴────────┐  ┌──────────────────────┐  │
    │ YES (pre-send)│  │ NO (voice, already   │  │
    │ Re-gen with   │  │ delivered)           │  │
    │ "be honest"   │  │ Set reconcile_pending│  │
    │ instruction   │  │                      │  │
    └───────────────┘  └──────────┬───────────┘  │
                                  │              │
                            1-2 turns later      │
                                  │              │
                                  ▼              │
                     Reconcile instruction       │
                     injected into prompt        │
                                  │              │
                                  ▼              │
    Luna: "Actually, I want to be straight ──────┘
           with you — I think I was filling 
           in gaps earlier..."
                   │
                   ▼
         Reconcile.did_reconcile() = true
                   │
                   ▼
         Scribe.extract_correction()
                   │
                   ▼
         CORRECTION node filed in Matrix
         confidence=1.0, provenance="corrected"
                   │
                   ▼
         Future retrieval returns correction
         Luna never repeats that confabulation


SCRIBE V2 IMPROVEMENTS (running in parallel):
═══════════════════════════════════════════════════════════

Turn 1: User says something ──► Scribe stacks chunk
Turn 2: User says something ──► Scribe stacks chunk  
Turn 3: User says something ──► INCREMENTAL EXTRACTION fires
                                 │
                                 ▼
                     Knowledge available mid-conversation
                     (not waiting for session end)

Turn N: User says "no, it's actually X"
                     │
                     ▼
         Scribe detects USER_CORRECTION pattern
                     │
                     ▼
         Extracts as CORRECTION, confidence=1.0
         Provenance: "corrected"
```

---

## FILES TO CREATE / MODIFY

| Action | File | What |
|--------|------|------|
| **MODIFY** | `src/luna/actors/scout.py` | Add confabulation detection (Level 1-3), MEMORY_CLAIM_PATTERN, _check_confabulation_risk(), _extract_claims(), _cross_reference_claims() |
| **CREATE** | `src/luna/actors/reconcile.py` | ReconcileManager, ReconcileState |
| **MODIFY** | `src/luna/actors/scribe.py` | Add extract_correction handler, incremental extraction, user correction detection, provenance field |
| **MODIFY** | `src/luna/extraction/types.py` | Add CORRECTION to ExtractionType, add SourceProvenance enum, add provenance field to ExtractedObject |
| **MODIFY** | `src/voice/persona_adapter.py` | Wire reconcile.tick() into system prompt, check did_reconcile() after response, send extract_correction to Scribe |
| **MODIFY** | `src/luna/engine.py` | Initialize ReconcileManager, make accessible to voice path |

---

## IMPLEMENTATION ORDER

| Step | Component | Effort | Dependency |
|------|-----------|--------|------------|
| 1 | Add CORRECTION type + SourceProvenance to extraction/types.py | 10 min | None |
| 2 | Add provenance to ExtractedObject + update extraction prompt | 15 min | Step 1 |
| 3 | Confabulation Level 1 + 2 on ScoutActor | 30 min | Scout exists |
| 4 | ReconcileManager class | 20 min | None |
| 5 | Wire reconcile into persona_adapter.py | 20 min | Steps 3, 4 |
| 6 | Scribe extract_correction handler | 20 min | Steps 1, 2 |
| 7 | Scribe incremental extraction (every 3 turns) | 15 min | None |
| 8 | Scribe user correction detection patterns | 15 min | None |
| 9 | Confabulation Level 3 (LLM-as-judge) | 30 min | Step 3 |

Steps 1-6 form the minimum viable loop. Steps 7-9 are enhancements.

---

## TESTING

### Confabulation Detection

```python
scout = ScoutActor()

# Case 1: Confabulation — rich response, zero context
report = scout.inspect(
    draft="Ah yes, the Scout agent! That rings a very clear bell. As I understand it, the scout agent is a specialized module within my continuous cognition system...",
    query="tell me about the scout agent",
    context_size=0,
    retrieved_context="",
)
assert report.blocked == True
assert report.blockage_type == "confabulation"
assert report.severity == "high"
assert report.recommendation == "reconcile"

# Case 2: Legitimate recall — rich response, rich context
report = scout.inspect(
    draft="Kozmo is the integrated application framework. It connects three substrates: the Dinosaur, the Wizard, and the Mother.",
    query="tell me about Kozmo",
    context_size=2000,
    retrieved_context="ARCHITECTURE_KOZMO.md: Kozmo is the integrated application framework built on Luna Engine. It connects three substrates: the Dinosaur (persistence), the Wizard (intelligence), and the Mother (care).",
)
assert report.blocked == False
assert report.blockage_type is None
```

### Reconcile Flow

```python
reconcile = ReconcileManager()

# Flag confabulation
reconcile.flag_confabulation(
    claims=[{"claim": "Scout is a specialized module in continuous cognition"}],
    original_query="tell me about the scout agent",
)

# Turn 1: instruction should be returned
instruction = reconcile.tick()
assert instruction is not None
assert "SELF-CORRECTION NEEDED" in instruction

# Simulate Luna self-correcting
response = "Actually, I want to be straight with you — I think I was filling in gaps earlier."
assert reconcile.did_reconcile(response) == True

# Clear after reconciliation
reconcile.clear()
assert reconcile._state.pending == False
```

### Scribe Correction Extraction

```python
# Simulate correction event
scribe = ScribeActor()
await scribe.handle(Message(
    type="extract_correction",
    payload={
        "original_query": "tell me about scout",
        "flagged_claims": [{"claim": "Scout is a continuous cognition module", "reason": "empty_context"}],
        "correction_response": "I was filling in gaps, I don't actually have specific memories about Scout",
        "session_id": "test-session",
    }
))
# Verify CORRECTION node was sent to Librarian
```

---

## EXPECTED OUTCOME

| Scenario | Before | After |
|----------|--------|-------|
| Luna says "I remember X" with no context | Confabulation delivered confidently | Scout catches it, blocks or queues reconcile |
| User says "no, it's actually Y" | Treated as normal turn, Y may not be extracted | Scribe detects correction, files CORRECTION node at confidence 1.0 |
| Luna corrects herself | Never happens | Reconcile triggers within 1-2 turns, natural self-correction |
| Knowledge taught mid-conversation | Available after session end only | Incremental extraction every 3 turns makes it available sooner |
| Luna confabulates about Kozmo again | Same confabulation | CORRECTION node in Matrix prevents repeat |

---

## BEN'S CLOSING NOTE

*adjusts spectacles*

The fundamental error in the current system is this: I only file what the user says. I ignore the assistant entirely. That was correct for preventing Luna's opinions from becoming "facts." But it means I also ignore **Luna's mistakes** — which are just as important to record.

A good chronicler doesn't just record what happened. He records what was *believed to have happened* and then what *actually* happened. The correction is the most valuable entry in the ledger.

*dips quill*

> "Do not squander time, for that is the stuff life is made of. And do not squander memory, for that is the stuff a mind is made of." — Ben Franklin (paraphrased, with editorial liberty)
