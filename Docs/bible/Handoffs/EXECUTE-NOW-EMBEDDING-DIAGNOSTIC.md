# EXECUTE NOW: Embedding Reload Diagnostic

**Status:** 🔴 DO THIS NOW
**Priority:** BLOCKING
**Time:** 30 minutes

---

## STOP READING. START DOING.

Do not document. Do not organize. Do not summarize.

**RUN THE DIAGNOSTICS. REPORT THE DATA.**

---

## THE PROBLEM

Luna's embedding model reloads after EVERY response:
```
✓ [LOCAL] Complete: 20 tokens in 6289ms
📝 Extraction triggered for assistant turn (93 chars)
Loading weights:   0%|          | 0/103 [00:00<?, ?it/s]
...
Loading weights: 100%|██████████| 103/103 [...]
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
```

This should load ONCE. It's loading every time. Find out why.

---

## STEP 1: Add Diagnostic Logging (5 min)

Edit `src/luna/substrate/local_embeddings.py`:

```python
import os
import logging

logger = logging.getLogger(__name__)

_instance = None
_lock = threading.Lock()

def get_embeddings():
    global _instance
    with _lock:
        if _instance is None:
            logger.warning(f"[EMBED-SINGLETON] CREATING NEW INSTANCE pid={os.getpid()}")
            _instance = LocalEmbeddings()
        else:
            logger.info(f"[EMBED-SINGLETON] REUSING instance pid={os.getpid()}")
        return _instance

class LocalEmbeddings:
    def _load_model(self):
        if self._model is None:
            logger.warning(f"[EMBED-MODEL] LOADING MODEL pid={os.getpid()} instance_id={id(self)}")
            # ... existing load code
        else:
            logger.info(f"[EMBED-MODEL] MODEL ALREADY LOADED pid={os.getpid()}")
```

---

## STEP 2: Check for Multiple Processes (2 min)

```bash
# Are there multiple uvicorn workers?
ps aux | grep -E "uvicorn|python.*luna" | grep -v grep
```

Report: How many python processes? Same PID or different?

---

## STEP 3: Restart Server and Send 3 Messages (5 min)

```bash
# Kill existing
pkill -f "uvicorn.*luna"
sleep 2

# Start fresh
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -m luna.hub.server &
sleep 10

# Send 3 messages
curl -X POST "http://localhost:8000/message" -H "Content-Type: application/json" -d '{"message":"hi"}' &
sleep 15
curl -X POST "http://localhost:8000/message" -H "Content-Type: application/json" -d '{"message":"hello"}' &
sleep 15
curl -X POST "http://localhost:8000/message" -H "Content-Type: application/json" -d '{"message":"hey"}' &
sleep 15

# Capture logs
cat /tmp/luna_debug.log | grep -E "EMBED-SINGLETON|EMBED-MODEL|Loading weights" > /tmp/embed_diagnostic.txt
cat /tmp/embed_diagnostic.txt
```

---

## STEP 4: Report Back With This Data

I need these answers:

| Question | Your Finding |
|----------|--------------|
| How many "CREATING NEW INSTANCE" logs? | ___ |
| How many "LOADING MODEL" logs? | ___ |
| How many "Loading weights" progress bars? | ___ |
| Are PIDs the same or different? | ___ |
| How many python processes running? | ___ |

---

## EXPECTED VS BROKEN

**If singleton works:**
```
[EMBED-SINGLETON] CREATING NEW INSTANCE pid=12345  ← ONCE
[EMBED-MODEL] LOADING MODEL pid=12345              ← ONCE
Loading weights: 0%...100%                          ← ONCE
[EMBED-SINGLETON] REUSING instance pid=12345       ← EVERY OTHER TIME
[EMBED-MODEL] MODEL ALREADY LOADED pid=12345       ← EVERY OTHER TIME
```

**If broken (multiple processes):**
```
[EMBED-SINGLETON] CREATING NEW INSTANCE pid=12345
[EMBED-SINGLETON] CREATING NEW INSTANCE pid=12346  ← DIFFERENT PID = PROBLEM
[EMBED-SINGLETON] CREATING NEW INSTANCE pid=12347  ← EACH WORKER HAS OWN SINGLETON
```

**If broken (singleton not persisting):**
```
[EMBED-SINGLETON] CREATING NEW INSTANCE pid=12345
[EMBED-MODEL] LOADING MODEL pid=12345
[EMBED-SINGLETON] CREATING NEW INSTANCE pid=12345  ← SAME PID, NEW INSTANCE = GC PROBLEM
[EMBED-MODEL] LOADING MODEL pid=12345
```

---

## DO NOT

- ❌ Write more documentation
- ❌ Summarize this handoff
- ❌ Create new files explaining what you'll do
- ❌ Ask for clarification

## DO

- ✅ Edit local_embeddings.py with the logging
- ✅ Run the commands
- ✅ Paste the output
- ✅ Fill in the data table

---

**GO.**
