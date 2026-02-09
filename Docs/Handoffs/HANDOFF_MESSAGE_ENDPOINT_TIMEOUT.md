# HANDOFF: /message Endpoint Timeout Debug

**Date:** 2025-02-04
**Priority:** CRITICAL - Server unresponsive to chat
**Author:** Architect Claude (via Ahab)

---

## PROBLEM

Frontend chat shows "network error" but server IS running and healthy.

**Symptoms:**
- `/health` returns `{"status":"healthy","state":"RUNNING"}` ✅
- `/status` returns 200 ✅
- `/consciousness` returns 200 ✅
- `/message` POST → **30s timeout, no response** ❌

**User sees:**
```
hey how are you?
Error: network error
```

---

## DIAGNOSTIC FINDINGS

### 1. Server Status
```bash
# Server IS running on port 8000
lsof -i :8000
# PID 71106 - Python process listening

# Health check works
curl http://localhost:8000/health
# {"status":"healthy","state":"RUNNING"}
```

### 2. Message Endpoint Failure
```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message":"hey how are you?"}'

# RESULT: {"detail":"Response timeout after 30.0s"}
```

### 3. Server Logs (Last entries)
```
INFO: 127.0.0.1:49366 - "POST /slash/restart-backend HTTP/1.1" 200 OK
Python(31633) MallocStackLogging: can't turn off malloc stack logging...
resource_tracker: There appear to be 1 leaked semaphore objects...
```

**Key observation:** No log entry for the `/message` POST that timed out. Request may be hanging before logging.

---

## LIKELY CAUSES (Priority Order)

### 1. **Inference Hang** (Most Likely)
The `/message` endpoint calls into inference (local or delegation). If:
- Local MLX model failed to load
- Delegation path waiting on Claude API with no timeout
- Model loading blocking the event loop

**Check:**
```python
# src/luna/api/server.py - find /message handler
# Trace what it calls: engine.process_message() or similar
```

### 2. **Database Lock**
Memory Matrix SQLite could be locked by another process.

**Check:**
```bash
lsof /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db
```

### 3. **Async Deadlock**
Event loop blocked by synchronous call in async handler.

**Check:**
```python
# Look for any `time.sleep()` or blocking I/O in async path
```

### 4. **Memory/Resource Exhaustion**
Leaked semaphores suggest resource issues.

**Check:**
```bash
ps aux | grep python | head -5
# Check memory usage of PID 71106
```

---

## DEBUG STEPS FOR CLAUDE CODE

### Step 1: Find the /message handler
```bash
grep -n "def.*message\|@app.post.*message" src/luna/api/server.py
```

### Step 2: Add timeout tracing
Add logging at entry point:
```python
@app.post("/message")
async def handle_message(request: MessageRequest):
    logger.info(f"[TRACE] /message entry: {request.message[:50]}")
    # ... existing code
```

### Step 3: Check engine initialization
```python
# Is self.engine None or failed to init?
# Add: logger.info(f"[TRACE] Engine state: {self.engine}")
```

### Step 4: Test inference directly
```python
# Create test script:
from src.luna.engine import LunaEngine
engine = LunaEngine()
result = engine.process("test")  # Does this hang?
```

### Step 5: Check for blocking calls
```bash
grep -rn "time.sleep\|\.result()\|\.get()" src/luna/api/
```

---

## QUICK FIX ATTEMPTS

### Option A: Restart with fresh state
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
pkill -f "python.*run.py"
rm -f *.lock  # Remove any lock files
python scripts/run.py --server 2>&1 | tee server_debug.log
```

### Option B: Run without inference (API-only mode if exists)
```bash
python scripts/run.py --server --no-inference
```

### Option C: Test inference isolation
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -c "
from src.luna.engine import LunaEngine
print('Loading engine...')
e = LunaEngine()
print('Engine loaded, testing...')
r = e.process('hello')
print(f'Result: {r}')
"
```

---

## FILES TO EXAMINE

1. **`src/luna/api/server.py`** - `/message` endpoint handler
2. **`src/luna/engine.py`** - Main engine, `process()` method
3. **`src/luna/inference/`** - Local and delegation inference
4. **`scripts/run.py`** - Server startup, initialization order

---

## SUCCESS CRITERIA

- [ ] `/message` endpoint responds within 5s for simple queries
- [ ] Server logs show request entry AND exit
- [ ] No timeout errors in frontend
- [ ] Identify root cause (inference? db? async?)

---

## CONTEXT

This is blocking ALL chat functionality. The VK test showed 32.7% (Replicant status) but that's separate - this is the server not responding at all.

The server was working earlier today. Something changed or a resource got exhausted.
