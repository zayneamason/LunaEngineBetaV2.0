# Fix Plan - Luna System Diagnostic

**Priority Order:** Execute in sequence, test after each fix.

---

## FIX 1: Test Script - Wrong Attribute Name (P2)

**File:** `scripts/test_llm_providers.py`
**Line:** ~288
**Change:** `result.text` -> `result.content`

**Before:**
```python
print(f"  Response: {result.text[:50]}")
```

**After:**
```python
print(f"  Response: {result.content[:50] if result.content else 'EMPTY'}")
```

**Test:** `python scripts/test_llm_providers.py`

---

## FIX 2: Unit Test - Wrong Class Name (P3)

**File:** `tests/test_critical_systems.py`
**Line:** 89
**Change:** `Director` -> `DirectorActor`

**Before:**
```python
from luna.actors.director import Director
```

**After:**
```python
from luna.actors.director import DirectorActor
```

**Test:** `pytest tests/test_critical_systems.py::TestLunaImports::test_actors -v`

---

## FIX 3: Gemini Provider - Model Discovery (P1)

**Action:** First, discover available models.

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python3 -c "
import google.generativeai as genai
import os
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
for m in genai.list_models():
    if 'generateContent' in str(m.supported_generation_methods):
        print(f'{m.name}: {m.supported_generation_methods}')
"
```

**Then:** Update `src/luna/llm/providers/gemini_provider.py` with correct model names.

**Possible new models:**
- `models/gemini-1.5-flash-latest`
- `models/gemini-pro`
- `models/gemini-2.0-flash`

**Test:** `python scripts/test_llm_providers.py`

---

## FIX 4: Claude Billing (P4 - External)

**Action:** No code change. Add credits at:
https://console.anthropic.com/settings/billing

**Alternative:** Luna works fine with Groq + Gemini. Claude is optional.

---

## Post-Fix Verification

After all fixes, run full diagnostic:
```bash
./scripts/run_all_diagnostics.sh 2>&1 | tee Docs/Handoffs/DiagnosticResults/POST_FIX_DIAGNOSTIC.txt
```

**Success Criteria:**
- [ ] All 20 unit tests pass
- [ ] At least 2/3 LLM providers working
- [ ] WebSocket stable
- [ ] `/persona/stream` returns tokens

---

## Notes

**WebSocket is NOT flapping.** The diagnostic shows:
- Connected successfully
- Stayed stable for 10 seconds
- 5/5 rapid reconnects worked

The original flapping issue may have been resolved by previous fixes, or occurs only under specific conditions (frontend interaction, concurrent connections, etc.).

**Chat flow is working.** The `/persona/stream` endpoint:
- Returns 200 OK
- Streams 21 events
- Includes token events
- Full response in 16.37s
