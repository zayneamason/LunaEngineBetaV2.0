# HANDOFF V3: Engine Fixes + Demo Features

Download the docx from Claude conversation.

## Quick Summary

### Part A: Engine Fixes (All Builds)
1. **sqlite-vec** — compile Python with --enable-loadable-sqlite-extensions (or static link)
2. **Singleton guard** — check port before bind, open browser to existing instance
3. **WATCHDOG seed-mode** — detect fresh/young/mature instances, adjust thresholds
4. **Warning suppression** — compiled builds log to DEBUG not console
5. **LunaFM config** — Forge must copy config/lunafm/ to build output
6. **Hardcoded dataroom** — grep and remove from search chain

### Part B: Demo Features (Ambassador Build ONLY)
7. **Preloaded API keys** — bake keys into secrets.json, mask in UI, 4444 keyboard unlock
8. **Pre-flight tracer** — fires live test through LLM, Nexus, Memory, returns checklist
9. **Jumpstart button** — soft reboot of pipeline actors, rotates LLM fallback, fires tracer
10. **Demo reset slider puzzle** — wipes conversations/memory/owner, keeps keys/collections

## CRITICAL
- Task 10 (demo reset) is gated behind `demo_mode: true`. Dev builds NEVER see it.
- `demo_mode` defaults to false. Only hai-dai.yaml sets it to true.
