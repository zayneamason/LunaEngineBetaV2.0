# Bite 9 — MCP Tools for Live QA Pipeline Control

Add MCP tools for active QA pipeline control — beyond the read-only diagnostics that already exist. These let Claude Desktop inspect, test, and compare pipeline behavior in real time.

## Tools to add

### qa_node_status
Get pass/warn/fail status for each pipeline node right now.
- Hit `/api/diagnostics/pipeline` and extract `node_status` from the response
- Return a clean map: `{ "director": "pass", "memory_matrix": "fail", "identity_faceid": "warn" }`

### qa_force_revalidate(assertion_ids)
Re-run specific assertion(s) against last inference. Not a full sweep — targeted.
- Takes a comma-separated list of assertion IDs (e.g. "R1,R3,V1")
- Runs only those assertions against the cached last inference context
- Returns results for just those assertions
- May need a new endpoint: POST `/api/diagnostics/trigger/revalidate` with `{ "assertion_ids": ["R1", "R3"] }`

### qa_assertion_history(assertion_id, count)
Get pass/fail trend for a specific assertion over the last N inferences.
- Query `qa.db` for the last N reports that include this assertion
- Return: `[{ "timestamp": ..., "passed": true/false, "detail": "..." }, ...]`
- May need a new endpoint or can query the DB directly via engine_client fallback

### qa_inject_test(message)
Send a test message through the full pipeline and return complete QA results WITHOUT affecting conversation state.
- Runs the message through assembler → director → QA validator
- Does NOT save to session history or memory
- Returns: routing decision, assembled prompt length, all assertion results, node status
- Needs a new endpoint: POST `/api/diagnostics/trigger/test-inference` with `{ "message": "..." }`

### qa_compare(message, param, value_a, value_b)
Run same message through pipeline twice with different settings, diff the results.
- Example: `qa_compare("tell me about Hai Dai", "aperture_mode", "focused", "open")`
- Returns side-by-side assertion results, token counts, memory retrieval differences
- Needs a new endpoint or can orchestrate via two calls to test-inference with param changes

## Implementation

- `qa_node_status` and `qa_assertion_history` can use existing endpoints/DB
- `qa_force_revalidate`, `qa_inject_test`, and `qa_compare` need new `/api/diagnostics/trigger/*` endpoints
- Create the endpoints in `src/luna/api/diagnostics.py` (or inline in server.py)
- Create the MCP tool wrappers following the engine_client.py pattern
- Register in server.py

The goal: Claude Desktop can poke at Luna's pipeline, run test messages, compare configurations, and watch assertion trends — all without disrupting live conversation.
