# Handoff Queue

Do these IN ORDER. One at a time. Don't start the next until the current one is done and verified.

| # | File | What | Priority |
|---|------|------|----------|
| 1 | bite-01-port-lockdown.md | Lock all ports to 8000/5173 | HIGH |
| 2 | bite-02-kill-hardcoded-urls.md | Remove all hardcoded backend URLs from frontend | HIGH |
| 3 | bite-03-vite-proxy.md | Fix Vite proxy to forward all routes | HIGH |
| 4 | bite-04-lunar-studio-tab.md | Embed existing Studio app, delete duplicate views | HIGH |
| 5 | bite-05-qa-module-placement.md | Give QA module a home | MEDIUM |
| 6 | bite-06-fix-memory-probe.md | Fix MatrixActor kwarg bug | HIGH |
| 7 | bite-07-fix-qa-sweep.md | Fix QAReport dict access bug | HIGH |
| 8 | bite-08-engine-control-mcp.md | Add aperture/voice/LLM/consciousness MCP tools | MEDIUM |
| 9 | bite-09-qa-pipeline-control-mcp.md | Add live QA pipeline control MCP tools | MEDIUM |

## Rules

- Read the bite file. Do exactly what it says. Nothing more.
- Do NOT build new components unless the bite explicitly says to.
- Do NOT use regex on YAML files.
- Do NOT rename Python files, class names, or MCP tool names (Path C).
- When done, say what you did and what file(s) you touched. Then wait.
