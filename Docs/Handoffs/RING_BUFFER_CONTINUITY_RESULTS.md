# Ring Buffer Continuity Diagnostic Results

**Date:** 2026-02-03
**Investigator:** Claude Code
**Status:** ✅ Voice is preserved correctly

---

## 1. Executive Summary

**Finding:** The ring buffer correctly preserves Luna's voice across turns.

- Content stored verbatim (no sanitization)
- Role translated to "Luna" when formatting for prompt
- Emoji, punctuation, and style markers preserved

**No fix needed.**

---

## 2. Ring Buffer Implementation

**File:** [src/luna/memory/ring.py](src/luna/memory/ring.py)

### Storage (Lines 52-63)

```python
def add(self, role: str, content: str) -> None:
    """Add a turn to the buffer. Oldest evicted if full."""
    self._buffer.append(Turn(role=role, content=content))  # Verbatim!

def add_assistant(self, content: str) -> None:
    """Convenience: add an assistant turn."""
    self.add("assistant", content)  # Stored as "assistant" internally
```

✅ **Content is verbatim** — no sanitization, cleaning, or normalization.

### Retrieval for Prompt (Lines 105-124)

```python
def format_for_prompt(
    self,
    user_name: str = "Ahab",
    assistant_name: str = "Luna"
) -> str:
    lines = []
    for i, turn in enumerate(self._buffer):
        name = user_name if turn.role == "user" else assistant_name
        lines.append(f"[{i+1}] {name}: {turn.content}")
    return "\n".join(lines)
```

✅ **"assistant" → "Luna"** when formatting for prompt
✅ **Content remains verbatim** including emoji

---

## 3. Test Results

### Input

```python
ring.add_user("hey Luna")
ring.add_assistant("yo! what's good? been thinking about that project we discussed 💜")
ring.add_user("tell me more")
ring.add_assistant("honestly... it's kinda wild how things are coming together 🤔")
```

### format_for_prompt() Output (Used in system prompt)

```
[1] Ahab: hey Luna
[2] Luna: yo! what's good? been thinking about that project we discussed 💜
[3] Ahab: tell me more
[4] Luna: honestly... it's kinda wild how things are coming together 🤔
```

✅ **Voice preserved:**
- "Luna" label (not "assistant")
- Emoji retained (💜, 🤔)
- Punctuation intact ("yo!", "...")
- Casual phrasing preserved ("kinda", "what's good?")

### get_as_dicts() Output (Used for Claude API)

```python
{'role': 'user', 'content': 'hey Luna'}
{'role': 'assistant', 'content': "yo! what's good? been thinking about that project we discussed 💜"}
...
```

- Uses "assistant" role (required by Claude API)
- Content still verbatim

---

## 4. How History Reaches the LLM

### Path for Local Inference (LoRA)

```
1. Ring stores turns with content verbatim
2. Pipeline calls ring.format_for_prompt()
3. Result: "[1] Ahab: ...\n[2] Luna: ..."
4. This goes into system_prompt
5. System prompt is passed to _local.generate()
6. LoRA sees history with "Luna:" labels
```

✅ **Voice preserved throughout.**

### Path for Claude API (Delegation)

```
1. Ring stores turns with content verbatim
2. Pipeline calls ring.get_as_dicts()
3. Result: [{"role": "assistant", "content": "..."}]
4. This goes into messages array
5. Claude API receives messages with "assistant" role
```

Note: Claude API requires `role: "assistant"`, not custom names. But content is still verbatim.

---

## 5. Verification Checklist

| Question | Answer |
|----------|--------|
| Is content stored verbatim? | ✅ Yes |
| Are emoji preserved? | ✅ Yes |
| Is punctuation preserved? | ✅ Yes |
| Is voice styling preserved? | ✅ Yes |
| Is role "Luna" in prompt? | ✅ Yes (via format_for_prompt) |
| Does history reach LLM? | ✅ Yes |

---

## 6. Conclusion

**The ring buffer is NOT the problem.**

Voice continuity is correctly implemented:
1. Storage is verbatim
2. Format uses "Luna" label
3. All voice markers preserved

If Luna's voice is inconsistent across turns, the cause is elsewhere (likely was the voice examples pollution, now fixed).

---

*The river flows unobstructed. Voice momentum should carry.*
