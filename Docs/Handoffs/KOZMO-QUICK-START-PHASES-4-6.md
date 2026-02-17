# KOZMO Phases 4-6 Quick Start Guide

**Goal:** Get WebSocket sync, usage tracking, and scene generation working in under 15 minutes.

---

## Prerequisites

- Luna Engine v2.0 running
- Node.js 18+
- Python 3.11+
- MongoDB (for production) OR SQLite (for testing)

---

## 1. Install Dependencies

### Backend (Python)
```bash
cd /path/to/LunaEngine_BetaProject_V2.0_Root

# Install Python packages
pip install motor anthropic  # MongoDB + Claude SDK
```

### Frontend (React)
```bash
cd Tools/KOZMO-Prototype-V1

# Already installed if you ran `npm install` before
# If not:
npm install
```

---

## 2. Set Environment Variables

Create/edit `.env` file:

```bash
# KOZMO Database (choose one)
KOZMO_MONGO_URI=mongodb://localhost:27017  # MongoDB (production)
# OR
KOZMO_SQLITE_PATH=data/kozmo_test.db       # SQLite (testing)

# Claude API (for scene generation)
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE
```

---

## 3. Start MongoDB (if using)

### macOS
```bash
brew install mongodb-community
brew services start mongodb-community

# Test connection
mongosh
```

### Linux/Windows
See: https://www.mongodb.com/docs/manual/installation/

---

## 4. Update Luna API Server

Edit `src/luna/api/server.py` to include KOZMO routes:

```python
# Add to imports
from luna.services.kozmo.routes import router as kozmo_router

# Add to app.include_router() section
app.include_router(kozmo_router)
```

---

## 5. Start Backend

```bash
python scripts/run.py  # Luna Engine server on :8000
```

**Verify:**
- Navigate to http://localhost:8000/docs
- Look for `/kozmo/*` endpoints in Swagger UI

---

## 6. Start Frontend

```bash
cd Tools/KOZMO-Prototype-V1
npm run dev  # Vite server on :5174
```

**Verify:**
- Navigate to http://localhost:5174
- Should see KOZMO interface

---

## 7. Test WebSocket Connection

Open browser console (F12) and run:

```javascript
const ws = new WebSocket('ws://localhost:8000/kozmo/ws/test-project');

ws.onopen = () => console.log('✅ WebSocket connected');
ws.onmessage = (e) => console.log('📨 Message:', JSON.parse(e.data));
ws.onerror = (e) => console.error('❌ Error:', e);

// Send ping
ws.send(JSON.stringify({type: 'ping'}));
// Should receive: {"type": "pong"}
```

---

## 8. Test Entity Update Broadcast (Phase 4)

### Terminal 1: Start watching logs
```bash
tail -f logs/luna.log | grep "WebSocket"
```

### Terminal 2: Update entity
```bash
curl -X PUT http://localhost:8000/kozmo/projects/test-project/entities/character/alice_chen/sync \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Wong", "color": "#c084fc"}'
```

### Browser: Open 2 tabs
1. Tab A: Open scene with "Alice Chen"
2. Tab B: Change entity name to "Alice Wong"
3. **Expected:** Tab A shows notification toast

---

## 9. Test Reverse Index (Phase 5)

### Rebuild index
```bash
curl -X POST http://localhost:8000/kozmo/projects/test-project/reverse-index/rebuild
```

### Get entity usage
```bash
curl http://localhost:8000/kozmo/projects/test-project/entities/alice_chen/usage
```

**Expected Response:**
```json
{
  "entity_slug": "alice_chen",
  "entity_name": "Alice Chen",
  "total_scenes": 5,
  "first_appearance": "scene_001",
  "last_appearance": "scene_010",
  "scenes": [
    {
      "scene_slug": "scene_001",
      "scene_title": "Opening",
      "scene_number": 1,
      "reference_type": "frontmatter",
      "field": "characters_present"
    }
  ]
}
```

---

## 10. Test Scene Generation (Phase 6)

### Estimate cost first
```bash
curl -X POST http://localhost:8000/kozmo/projects/test-project/scenes/generate/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "character_slugs": ["alice_chen"],
    "location_slug": "tech_noir",
    "goal": "Alice discovers the truth",
    "style": "fountain"
  }'
```

**Response:**
```json
{
  "estimated_input_tokens": 400,
  "estimated_output_tokens": 200,
  "estimated_cost_usd": 0.0042,
  "model": "claude-sonnet-4-20250514"
}
```

### Generate scene
```bash
curl -X POST http://localhost:8000/kozmo/projects/test-project/scenes/generate \
  -H "Content-Type: application/json" \
  -d '{
    "character_slugs": ["alice_chen", "bob_jones"],
    "location_slug": "tech_noir",
    "goal": "Tense confrontation about stolen data",
    "style": "fountain"
  }'
```

**Expected:** Generated Fountain scene with atmosphere, character intros, dialogue

---

## Troubleshooting

### "WebSocket connection failed"
- ✅ Luna Engine running on :8000?
- ✅ CORS enabled in FastAPI?
- ✅ Firewall blocking WebSocket?

### "Module 'motor' not found"
```bash
pip install motor  # MongoDB async driver
```

### "ANTHROPIC_API_KEY not set"
- Add to `.env` file
- Restart Luna Engine
- Get API key: https://console.anthropic.com/

### "Database connection failed"
- MongoDB running? `brew services list`
- Correct URI? Check `KOZMO_MONGO_URI`
- Try SQLite for testing instead

### "Entity usage returns empty"
- Run rebuild: `POST /reverse-index/rebuild`
- Check scenes have frontmatter with entity slugs
- Verify entity slugs match exactly

---

## Integration Checklist

- [ ] MongoDB or SQLite running
- [ ] `.env` file configured
- [ ] Luna Engine includes KOZMO routes
- [ ] Backend starts without errors
- [ ] Frontend connects to backend
- [ ] WebSocket connection works
- [ ] Entity update broadcasts
- [ ] Reverse index builds successfully
- [ ] Scene generation works (if API key set)

---

## Next Steps

Once basic setup works:

1. **Wire Frontend WebSocket** - Integrate `useWebSocket` into `KozmoProvider`
2. **Add Usage Panel** - Show `EntityUsagePanel` in CODEX sidebar
3. **Test Real-Time Updates** - Two users editing same project
4. **Performance Tune** - Index large projects (100+ scenes)
5. **Add Conflict Resolution** - Handle simultaneous edits

---

## Production Deployment

For production use:

1. **Use MongoDB** (not SQLite)
2. **Add Redis** for WebSocket scaling
3. **Enable CORS** properly (not `allow_origins=["*"]`)
4. **Rate Limit** scene generation
5. **Monitor Costs** for Claude API usage
6. **Add User Auth** to WebSocket connections

---

## Getting Help

- **Full Handoff Doc:** `Docs/Handoffs/KOZMO-PHASES-4-5-6-IMPLEMENTATION-HANDOFF.md`
- **Architecture:** `Docs/ARCHITECTURE_KOZMO.md`
- **Luna Engine Docs:** `Docs/bible/`
- **Issues:** https://github.com/anthropics/claude-code/issues

---

**Last Updated:** 2026-02-11
**Implemented By:** Claude Code (Sonnet 4.5)
