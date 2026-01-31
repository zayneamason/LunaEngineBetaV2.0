# AUDIT-CONFIG.md

**Generated:** 2026-01-30
**Agent:** Config Auditor
**Phase:** 1.9

---

## Summary

| Metric | Count |
|--------|-------|
| Config files (config/) | 3 |
| Swarm config files (.swarm/) | 5 |
| Entity config files (entities/) | 4 |
| Root config files | 2 |
| Environment variables used | 8 |
| **SECURITY VIOLATIONS** | **3 CRITICAL** |
| Deprecated keys | 1 |
| Config validation present | Partial |

---

## Config File Inventory

### Primary Config Files (`config/`)

| File | Purpose | Schema Type |
|------|---------|-------------|
| `config/llm_providers.json` | LLM provider settings (Groq, Gemini, Claude) | JSON |
| `config/personality.json` | Luna personality, gestures, expression config | JSON |
| `config/memory_economy_config.json` | Memory economy thresholds, weights, decay | JSON |

### Swarm Config Files (`.swarm/`)

| File | Purpose | Format |
|------|---------|--------|
| `.swarm/model-router-state.json` | Model router runtime state (not config) | JSON |
| `.swarm/orb_emotion_system.yaml` | Orb emotion swarm task definition | YAML |
| `.swarm/full-system-diagnostic.yaml` | Diagnostic swarm workflow | YAML |
| `.swarm/phase1-codebase-audit.yaml` | Phase 1 audit swarm config | YAML |
| `.swarm/phase2-test-expansion.yaml` | Phase 2 test expansion hive config | YAML |
| `.swarm/phase5-bible-update.yaml` | Phase 5 Bible update parallel config | YAML |

### Entity Config Files (`entities/`)

| File | Purpose | Format |
|------|---------|--------|
| `entities/personas/luna.yaml` | Luna's personality and voice config | YAML |
| `entities/personas/ben-franklin.yaml` | Ben Franklin (Scribe) persona | YAML |
| `entities/personas/the-dude.yaml` | The Dude (Librarian) persona | YAML |
| `entities/people/ahab.yaml` | User (Ahab) entity definition | YAML |

### Root Config Files

| File | Purpose | Format |
|------|---------|--------|
| `pyproject.toml` | Python project configuration | TOML |
| `.claude/settings.json` | Claude Code permissions | JSON |

---

## Schema Documentation

### config/llm_providers.json

```json
{
  "current_provider": "string",  // Active provider name
  "default_provider": "string",  // Fallback provider
  "providers": {
    "<provider_name>": {
      "enabled": boolean,
      "api_key_env": "string",  // Environment variable name (NOT the key itself)
      "default_model": "string",
      "models": ["string"]
    }
  }
}
```

**Providers Defined:** groq, gemini, claude

**Models Available:**
- Groq: llama-3.3-70b-versatile, llama-3.3-70b-specdec, llama3-70b-8192, llama3-8b-8192, mixtral-8x7b-32768
- Gemini: gemini-2.0-flash, gemini-2.0-flash-lite, gemini-1.5-pro
- Claude: claude-3-haiku-20240307, claude-3-5-sonnet-20241022, claude-3-opus-20240229

### config/personality.json

```json
{
  "personality_patch_storage": {
    "mode": "string",          // "memory_nodes"
    "node_type": "string",     // "PERSONALITY_REFLECTION"
    "settings": {
      "initial_lock_in": float,
      "consolidation_threshold": int,
      "max_active_patches": int,
      "decay_days_threshold": int,
      "decay_amount": float,
      "lock_in_deactivation_threshold": float
    }
  },
  "emergent_prompt": {
    "enabled": boolean,
    "max_patches_in_prompt": int,
    "min_lock_in_for_inclusion": float,
    "priority_rules": {
      "experience_over_dna": boolean,
      "mood_modulates_tone": boolean
    }
  },
  "mood_analysis": {
    "enabled": boolean,
    "recent_messages_count": int,
    "energy_threshold_high": int,
    "energy_threshold_low": int
  },
  "reflection_loop": {
    "enabled": boolean,
    "trigger_points": {
      "session_end": boolean,
      "every_n_interactions": int,
      "user_requested": boolean
    },
    "min_confidence_for_patch": float
  },
  "lifecycle": {
    "decay_enabled": boolean,
    "consolidation_enabled": boolean,
    "maintenance_interval_hours": int
  },
  "bootstrap": {
    "enabled": boolean,
    "run_on_first_launch": boolean,
    "protect_core_patches": boolean,
    "seed_patches": [...]
  },
  "token_budget": {
    "default_preset": "string",   // "minimal" | "balanced" | "rich"
    "presets": {
      "<preset_name>": {
        "total": int,
        "dna": int,
        "experience": int,
        "mood": int
      }
    }
  },
  "expression": {
    "gesture_frequency": "string",        // "minimal" | "moderate" | "expressive"
    "gesture_display_mode": "string",     // "visible" | "stripped" | "debug"
    "settings": {...},
    "gesture_contexts": ["string"]
  }
}
```

### config/memory_economy_config.json

```json
{
  "enabled": boolean,
  "use_clusters": boolean,
  "use_louvain": boolean,

  "constellation": {
    "max_tokens": int,
    "prioritize_clusters": boolean,
    "cluster_budget_pct": float
  },

  "thresholds": {
    "drifting": float,      // 0.20
    "fluid": float,         // 0.70
    "settled": float,       // 0.85
    "similarity": float,    // 0.82
    "auto_activation": float // 0.80
  },

  "weights": {
    "node": float,    // 0.40
    "access": float,  // 0.30
    "edge": float,    // 0.20
    "age": float      // 0.10
  },

  "decay": {
    "crystallized": float,  // 0.00001
    "settled": float,       // 0.0001
    "fluid": float,         // 0.001
    "drifting": float       // 0.01
  },

  "services": {
    "clustering_interval_hours": int,
    "lockin_update_interval_minutes": int,
    "cleanup_interval_hours": int
  },

  "clustering": {
    "min_cluster_size": int,
    "max_cluster_size": int,
    "min_keyword_overlap": float,
    "max_generic_frequency": int,
    "merge_similarity_threshold": float
  },

  "retrieval": {
    "max_clusters_per_query": int,
    "expand_top_clusters": int,
    "include_multi_hop": boolean,
    "min_edge_lock_in_for_hop": float
  },

  "limits": {
    "max_nodes_per_cluster": int,
    "max_expanded_nodes": int,
    "max_total_clusters": int
  }
}
```

### pyproject.toml

```toml
[project]
name = "luna-engine"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [...]

[project.optional-dependencies]
dev = [...]
memory = [...]
local = [...]
mcp = [...]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

---

## Environment Variables

### Required API Keys

| Variable | Purpose | Used By | Default |
|----------|---------|---------|---------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API | claude_provider.py, tests | None (required) |
| `GROQ_API_KEY` | Groq API | groq_provider.py, tests | None (required) |
| `GOOGLE_API_KEY` | Google Gemini API | gemini_provider.py, tests | None (required) |

### MCP Environment Variables

| Variable | Purpose | Used By | Default |
|----------|---------|---------|---------|
| `LUNA_BASE_PATH` | Project root path | luna_mcp/server.py, security.py | Auto-detected from `__file__` |
| `LUNA_MCP_API_URL` | MCP API endpoint URL | luna_mcp/server.py | `http://localhost:8742` |
| `LUNA_LOGS_DIR` | Log file directory | luna_mcp/memory_log.py | Project `logs/` directory |

### System Environment Variables

| Variable | Purpose | Used By | Default |
|----------|---------|---------|---------|
| `DYLD_LIBRARY_PATH` | Piper TTS library path | voice/tts/piper.py | Set dynamically |
| `TERM_PROGRAM` | Terminal detection (iTerm2) | persona_forge visualization | OS default |

### Environment Variable Validation

**Validation implemented in:** `src/luna/llm/config.py`

```python
@property
def is_configured(self) -> bool:
    """Check if API key is set."""
    return self.api_key is not None and len(self.api_key) > 0
```

---

## Security Check (Secrets)

### :rotating_light: CRITICAL SECURITY VIOLATIONS

#### 1. `.env` file contains hardcoded API keys

**File:** `/.env`

```
ANTHROPIC_API_KEY=sk-ant-api03-J30cClhH3zyG1tAe...
GROQ_API_KEY=gsk_IoQxBDNyCSyfYPZyvpx9...
GOOGLE_API_KEY=AIzaSyBt5fPuwuemNoVl1uVt...
```

**Status:** :x: VIOLATION - Real API keys committed to repo
**Severity:** CRITICAL
**Action Required:**
1. Immediately rotate ALL three API keys
2. Add `.env` to `.gitignore` if not already present
3. Remove `.env` from git history using `git filter-branch` or BFG Repo-Cleaner
4. Create `.env.example` with placeholder values

#### 2. Diagnostic Output contains truncated API keys

**File:** `Docs/Handoffs/DiagnosticResults/DIAGNOSTIC_OUTPUT.txt`

```
ANTHROPIC_API_KEY: sk-ant-api03-J3...skwAA
GROQ_API_KEY: gsk_IoQxBDNyCSy...BON0H
GOOGLE_API_KEY: AIzaSyBt5fPuwue...2gK_o
```

**Status:** :warning: PARTIAL EXPOSURE - Keys partially visible
**Severity:** HIGH
**Action Required:** Delete this file and sanitize diagnostic scripts

#### 3. Handoff Documentation Contains Key Format Examples

**File:** `HANDOFF_Multi_LLM_Provider_System.md`

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

**Status:** :white_check_mark: ACCEPTABLE - Using placeholder patterns
**Note:** Example format is fine, but ensure no real keys slip in

### Security Best Practices Implemented

| Feature | Status | Location |
|---------|--------|----------|
| API keys stored in env vars, not config | :white_check_mark: | llm_providers.json uses `api_key_env` |
| Forbidden file extensions list | :white_check_mark: | luna_mcp/security.py |
| Path traversal prevention | :white_check_mark: | luna_mcp/security.py |
| .env file protection | :x: | `.env` is tracked in git |

### Forbidden Patterns (security.py)

```python
FORBIDDEN_PATTERNS = {
    '.env',       # Environment secrets
    '.pem',       # Private keys
    '.key',       # Private keys
    '.crt',       # Certificates
    '.p12',       # PKCS12 keystores
    '.pfx',       # PKCS12 keystores
    '.sqlite',    # Sensitive data
    '.db',        # Sensitive data
}
```

---

## Deprecated Keys

### Potentially Deprecated

| Key | Location | Status | Reason |
|-----|----------|--------|--------|
| `use_louvain` | memory_economy_config.json | :warning: UNUSED | Set to `false`, no code references found for Louvain clustering implementation |

### Keys with Defaults (May Be Overridden)

| Key | Config Location | Default Value | Used |
|-----|-----------------|---------------|------|
| `current_provider` | llm_providers.json | "groq" | :white_check_mark: Yes |
| `gesture_frequency` | personality.json | "moderate" | :white_check_mark: Yes |
| `enabled` | memory_economy_config.json | true | :white_check_mark: Yes |

---

## Default Values

### LLM Providers (config.py `_create_default()`)

| Setting | Default |
|---------|---------|
| `current_provider` | "groq" |
| `default_provider` | "groq" |
| Groq model | "llama-3.1-70b-versatile" |
| Gemini model | "gemini-2.0-flash" |
| Claude model | "claude-3-haiku-20240307" |

### Memory Economy (params.py fallback)

| Setting | Default |
|---------|---------|
| `enabled` | true |
| `use_clusters` | true |
| `max_tokens` | 3000 |
| `prioritize_clusters` | true |
| `drifting` threshold | 0.20 |
| `fluid` threshold | 0.70 |
| `settled` threshold | 0.85 |
| `similarity` threshold | 0.82 |
| `min_cluster_size` | 3 |
| `max_cluster_size` | 50 |

### Lock-In Coefficient (substrate/lock_in.py)

| Setting | Default |
|---------|---------|
| `enabled` | true |
| `node_weight` | 0.4 |
| `access_weight` | 0.3 |
| `edge_weight` | 0.2 |
| `age_weight` | 0.1 |

### MCP Environment

| Setting | Default |
|---------|---------|
| `LUNA_MCP_API_URL` | "http://localhost:8742" |
| `LUNA_BASE_PATH` | Auto-detected PROJECT_ROOT |

---

## Validation Status

### Config Files with Validation

| File | Validation Method | Error Handling |
|------|-------------------|----------------|
| `llm_providers.json` | `LLMConfig.load()` in config.py | Falls back to `_create_default()` on error |
| `personality.json` | `PersonalityLifecycle._load_config()` | Returns empty dict on error |
| `memory_economy_config.json` | `_apply_memory_economy_param()` in params.py | Creates default config if missing |

### Validation Coverage

```
src/luna/llm/config.py:
    - Validates JSON structure
    - Falls back to defaults on parse error
    - Logs warnings for missing config

src/luna/entities/lifecycle.py:
    - Returns DEFAULT_CONFIG if file missing
    - No schema validation

src/luna/tuning/params.py:
    - Creates config with defaults if missing
    - Type coercion on write (bool/int/float)
```

### Missing Validation

| Gap | Risk | Recommendation |
|-----|------|----------------|
| No JSON schema validation | Invalid values accepted | Add pydantic models or JSON Schema |
| No range validation for thresholds | Values outside 0-1 accepted | Add bounds checking |
| No model name validation | Typos in model names not caught | Validate against known models list |

---

## Recommendations

### Immediate Actions (Security)

1. **CRITICAL:** Rotate all 3 API keys (Anthropic, Groq, Google)
2. **CRITICAL:** Add `.env` to `.gitignore` if missing
3. **CRITICAL:** Scrub git history to remove `.env` with real keys
4. **HIGH:** Delete `Docs/Handoffs/DiagnosticResults/DIAGNOSTIC_OUTPUT.txt`
5. **HIGH:** Update diagnostic scripts to mask key values

### Config Improvements

1. Add pydantic models for config validation
2. Remove `use_louvain` key if Louvain clustering not implemented
3. Document all config keys in a central reference
4. Add `.env.example` with placeholder values
5. Consider using `python-dotenv` for env file management

### Environment Variable Management

1. Use `.env.example` as template
2. Never commit `.env` files
3. Add pre-commit hook to catch secret leaks
4. Consider using a secrets manager for production

---

## Cross-References

- **Related Audit:** AUDIT-MODULES.md (for config loading code)
- **Related Audit:** AUDIT-MEMORY.md (for memory_economy_config usage)
- **Related Audit:** AUDIT-INFERENCE.md (for LLM provider config)
- **Bible Chapter:** 10-SOVEREIGNTY.md (security guarantees)
