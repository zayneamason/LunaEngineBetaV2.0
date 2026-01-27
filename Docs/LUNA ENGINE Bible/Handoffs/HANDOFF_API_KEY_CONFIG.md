# HANDOFF: Fix Anthropic API Key Configuration

## Problem Statement

Luna Engine is timing out on all responses with this error:

```
Could not resolve authentication method. Expected either api_key or auth_token to be set.
Or for one of the `X-Api-Key` or `Authorization` headers to be explicitly omitted
```

The server starts fine, health checks pass, but any actual message triggers a timeout because the Claude API call fails — **no API key is configured**.

## Root Cause

No `.env` file exists in the Luna Engine project root:

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/.env
```

## Fix Required

### 1. Find the existing API key

Check these locations for an existing Anthropic API key:

```bash
# Check Eclessi project (likely has one)
cat /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/.env

# Check home directory
cat ~/.anthropic_api_key 2>/dev/null

# Check environment
echo $ANTHROPIC_API_KEY

# Check other common locations
grep -r "sk-ant-" ~/.config/ 2>/dev/null | head -5
```

### 2. Create `.env` file

Once you find the key, create the `.env` file:

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Create .env with the API key
echo "ANTHROPIC_API_KEY=sk-ant-XXXXX" > .env

# Verify
cat .env
```

### 3. Restart the server

```bash
# Kill existing
pkill -f "run.py.*server" 2>/dev/null
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Wait
sleep 2

# Restart
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
python scripts/run.py --server > /tmp/luna_backend.log 2>&1 &

# Wait for startup
sleep 5
```

### 4. Test

```bash
# Health check
curl -s http://localhost:8000/health

# Test actual message (should NOT timeout now)
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hey luna", "timeout": 30}'
```

**Expected result:** Actual response from Luna instead of timeout.

## Verification

Check the logs after restart:

```bash
tail -20 /tmp/luna_backend.log
```

Should see successful Claude API calls instead of:
```
❌ [DELEGATION] Failed: "Could not resolve authentication method..."
```

---

## If Key Not Found

If no existing key is found, Ahab needs to:

1. Go to https://console.anthropic.com/
2. Create/copy API key
3. Provide it to create the `.env` file

---

## Files Changed

| File | Action |
|------|--------|
| `.env` | CREATE with `ANTHROPIC_API_KEY=sk-ant-...` |

## Priority

**P0** — Luna cannot respond to any messages without this fix.
