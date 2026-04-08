# HANDOFF: LLM Provider Abstraction & Settings UI

**Priority:** HIGH — architectural integrity issue (cloud dependencies in an offline-first system)
**Scope:** Backend provider abstraction + Eclissi frontend settings panel
**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`
**Python:** `.venv/bin/python3`

---

## THE PROBLEM

Luna is offline-first. But the engine has hard imports on `openai` and `groq` Python packages — cloud SDKs wired as dependencies, not plugins. When they're missing, Luna crashes instead of gracefully falling back to local inference.

There is no UI for switching LLM providers. Changing from Ollama to Groq to Claude requires editing config files or environment variables. This is not how a product works.

**What we need:**
1. A single LLM provider interface that all engine code calls
2. Providers registered as optional plugins — local (Ollama) is default, cloud is opt-in
3. A settings panel in Eclissi where the user picks their provider and enters API keys
4. Graceful fallback: if selected provider is unreachable, try local before failing

---

## PHASE 1: AUDIT — Map Every LLM Call

Before writing any code, find every place the engine makes an LLM call.

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find all cloud SDK imports
grep -rn "import openai\|from openai\|import groq\|from groq\|import anthropic\|from anthropic" src/

# Find all LLM call sites
grep -rn "ollama\|groq\|openai\|chat\.completions\|ChatCompletion" src/

# Find config references
grep -rn "GROQ_API_KEY\|OPENAI_API_KEY\|ANTHROPIC_API_KEY\|LLM_PROVIDER\|model_name\|model_id" src/

# Find requirements
cat requirements.txt | grep -i "openai\|groq\|anthropic"
```

**Document every call site.** For each one, record:
- File and line number
- What it's doing (main inference? scribe extraction? embedding? subtask?)
- What provider it's currently hardcoded to
- What model it's using

---

## PHASE 2: BACKEND — Provider Abstraction Layer

### 2A. Create provider interface

Create `src/llm/provider.py`:

```python
"""
LLM Provider abstraction. All engine code calls this interface.
Providers are optional — only local (Ollama) is required.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, AsyncIterator
import logging

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    OLLAMA = "ollama"       # Local, always available
    GROQ = "groq"           # Cloud, optional
    ANTHROPIC = "anthropic" # Cloud, optional
    OPENAI = "openai"       # Cloud, optional


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: ProviderType
    tokens_used: Optional[int] = None


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "", 
                       model: str = None, temperature: float = 0.7,
                       max_tokens: int = 2048) -> LLMResponse:
        ...

    @abstractmethod
    async def stream(self, prompt: str, system: str = "",
                     model: str = None, temperature: float = 0.7,
                     max_tokens: int = 2048) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable and ready."""
        ...

    @abstractmethod
    def available_models(self) -> list[str]:
        """Return list of models this provider supports."""
        ...
```

### 2B. Create provider implementations

Create `src/llm/providers/` directory with:

**`ollama.py`** — The default. Always present. No pip dependency.
```python
"""Ollama provider — local inference, no external dependencies."""
import aiohttp  # already a dependency for FastAPI
from ..provider import LLMProvider, LLMResponse, ProviderType

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def generate(self, prompt, system="", model=None, 
                       temperature=0.7, max_tokens=2048):
        model = model or "qwen2.5:3b"  # sensible local default
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/api/generate", json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens}
            }) as resp:
                data = await resp.json()
                return LLMResponse(
                    text=data["response"],
                    model=model,
                    provider=ProviderType.OLLAMA
                )

    async def health_check(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", 
                                       timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def stream(self, prompt, system="", model=None, 
                     temperature=0.7, max_tokens=2048):
        model = model or "qwen2.5:3b"
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/api/generate", json={
                "model": model, "prompt": prompt, "system": system,
                "stream": True,
                "options": {"temperature": temperature, "num_predict": max_tokens}
            }) as resp:
                async for line in resp.content:
                    import json
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        yield chunk["response"]

    def available_models(self):
        # This would ideally query /api/tags but return sensible defaults
        return ["qwen2.5:3b", "qwen2.5:7b", "llama3.2:3b", "mistral:7b"]
```

**`groq.py`** — Optional. Import guarded.
```python
"""Groq provider — cloud inference, requires 'groq' package and API key."""
from ..provider import LLMProvider, LLMResponse, ProviderType

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str):
        try:
            from groq import AsyncGroq
        except ImportError:
            raise ImportError(
                "Groq provider requires 'groq' package. "
                "Install with: pip install groq"
            )
        self.client = AsyncGroq(api_key=api_key)

    # ... implement generate, stream, health_check, available_models
    # available_models returns ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", etc.]
```

**`anthropic_provider.py`** — Optional. Import guarded. Same pattern.

**`openai_provider.py`** — Optional. Import guarded. Same pattern.

**CRITICAL:** Cloud provider imports are lazy (inside `__init__`, not at module top). If the package isn't installed, the provider simply can't be instantiated — it doesn't crash the engine.

### 2C. Create provider registry

Create `src/llm/registry.py`:

```python
"""
Provider registry. Manages active provider and fallback chain.
Config persisted to SQLite so it survives restarts.
"""
import logging
from .provider import LLMProvider, ProviderType
from .providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self, db_conn):
        self._providers: dict[ProviderType, LLMProvider] = {}
        self._active: ProviderType = ProviderType.OLLAMA
        self._db = db_conn
        self._ensure_table()
        self._load_config()
        # Ollama is always registered
        self._providers[ProviderType.OLLAMA] = OllamaProvider()

    def _ensure_table(self):
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS llm_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self._db.commit()

    def _load_config(self):
        """Load saved provider preference from DB."""
        row = self._db.execute(
            "SELECT value FROM llm_config WHERE key = 'active_provider'"
        ).fetchone()
        if row:
            try:
                self._active = ProviderType(row[0])
            except ValueError:
                self._active = ProviderType.OLLAMA

    def register(self, provider_type: ProviderType, provider: LLMProvider):
        self._providers[provider_type] = provider

    def set_active(self, provider_type: ProviderType):
        if provider_type not in self._providers:
            raise ValueError(f"Provider {provider_type} not registered")
        self._active = provider_type
        self._db.execute(
            "INSERT OR REPLACE INTO llm_config (key, value) VALUES (?, ?)",
            ("active_provider", provider_type.value)
        )
        self._db.commit()

    async def get_provider(self) -> LLMProvider:
        """Return active provider. Falls back to Ollama if active is unreachable."""
        provider = self._providers.get(self._active)
        if provider and await provider.health_check():
            return provider
        # Fallback to local
        if self._active != ProviderType.OLLAMA:
            logger.warning(
                f"{self._active.value} unreachable, falling back to Ollama"
            )
            ollama = self._providers[ProviderType.OLLAMA]
            if await ollama.health_check():
                return ollama
        raise RuntimeError("No LLM provider available (is Ollama running?)")

    def list_available(self) -> list[dict]:
        """Return list of registered providers with health status (for UI)."""
        return [
            {"type": pt.value, "registered": pt in self._providers}
            for pt in ProviderType
        ]
```

### 2D. Wire into engine

Replace every direct LLM call in the codebase with calls through the registry:

```python
# BEFORE (scattered throughout codebase):
from groq import Groq
client = Groq(api_key=os.environ["GROQ_API_KEY"])
response = client.chat.completions.create(model="llama-3.3-70b-versatile", ...)

# AFTER:
provider = await self.registry.get_provider()
response = await provider.generate(prompt=prompt, system=system)
```

**Every call site found in Phase 1 gets this treatment.** No exceptions.

### 2E. Add API endpoints for settings

In the FastAPI app, add:

```python
@app.get("/api/settings/providers")
async def list_providers():
    """Return available providers and which is active."""
    providers = registry.list_available()
    active = registry._active.value
    return {"providers": providers, "active": active}

@app.post("/api/settings/provider")
async def set_provider(body: dict):
    """Switch active provider. Body: {"provider": "groq", "api_key": "..."}"""
    provider_type = ProviderType(body["provider"])

    if provider_type != ProviderType.OLLAMA:
        api_key = body.get("api_key", "")
        if not api_key:
            return {"error": "API key required for cloud providers"}, 400
        # Store key securely (in DB, not env var)
        # Instantiate and register the provider
        # ...

    registry.set_active(provider_type)
    return {"active": provider_type.value}

@app.get("/api/settings/models")
async def list_models():
    """Return models available from the active provider."""
    provider = await registry.get_provider()
    return {"models": provider.available_models()}

@app.post("/api/settings/model")
async def set_model(body: dict):
    """Set the active model. Body: {"model": "qwen2.5:7b"}"""
    # Persist to llm_config table
    # ...
```

### 2F. Remove hard dependencies

In `requirements.txt`, move cloud SDKs to optional:

```
# requirements.txt — REQUIRED
aiohttp
fastapi
uvicorn
sqlite-vec
# ... other core deps

# OPTIONAL (install for cloud provider support)
# pip install groq        — for Groq cloud inference
# pip install anthropic   — for Claude cloud inference
# pip install openai      — for OpenAI cloud inference
```

**Or** use extras in `pyproject.toml`:
```toml
[project.optional-dependencies]
groq = ["groq"]
anthropic = ["anthropic"]
openai = ["openai"]
cloud = ["groq", "anthropic", "openai"]
```

---

## PHASE 3: FRONTEND — Settings Panel in Eclissi

### 3A. Settings route

Add a Settings page/panel to Eclissi (React/Vite/Tailwind). Accessible from a gear icon or menu.

### 3B. Provider selector

The settings panel needs:

**LLM Provider section:**
- Dropdown or radio group: `Ollama (Local)` | `Groq` | `Anthropic` | `OpenAI`
- Ollama selected by default, shown with a green "Local · No internet required" badge
- Cloud providers show an API key input field when selected
- "Test Connection" button that hits the health_check endpoint
- Status indicator: green dot (connected), yellow (checking), red (unreachable)

**Model selector:**
- Dropdown populated from `/api/settings/models` based on active provider
- For Ollama: shows locally downloaded models
- For cloud: shows available models for that provider

**Visual hierarchy:**
- Local-first emphasis. Ollama should feel like the natural default, not the fallback.
- Cloud options should feel like "upgrades" or "boosters," not the main path.
- Something like: the Ollama option is full-width and prominent, cloud options are in a collapsible "Cloud Providers" section below.

### 3C. Behavior

- Changing provider calls `POST /api/settings/provider`
- API keys stored server-side in luna_engine.db (NOT in localStorage, NOT in .env files)
- If cloud provider is selected but unreachable, show a toast/banner: "Groq unreachable — using local Ollama"
- Settings persist across restarts (saved to DB)

### 3D. Rough layout

```
┌─────────────────────────────────────────┐
│  ⚙️ Settings                             │
├─────────────────────────────────────────┤
│                                         │
│  LLM Provider                           │
│  ┌─────────────────────────────────────┐│
│  │ ● Ollama (Local)                    ││
│  │   🟢 Connected · qwen2.5:3b        ││
│  │   Model: [qwen2.5:3b        ▼]     ││
│  │   No internet required              ││
│  └─────────────────────────────────────┘│
│                                         │
│  ▸ Cloud Providers (optional)           │
│  ┌─────────────────────────────────────┐│
│  │ ○ Groq                              ││
│  │   API Key: [••••••••••••••••]       ││
│  │   [Test Connection]                  ││
│  │                                      ││
│  │ ○ Anthropic (Claude)                 ││
│  │   API Key: [                  ]     ││
│  │   [Test Connection]                  ││
│  │                                      ││
│  │ ○ OpenAI                             ││
│  │   API Key: [                  ]     ││
│  │   [Test Connection]                  ││
│  └─────────────────────────────────────┘│
│                                         │
│  Fallback: Always try Ollama if cloud   │
│  provider is unreachable                │
│                                         │
└─────────────────────────────────────────┘
```

---

## DO NOT

- Do NOT remove Groq/OpenAI/Anthropic *support* — just make them optional plugins, not hard requirements
- Do NOT change any retrieval logic (Nexus/AiBrarian) — separate handoff
- Do NOT change the `/stream` or `/message` endpoint signatures
- Do NOT rename anything (no AiBrarian→Nexus in this handoff)
- Do NOT touch the Memory Matrix, scribe extraction logic, or FTS5 tables
- Do NOT store API keys in environment variables or .env files — use the llm_config DB table
- Do NOT make the UI feel like cloud is the default — local-first, always

---

## VERIFICATION

### Backend
1. `pip uninstall groq openai` — Luna should start and respond using Ollama with zero errors
2. `pip install groq` + set API key via settings endpoint → Groq becomes available
3. Kill Ollama while Groq is active → still works via cloud
4. Kill Groq while Ollama is active → still works via local
5. Kill both → clean error message, no crash

### Frontend
1. Settings page loads, shows Ollama as default with green status
2. Switch to Groq, enter key, test connection → green
3. Switch back to Ollama → persists across page refresh
4. Restart Luna server → settings preserved

### Integration
1. Run the QA test suite with Ollama selected → all queries go through local
2. Switch to Groq mid-session → subsequent queries use Groq
3. Disconnect wifi → Luna falls back to Ollama automatically

---

## FILES TO CREATE
- `src/llm/__init__.py`
- `src/llm/provider.py`
- `src/llm/registry.py`
- `src/llm/providers/__init__.py`
- `src/llm/providers/ollama.py`
- `src/llm/providers/groq.py`
- `src/llm/providers/anthropic_provider.py`
- `src/llm/providers/openai_provider.py`
- Settings API routes (in existing FastAPI app)
- Settings component in Eclissi frontend

## FILES TO MODIFY
- Every file that currently imports cloud SDKs directly (found in Phase 1 audit)
- `requirements.txt` or `pyproject.toml` — move cloud deps to optional
- FastAPI app initialization — wire up ProviderRegistry

---

## PRIORITY ORDER
1. Phase 1 (audit) — know what we're dealing with
2. Phase 2A-2C (provider interface + registry) — the abstraction
3. Phase 2D (wire into engine) — make it work
4. Phase 2F (remove hard deps) — make it sovereign
5. Phase 2E (API endpoints) — expose to frontend
6. Phase 3 (frontend settings UI) — make it usable
