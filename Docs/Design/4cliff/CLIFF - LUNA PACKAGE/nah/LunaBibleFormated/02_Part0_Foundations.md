# Part 0: Foundations
## The Fundamental Insight

**Version:** 3.0
**Last Updated:** 2026-01-30
**Status:** Current

---

## What Are We Actually Building?

This is the insight that makes everything else make sense:

> **"We are not building an LLM. We are building everything around it."**

The LLM — whether it's Claude API or a local Qwen model — is like a **graphics card**. It's a specialized compute resource that does one thing extremely well (inference), but it doesn't run the show. It renders frames when asked.

**We're building the game engine.**

---

## The GPU Analogy

### How a Game Engine Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        GAME ENGINE                              │
│                                                                 │
│   • Input handling (keyboard, mouse, controller)                │
│   • Game state (player position, inventory, world)              │
│   • Physics simulation                                          │
│   • Audio management                                            │
│   • Asset loading                                               │
│   • Scene management                                            │
│   • Networking                                                  │
│   • Save/load                                                   │
│                                                                 │
│   The engine CALLS the GPU when it needs to render.             │
│   The GPU doesn't know about game state. It just draws.         │
│                                                                 │
│   ┌─────────┐                                                   │
│   │   GPU   │ ◄─── "Here's geometry. Draw it."                  │
│   │         │                                                   │
│   │ Shaders │      Returns: pixels                              │
│   │ Textures│                                                   │
│   │ Rasterize│     Doesn't know: what those pixels mean         │
│   └─────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### How Luna Engine Works

```
┌─────────────────────────────────────────────────────────────────┐
│                       LUNA ENGINE                               │
│                                                                 │
│   • Input handling (voice, desktop, MCP)                        │
│   • Consciousness state (attention, personality, mood)          │
│   • Memory management (store, retrieve, forget)                 │
│   • Audio management (STT, TTS)                                 │
│   • Context loading (what memories to inject)                   │
│   • Conversation management                                     │
│   • Tool orchestration                                          │
│   • Persistence (snapshots, journals)                           │
│                                                                 │
│   The engine CALLS the LLM when it needs to think.              │
│   The LLM doesn't know about state. It just predicts tokens.    │
│                                                                 │
│   ┌─────────┐                                                   │
│   │   LLM   │ ◄─── "Here's context. Generate response."         │
│   │         │                                                   │
│   │Attention│      Returns: tokens                              │
│   │ Weights │                                                   │
│   │Generate │      Doesn't know: who it is across calls         │
│   └─────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Core Principle

> **"The LLM is stateless inference. Luna is stateful identity."**

---

**Page 3 of 5**
