# Scout Agent, Overdrive & Watchdog — Implementation Handoff

**Date:** 2026-02-27
**From:** Architecture session (Creative Direction + System Diagnostic)
**To:** Claude Code
**Priority:** P0 — Luna's primary defense against surrender, shallow recall, deflection, and stuck states
**Status:** ✅ **IMPLEMENTED** — ScoutActor + Overdrive + Watchdog live, wired into voice path
**Visual Map:** `scout_overdrive_map.html` (in project root)
**Depends on:** `HANDOFF_VOICE_AGENTIC_BRIDGE.md` (implemented), `HANDOFF_VOICE_AGENTIC_BRIDGE_FOLLOWUP.md`

---

## TL;DR

Three components, one system:

1. **Scout** — Actor that inspects Director's draft response for blockage patterns before delivery
2. **Overdrive** — Expanded retrieval with tiered weights, triggered by Scout, 60s cooldown
3. **Watchdog** — State handler that detects stuck states and forces reset to IDLE

No new dependencies. Uses existing SearchChainConfig, AgentLoop, ToolRegistry, BaseActor, and AgentStatus.

---

## WHY THIS EXISTS

Luna has three failure modes observed in voice conversations:

| Mode | Example | What Happened |
|------|---------|---------------|
| **Surrender** | "I don't have any memories about Kozmo" | Retrieval returned empty or never fired |
| **Shallow Recall** | "The details are a bit fuzzy... that's about all I can say" | Retrieval hit but token budget too tight |
| **Deflection** | "Can you tell me more about it? I'd love to learn!" | Luna asks user to teach her about her own project |

Additionally, the system can get stuck — AgentLoop times out, Director never returns, Overdrive fires but hangs. There's no recovery path. The Watchdog handles that.

---

## COMPONENT 1: SCOUT ACTOR

### What It Is

A new actor (`src/luna/actors/scout.py`) that extends BaseActor. Registered via `engine.register_actor()` alongside Director, Matrix, Scribe, Librarian.

Scout sits between draft generation and delivery. It reads the draft, pattern-matches for blockage, and either passes through or triggers Overdrive.

### Detection Patterns

Four blockage types, two severity levels:

```python
import re

class BlockageType:
    SURRENDER = "surrender"        # "I don't know" — severity HIGH
    SHALLOW = "shallow_recall"     # "details are fuzzy" — severity MEDIUM
    DEFLECTION = "deflection"      # asks user to teach her — severity HIGH
    HEDGING = "hedging"            # vague claims, no evidence — severity MEDIUM

# Surrender: Luna admits she has no information
SURRENDER_PATTERN = re.compile(
    r"i don.t have (any |specific )?(information|memory|memories|context|knowledge|details)"
    r"|tell me (more|a bit more)"
    r"|i.m not (sure|familiar)"
    r"|i don.t know (about|anything)"
    r"|not in my (memory|records|context)"
    r"|i.m afraid i don.t"
    r"|doesn.t ring (any )?bells?"
    r"|outside my (current )?knowledge",
    re.IGNORECASE,
)

# Shallow recall: Luna found something but not enough
SHALLOW_PATTERN = re.compile(
    r"details are (a bit |quite )?fuzzy"
    r"|i don.t have much more (concrete |specific )?(information|details)"
    r"|beyond that.{0,20}(i.m afraid|i don.t)"
    r"|that.s (about )?all i can (confidently |really )?(say|recall|remember)"
    r"|a bit out of the loop",
    re.IGNORECASE,
)

# Deflection: Luna asks user to teach her about her own stuff
DEFLECTION_PATTERN = re.compile(
    r"(can|could) you (tell|share|fill) me (more|in|a bit)"
    r"|i.d (love|be happy|be eager) to (learn|hear|know) more"
    r"|what can you (tell|share|teach) me about"
    r"|why don.t you fill me in"
    r"|i.m (all ears|listening closely|eager to learn)",
    re.IGNORECASE,
)

# Hedging: vague claims without evidence
HEDGING_PATTERN = re.compile(
    r"(it seems like|from what i can gather|if i recall correctly|i believe).{0,40}$"  # vague + short
    r"|some kind of.{0,30}(environment|platform|project|system|tool)",
    re.IGNORECASE,
)
```

### Scout Analysis Method

```python
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

@dataclass
class BlockageReport:
    """Result of Scout's draft inspection."""
    blocked: bool
    blockage_type: Optional[str] = None       # surrender, shallow_recall, deflection, hedging
    severity: str = "none"                     # none, medium, high
    overdrive_tier: int = 0                    # 0 = no overdrive, 1-3
    patterns_matched: List[str] = field(default_factory=list)
    draft_length: int = 0
    recommendation: str = "pass"              # pass, overdrive_t1, overdrive_t2, overdrive_t3

class ScoutActor(BaseActor):
    """
    Blockage detection agent. Inspects Director drafts before delivery.
    Triggers Overdrive when blockage detected. Manages cooldown state.
    """
    
    def __init__(self):
        super().__init__(name="scout")
        self._cooldown_until: Optional[datetime] = None
        self._cooldown_duration: float = 60.0  # seconds, default
        self._last_overdrive_tier: int = 0
        self._consecutive_blockages: int = 0   # tracks repeated failures across turns
    
    def inspect(self, draft: str, query: str, context_size: int = 0) -> BlockageReport:
        """
        Inspect a draft response for blockage patterns.
        
        Args:
            draft: The Director's draft response text
            query: The original user query (for context)
            context_size: How many chars of context were available to Director
        
        Returns:
            BlockageReport with blockage type, severity, and recommended tier
        """
        report = BlockageReport(blocked=False, draft_length=len(draft))
        
        # Check each pattern
        if SURRENDER_PATTERN.search(draft):
            report.patterns_matched.append("surrender")
        if SHALLOW_PATTERN.search(draft):
            report.patterns_matched.append("shallow_recall")
        if DEFLECTION_PATTERN.search(draft):
            report.patterns_matched.append("deflection")
        if HEDGING_PATTERN.search(draft) and len(draft) < 500:
            report.patterns_matched.append("hedging")
        
        if not report.patterns_matched:
            self._consecutive_blockages = 0
            return report  # Clean draft, pass through
        
        # Determine blockage type (priority order)
        report.blocked = True
        self._consecutive_blockages += 1
        
        if "surrender" in report.patterns_matched or "deflection" in report.patterns_matched:
            report.blockage_type = report.patterns_matched[0]
            report.severity = "high"
        else:
            report.blockage_type = report.patterns_matched[0]
            report.severity = "medium"
        
        # Determine Overdrive tier based on depth
        report.overdrive_tier = self._select_tier(report)
        report.recommendation = f"overdrive_t{report.overdrive_tier}"
        
        # Check cooldown — may downgrade tier
        if self._is_cooling():
            available_tier = self._available_tier()
            if report.overdrive_tier > available_tier:
                report.overdrive_tier = available_tier
                report.recommendation = f"overdrive_t{available_tier}" if available_tier > 0 else "pass_cooling"
        
        return report
    
    def _select_tier(self, report: BlockageReport) -> int:
        """Select Overdrive tier based on blockage depth."""
        # Tier 3: repeated blockages or entity mention + surrender
        if self._consecutive_blockages >= 3:
            return 3
        
        # Tier 2: full surrender or deflection
        if report.severity == "high":
            return 2
        
        # Tier 1: shallow recall or hedging
        return 1
    
    def _is_cooling(self) -> bool:
        """Check if Overdrive is in cooldown."""
        if self._cooldown_until is None:
            return False
        return datetime.now() < self._cooldown_until
    
    def _available_tier(self) -> int:
        """What tier is available during cooldown?"""
        if self._cooldown_until is None:
            return 3  # All tiers available
        
        elapsed = (datetime.now() - (self._cooldown_until - timedelta(seconds=self._cooldown_duration))).total_seconds()
        
        if elapsed < 20:    # 0-20s: COOLING — nothing available
            return 0
        elif elapsed < 50:  # 20-50s: WARMING — Tier 1 only
            return 1
        else:               # 50s+: READY — all tiers
            return 3
    
    def start_cooldown(self, tier_used: int):
        """Start cooldown after Overdrive fires."""
        from datetime import timedelta
        self._cooldown_until = datetime.now() + timedelta(seconds=self._cooldown_duration)
        self._last_overdrive_tier = tier_used
        logger.info(f"[SCOUT] Cooldown started: {self._cooldown_duration}s after Tier {tier_used}")
    
    def get_status(self) -> dict:
        """Current Scout state for debug output."""
        return {
            "cooling": self._is_cooling(),
            "available_tier": self._available_tier(),
            "consecutive_blockages": self._consecutive_blockages,
            "last_tier_used": self._last_overdrive_tier,
            "cooldown_remaining": max(0, (self._cooldown_until - datetime.now()).total_seconds()) if self._cooldown_until else 0,
        }
```

### File Location

```
src/luna/actors/scout.py
```

Follows same pattern as other actors in `src/luna/actors/`.

---

## COMPONENT 2: OVERDRIVE

### What It Is

Not a separate class — it's a method on Scout that builds an expanded SearchChainConfig and re-runs retrieval + generation. Overdrive is what Scout *does* when it finds a blockage.

### Tier Weights

| Parameter | Normal | Tier 1 (shallow) | Tier 2 (surrender) | Tier 3 (deep) |
|-----------|--------|-------------------|---------------------|----------------|
| Token budget | 3,000 | 8,000 | 12,000 | 16,000 |
| Matrix tokens | 1,500 | 4,000 | 6,000 | 8,000 |
| Dataroom tokens | 1,500 | 4,000 | 6,000 | 8,000 |
| Dataroom doc limit | 3 | 5 | 8 | 12 |
| Sources | matrix, dataroom | matrix, dataroom | matrix, dataroom, local_files | matrix, dataroom, local_files, AgentLoop |
| Timeout | 10s | 15s | 20s | 30s |

### Implementation

```python
# On ScoutActor:

async def overdrive(self, query: str, tier: int, engine) -> Optional[str]:
    """
    Run expanded retrieval at the specified tier and re-generate.
    
    Args:
        query: Original user query
        tier: Overdrive tier (1-3)
        engine: LunaEngine instance
    
    Returns:
        Re-generated response text, or None if Overdrive also fails
    """
    from luna.tools.search_chain import SearchChainConfig, SearchSourceConfig, run_search_chain
    
    logger.info(f"[OVERDRIVE] Tier {tier} activating for: {query[:50]}")
    
    # Build tier-specific config
    config = self._build_tier_config(tier)
    
    # Run expanded retrieval
    results = await run_search_chain(config, query, engine)
    
    if not results:
        logger.warning(f"[OVERDRIVE] Tier {tier} retrieval returned empty")
        return None
    
    # For Tier 3, also run AgentLoop
    agent_context = ""
    if tier >= 3:
        agent_loop = getattr(engine, 'agent_loop', None)
        if agent_loop:
            try:
                import asyncio
                loop_result = await asyncio.wait_for(agent_loop.run(query), timeout=30.0)
                if loop_result and loop_result.success:
                    agent_context = loop_result.response or ""
            except Exception as e:
                logger.warning(f"[OVERDRIVE] AgentLoop failed in Tier 3: {e}")
    
    # Assemble enriched context
    enriched_context = "\n\n".join([r.get("content", "") for r in results])
    if agent_context:
        enriched_context += f"\n\n[Agent Research]\n{agent_context}"
    
    # Re-generate through Director with enriched context
    director = engine.get_actor("director") if hasattr(engine, 'get_actor') else None
    if not director:
        logger.error("[OVERDRIVE] No Director actor available for re-generation")
        return None
    
    try:
        result = await director.process(
            message=query,
            context={
                "interface": "voice",
                "memories": results,
                "overdrive": True,
                "overdrive_tier": tier,
                "enriched_context": enriched_context,
            }
        )
        response = result.get("response", "") if result else ""
        
        if response:
            logger.info(f"[OVERDRIVE] Tier {tier} re-generation succeeded ({len(response)} chars)")
            self.start_cooldown(tier)
        
        return response
    
    except Exception as e:
        logger.error(f"[OVERDRIVE] Re-generation failed: {e}")
        return None

def _build_tier_config(self, tier: int) -> "SearchChainConfig":
    """Build SearchChainConfig for a specific Overdrive tier."""
    from luna.tools.search_chain import SearchChainConfig, SearchSourceConfig
    
    if tier == 1:
        return SearchChainConfig(
            max_total_tokens=8000,
            sources=[
                SearchSourceConfig(type="matrix", max_tokens=4000),
                SearchSourceConfig(type="dataroom", max_tokens=4000, limit=5),
            ]
        )
    elif tier == 2:
        return SearchChainConfig(
            max_total_tokens=12000,
            sources=[
                SearchSourceConfig(type="matrix", max_tokens=6000),
                SearchSourceConfig(type="dataroom", max_tokens=6000, limit=8),
                SearchSourceConfig(type="local_files", max_tokens=3000, limit=5),
            ]
        )
    else:  # Tier 3
        return SearchChainConfig(
            max_total_tokens=16000,
            sources=[
                SearchSourceConfig(type="matrix", max_tokens=8000),
                SearchSourceConfig(type="dataroom", max_tokens=8000, limit=12),
                SearchSourceConfig(type="local_files", max_tokens=4000, limit=8),
            ]
        )
```

---

## COMPONENT 3: WATCHDOG (Stuck State Handler)

### What It Is

A lightweight monitor that detects when the system is stuck and forces a reset to IDLE. Runs as a background check, not a separate process. Can be a method on the engine or a mixin on Scout.

### Stuck States to Detect

| State | Condition | Max Duration | Recovery |
|-------|-----------|-------------|----------|
| EXECUTING stuck | AgentLoop in EXECUTING for too long | 45s | Abort loop, force IDLE |
| PLANNING stuck | Planner decomposition hung | 15s | Cancel plan, force IDLE |
| WAITING stuck | Waiting for external event that never came | 30s | Timeout, force IDLE |
| Overdrive hung | Overdrive retrieval + re-gen exceeds timeout | tier timeout + 10s buffer | Cancel, deliver original draft |
| Director hung | Director.process() never returned | 30s | Cancel, return fallback response |
| Scout loop | Scout triggers Overdrive, Overdrive re-gen triggers Scout again | depth > 1 | Hard block recursion |

### Implementation

```python
# Can live on ScoutActor or as a separate lightweight class

import asyncio
from datetime import datetime, timedelta

class Watchdog:
    """
    Detects stuck states in Luna's processing pipeline.
    Forces reset to IDLE when timeouts exceeded.
    """
    
    def __init__(self, engine):
        self._engine = engine
        self._active_operations: dict[str, datetime] = {}  # op_id → start_time
        self._max_durations: dict[str, float] = {
            "agent_loop": 45.0,
            "planning": 15.0,
            "waiting": 30.0,
            "overdrive": 40.0,   # tier timeout + buffer
            "director_process": 30.0,
        }
        self._recursion_depth: int = 0
        self._max_recursion: int = 1  # Scout → Overdrive → Director. No deeper.
    
    def start_operation(self, op_id: str) -> None:
        """Mark an operation as started."""
        self._active_operations[op_id] = datetime.now()
        logger.debug(f"[WATCHDOG] Operation started: {op_id}")
    
    def end_operation(self, op_id: str) -> None:
        """Mark an operation as completed."""
        if op_id in self._active_operations:
            elapsed = (datetime.now() - self._active_operations[op_id]).total_seconds()
            del self._active_operations[op_id]
            logger.debug(f"[WATCHDOG] Operation completed: {op_id} ({elapsed:.1f}s)")
    
    def check_stuck(self) -> list[str]:
        """
        Check for stuck operations.
        
        Returns:
            List of stuck operation IDs that need forced reset.
        """
        stuck = []
        now = datetime.now()
        
        for op_id, start_time in list(self._active_operations.items()):
            # Find the matching max duration
            max_dur = self._max_durations.get(op_id, 30.0)
            elapsed = (now - start_time).total_seconds()
            
            if elapsed > max_dur:
                logger.warning(f"[WATCHDOG] STUCK detected: {op_id} running for {elapsed:.1f}s (max {max_dur}s)")
                stuck.append(op_id)
        
        return stuck
    
    async def force_reset(self, op_id: str) -> None:
        """Force-reset a stuck operation."""
        logger.warning(f"[WATCHDOG] Forcing reset for: {op_id}")
        
        if op_id == "agent_loop":
            agent_loop = getattr(self._engine, 'agent_loop', None)
            if agent_loop and hasattr(agent_loop, 'abort'):
                agent_loop.abort()
                # AgentLoop.abort() sets _abort_requested = True, loop exits on next iteration
        
        # Clear from active operations
        self.end_operation(op_id)
        
        # Reset engine state if needed
        if hasattr(self._engine, 'agent_loop') and self._engine.agent_loop:
            self._engine.agent_loop.status = AgentStatus.IDLE
    
    def enter_recursion(self) -> bool:
        """
        Track recursion depth. Returns False if max depth exceeded.
        Prevents: Scout → Overdrive → Director → Scout → Overdrive → ...
        """
        self._recursion_depth += 1
        if self._recursion_depth > self._max_recursion:
            logger.warning(f"[WATCHDOG] Recursion blocked at depth {self._recursion_depth}")
            self._recursion_depth = 0
            return False
        return True
    
    def exit_recursion(self) -> None:
        """Exit one level of recursion."""
        self._recursion_depth = max(0, self._recursion_depth - 1)
    
    def get_status(self) -> dict:
        """Current Watchdog state for debug output."""
        now = datetime.now()
        active = {
            op_id: {
                "elapsed_s": round((now - start).total_seconds(), 1),
                "max_s": self._max_durations.get(op_id, 30.0),
                "stuck": (now - start).total_seconds() > self._max_durations.get(op_id, 30.0),
            }
            for op_id, start in self._active_operations.items()
        }
        return {
            "active_operations": active,
            "recursion_depth": self._recursion_depth,
            "stuck_count": sum(1 for v in active.values() if v["stuck"]),
        }
```

### Periodic Check (optional background task)

```python
# If you want proactive stuck detection rather than check-on-demand:

async def watchdog_loop(watchdog: Watchdog, interval: float = 5.0):
    """Background task that periodically checks for stuck states."""
    while True:
        await asyncio.sleep(interval)
        stuck = watchdog.check_stuck()
        for op_id in stuck:
            await watchdog.force_reset(op_id)
```

Register as a background task on engine startup:

```python
# In engine.py _boot():
self.watchdog = Watchdog(self)
asyncio.create_task(watchdog_loop(self.watchdog, interval=5.0))
```

---

## INTEGRATION: WIRING INTO PERSONA ADAPTER

The existing `persona_adapter.py` already has `_surrender_intercept()`. Replace it with the Scout system:

```python
# In PersonaAdapter.process_message():

# After Director generates draft...

# ── Scout inspection (replaces surrender_intercept) ──
scout = getattr(self._engine, 'scout', None) if self._engine else None
watchdog = getattr(self._engine, 'watchdog', None) if self._engine else None
scout_report = None

if scout and response_text:
    scout_report = scout.inspect(
        draft=response_text,
        query=message,
        context_size=sum(len(m.get("content", "")) for m in memory_context),
    )
    
    if scout_report.blocked and scout_report.overdrive_tier > 0:
        # Check watchdog recursion guard
        if watchdog and not watchdog.enter_recursion():
            logger.warning("[VOICE] Watchdog blocked Scout recursion")
        else:
            # Track operation for stuck detection
            if watchdog:
                watchdog.start_operation("overdrive")
            
            try:
                overdrive_response = await scout.overdrive(
                    query=message,
                    tier=scout_report.overdrive_tier,
                    engine=self._engine,
                )
                if overdrive_response:
                    response_text = overdrive_response
            except Exception as e:
                logger.error(f"[OVERDRIVE] Failed: {e}")
            finally:
                if watchdog:
                    watchdog.end_operation("overdrive")
                    watchdog.exit_recursion()

# Include Scout + Watchdog status in debug output
debug_info = {
    # ... existing debug fields ...
    "scout_report": scout_report.__dict__ if scout_report else None,
    "scout_status": scout.get_status() if scout else None,
    "watchdog_status": watchdog.get_status() if watchdog else None,
}
```

---

## REGISTRATION

### Add Scout + Watchdog to engine boot sequence

```python
# In src/luna/engine.py _boot(), after existing actor registration:

# Register Scout actor
from luna.actors.scout import ScoutActor
scout = ScoutActor()
self.register_actor(scout)

# Initialize Watchdog
from luna.actors.scout import Watchdog  # or separate file
self.watchdog = Watchdog(self)

# Optional: start background watchdog loop
import asyncio
asyncio.create_task(watchdog_loop(self.watchdog, interval=5.0))

logger.info("[ENGINE] Scout and Watchdog initialized")
```

---

## FILES TO CREATE / MODIFY

| Action | File | What |
|--------|------|------|
| **CREATE** | `src/luna/actors/scout.py` | ScoutActor, BlockageReport, detection patterns, Overdrive method, Watchdog class |
| **MODIFY** | `src/voice/persona_adapter.py` | Replace `_surrender_intercept()` with Scout inspection + Overdrive trigger |
| **MODIFY** | `src/luna/engine.py` | Register ScoutActor and Watchdog in `_boot()` |
| **MODIFY** | `src/luna/actors/__init__.py` | Export ScoutActor |

---

## WHAT NOT TO BUILD

- No external agent frameworks (no LangChain, no CrewAI)
- No separate process or service for Scout — it's an actor
- No new retrieval system — Overdrive uses existing SearchChainConfig
- No new tool system — Tier 3 uses existing AgentLoop + ToolRegistry
- No persistent state for Watchdog — in-memory only, resets on restart
- Don't remove existing `_surrender_intercept()` until Scout is validated — keep it as fallback

---

## TESTING

### Scout Detection Tests

```python
# Test each blockage type
scout = ScoutActor()

# Surrender
report = scout.inspect("I don't have any memories about Kozmo.", "tell me about Kozmo")
assert report.blocked == True
assert report.blockage_type == "surrender"
assert report.overdrive_tier == 2

# Shallow
report = scout.inspect("From what I recall, Kozmo is related to something. The details are a bit fuzzy though.", "tell me about Kozmo")
assert report.blocked == True
assert report.blockage_type == "shallow_recall"
assert report.overdrive_tier == 1

# Deflection
report = scout.inspect("I'd love to learn more! Can you tell me about Kozmo?", "tell me about Kozmo")
assert report.blocked == True
assert report.blockage_type == "deflection"
assert report.overdrive_tier == 2

# Clean pass
report = scout.inspect("Kozmo is the integrated application framework built on Luna Engine. It connects three substrates: the Dinosaur, the Wizard, and the Mother.", "tell me about Kozmo")
assert report.blocked == False
assert report.overdrive_tier == 0
```

### Cooldown Tests

```python
scout = ScoutActor()
scout._cooldown_duration = 10.0  # Short for testing

# Fire Overdrive
scout.start_cooldown(tier_used=2)
assert scout._is_cooling() == True
assert scout._available_tier() == 0  # Just fired, nothing available

# Wait for partial recovery
import time
time.sleep(4)  # 40% of cooldown
assert scout._available_tier() == 1  # Tier 1 only

# Wait for full recovery
time.sleep(7)  # Past cooldown
assert scout._is_cooling() == False
assert scout._available_tier() == 3  # All tiers
```

### Watchdog Tests

```python
watchdog = Watchdog(engine=None)

# Start an operation
watchdog.start_operation("agent_loop")
assert len(watchdog._active_operations) == 1

# Not stuck yet
assert watchdog.check_stuck() == []

# Simulate stuck (override start time)
from datetime import timedelta
watchdog._active_operations["agent_loop"] = datetime.now() - timedelta(seconds=60)
stuck = watchdog.check_stuck()
assert "agent_loop" in stuck

# Recursion guard
assert watchdog.enter_recursion() == True   # depth 1: OK
assert watchdog.enter_recursion() == False  # depth 2: BLOCKED
```

### Integration Test (Voice Path)

```bash
# Start server, send query that previously triggered surrender:
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "tell me about Kozmo"}'

# Check debug output for:
# - scout_report.blocked = true/false
# - scout_report.overdrive_tier (if blocked)
# - scout_status.cooling
# - watchdog_status.active_operations (should be empty after completion)
```

---

## EXPECTED OUTCOME

| Scenario | Before | After |
|----------|--------|-------|
| "Tell me about Kozmo" → surrender | "I don't have memories about that" | Scout detects → Tier 2 Overdrive → expanded retrieval → informed response |
| "Tell me about Kozmo" → shallow | "Details are fuzzy, that's all I can say" | Scout detects → Tier 1 Overdrive → deeper token budget → richer response |
| "Tell me about Kozmo" → deflection | "Can you tell me more? I'd love to learn!" | Scout detects → Tier 2 Overdrive → retrieves her own docs → answers with authority |
| AgentLoop hangs for 60s | Voice app freezes, no response | Watchdog detects at 45s → aborts loop → resets to IDLE → delivers fallback |
| Scout → Overdrive → re-gen triggers Scout again | Infinite loop | Watchdog recursion guard blocks at depth 1 |
| Overdrive fires 3 times in 1 minute | Resource abuse, slow responses | Cooldown: first fire = full, second = Tier 1 only, third = blocked until cooldown expires |

---

## ARCHITECTURE SUMMARY

```
User Query
    │
    ▼
QueryRouter.analyze() → ExecutionPath
    │
    ▼
Director.process() → draft response
    │
    ▼
Scout.inspect(draft) ─── clean? ──► deliver response
    │                                       ▲
    │ blocked                               │
    ▼                                       │
Watchdog.enter_recursion() ── blocked? ─► deliver draft as-is
    │
    │ allowed
    ▼
Watchdog.start_operation("overdrive")
    │
    ▼
Scout.overdrive(query, tier, engine)
    ├── _build_tier_config(tier) → expanded SearchChainConfig
    ├── run_search_chain() → enriched context
    ├── [Tier 3] AgentLoop.run() → additional research
    └── Director.process(enriched) → re-generated response
    │
    ▼
Watchdog.end_operation("overdrive")
Scout.start_cooldown(tier)
    │
    ▼
Deliver re-generated response


Background:
    Watchdog.check_stuck() runs every 5s
    └── If stuck detected → force_reset() → IDLE
```
