#!/usr/bin/env python3
"""
Luna Inference Speed Diagnostic
================================
One-shot script that runs all 5 diagnostic steps from
Docs/HANDOFF_INFERENCE_SPEED_DIAGNOSTIC.md

Run from project root:
    python scripts/diagnostics/diagnose_inference.py

Output: which model loaded, tok/s without LoRA, tok/s with LoRA,
memory pressure, prompt token count. Everything the next session
needs to jump straight to a fix.
"""

import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("diagnose")

# ── Helpers ──────────────────────────────────────────────────────

PROMPT = "Tell me a short joke."
SYSTEM = "You are Luna, a witty AI companion."
MAX_TOKENS = 80
BENCH_ROUNDS = 2  # run generation twice; first may include JIT warmup

def memory_pressure() -> dict:
    """Grab macOS memory pressure stats."""
    info = {"pressure": "unknown", "free_pct": "unknown", "swap": "unknown"}
    try:
        out = subprocess.check_output(["memory_pressure"], timeout=5, text=True)
        for line in out.splitlines():
            if "free percentage" in line.lower():
                info["free_pct"] = line.strip()
            if "pressure" in line.lower() and "level" in line.lower():
                info["pressure"] = line.strip()
    except Exception as e:
        info["pressure"] = f"error: {e}"
    try:
        out = subprocess.check_output(["sysctl", "vm.swapusage"], timeout=5, text=True)
        info["swap"] = out.strip()
    except Exception:
        pass
    return info


def print_header(title: str):
    width = 60
    log.info("=" * width)
    log.info(f"  {title}")
    log.info("=" * width)


def print_result(label: str, value):
    log.info(f"  {label:.<40s} {value}")


# ── Steps ────────────────────────────────────────────────────────

async def step1_verify_model_path():
    """Step 1: Which model actually loads?"""
    print_header("STEP 1 — Verify Model Path")

    from luna.inference.local import (
        LocalInference, InferenceConfig,
        LOCAL_MODEL_PATH, LUNA_LORA_PATH, DEFAULT_MODEL, FALLBACK_MODEL,
    )

    print_result("LOCAL_MODEL_PATH exists", LOCAL_MODEL_PATH.exists())
    print_result("model.safetensors exists",
                 (LOCAL_MODEL_PATH / "model.safetensors").exists())
    print_result("LUNA_LORA_PATH exists", LUNA_LORA_PATH.exists())
    print_result("DEFAULT_MODEL (full-prec)", DEFAULT_MODEL)
    print_result("FALLBACK_MODEL (4-bit DL)", FALLBACK_MODEL)

    return {
        "local_exists": LOCAL_MODEL_PATH.exists(),
        "safetensors_exists": (LOCAL_MODEL_PATH / "model.safetensors").exists(),
        "lora_exists": LUNA_LORA_PATH.exists(),
    }


async def step2_baseline_no_lora():
    """Step 2: Benchmark WITHOUT LoRA adapter."""
    print_header("STEP 2 — Baseline (no LoRA)")

    import luna.inference.local as local_mod
    from luna.inference.local import LocalInference, InferenceConfig

    # Patch out LoRA auto-detection
    original_lora = local_mod.LUNA_LORA_PATH
    local_mod.LUNA_LORA_PATH = Path("/nonexistent_lora_path")

    config = InferenceConfig(adapter_path=None)
    inf = LocalInference(config)

    try:
        mem_before = memory_pressure()
        loaded = await inf.load_model()
        if not loaded:
            log.error(f"FAILED to load model: {inf._load_error}")
            return None

        print_result("Model loaded", True)
        print_result("Adapter loaded", inf._adapter_loaded)

        results = []
        for i in range(BENCH_ROUNDS):
            result = await inf.generate(PROMPT, system_prompt=SYSTEM, max_tokens=MAX_TOKENS)
            label = "warmup" if i == 0 else f"run {i}"
            print_result(f"  [{label}] tokens", result.tokens)
            print_result(f"  [{label}] latency_ms", f"{result.latency_ms:.0f}")
            print_result(f"  [{label}] tok/s", f"{result.tokens_per_second:.1f}")
            results.append(result)

        # Use the non-warmup run
        best = results[-1]
        mem_after = memory_pressure()

        print_result("Memory pressure (during)", mem_after.get("pressure", "?"))
        print_result("Swap usage", mem_after.get("swap", "?"))

        return {
            "tokens": best.tokens,
            "latency_ms": best.latency_ms,
            "tok_s": best.tokens_per_second,
            "text_preview": best.text[:80],
            "mem": mem_after,
        }
    finally:
        await inf.unload_model()
        local_mod.LUNA_LORA_PATH = original_lora
        # Give memory time to release
        await asyncio.sleep(1)


async def step3_with_lora():
    """Step 3: Benchmark WITH LoRA adapter."""
    print_header("STEP 3 — With LoRA")

    from luna.inference.local import LocalInference, InferenceConfig, LUNA_LORA_PATH

    if not LUNA_LORA_PATH.exists():
        log.warning("No LoRA adapter found — skipping step 3")
        return None

    config = InferenceConfig()  # defaults pick up LoRA via auto-detect
    inf = LocalInference(config)

    try:
        loaded = await inf.load_model()
        if not loaded:
            log.error(f"FAILED to load model with LoRA: {inf._load_error}")
            return None

        print_result("Model loaded", True)
        print_result("Adapter loaded", inf._adapter_loaded)

        results = []
        for i in range(BENCH_ROUNDS):
            result = await inf.generate(PROMPT, system_prompt=SYSTEM, max_tokens=MAX_TOKENS)
            label = "warmup" if i == 0 else f"run {i}"
            print_result(f"  [{label}] tokens", result.tokens)
            print_result(f"  [{label}] latency_ms", f"{result.latency_ms:.0f}")
            print_result(f"  [{label}] tok/s", f"{result.tokens_per_second:.1f}")
            results.append(result)

        best = results[-1]
        mem_after = memory_pressure()

        print_result("Memory pressure (during)", mem_after.get("pressure", "?"))
        print_result("Swap usage", mem_after.get("swap", "?"))

        return {
            "tokens": best.tokens,
            "latency_ms": best.latency_ms,
            "tok_s": best.tokens_per_second,
            "text_preview": best.text[:80],
            "mem": mem_after,
        }
    finally:
        await inf.unload_model()
        await asyncio.sleep(1)


async def step4_prompt_tokens():
    """Step 4: Check prompt token count."""
    print_header("STEP 4 — Prompt Token Count")

    from luna.inference.local import LocalInference, InferenceConfig

    # Minimal load just for tokenizer
    import luna.inference.local as local_mod
    original_lora = local_mod.LUNA_LORA_PATH
    local_mod.LUNA_LORA_PATH = Path("/nonexistent_lora_path")

    config = InferenceConfig(adapter_path=None)
    inf = LocalInference(config)

    try:
        loaded = await inf.load_model()
        if not loaded:
            log.warning("Could not load model for token counting")
            return None

        prompt = inf._format_prompt(PROMPT, SYSTEM)
        tokens = inf._tokenizer.encode(prompt)
        print_result("System prompt length (chars)", len(SYSTEM))
        print_result("Formatted prompt length (chars)", len(prompt))
        print_result("Prompt token count", len(tokens))

        if len(tokens) > 500:
            log.warning("Prompt >500 tokens — prefill will eat into latency budget")

        return {"prompt_tokens": len(tokens), "prompt_chars": len(prompt)}
    finally:
        await inf.unload_model()
        local_mod.LUNA_LORA_PATH = original_lora


# ── Summary ──────────────────────────────────────────────────────

def print_summary(s1, s2, s3, s4):
    print_header("SUMMARY")

    log.info("")
    log.info("  Model path resolution:")
    if s1:
        if s1["local_exists"] and s1["safetensors_exists"]:
            log.info("    OK — local 4-bit model found, should load from disk")
        else:
            log.info("    WARNING — local model missing, will download from HuggingFace")

    log.info("")
    log.info("  Generation speed:")
    if s2:
        print_result("    No LoRA", f"{s2['tok_s']:.1f} tok/s")
    if s3:
        print_result("    With LoRA", f"{s3['tok_s']:.1f} tok/s")

    if s2 and s3 and s2["tok_s"] > 0:
        ratio = s3["tok_s"] / s2["tok_s"]
        slowdown = (1 - ratio) * 100
        print_result("    LoRA overhead", f"{slowdown:.0f}% slower")
        if slowdown > 50:
            log.info("    >>> LoRA is the bottleneck. Consider fusing or reducing rank.")
        elif s2["tok_s"] < 10:
            log.info("    >>> Both slow. Likely memory pressure — check swap usage above.")
        else:
            log.info("    >>> Base speed OK. LoRA overhead acceptable.")
    elif s2 and s2["tok_s"] < 10:
        log.info("    >>> Slow WITHOUT LoRA. Problem is model/memory, not adapter.")

    log.info("")
    log.info("  Memory:")
    mem = (s3 or s2 or {}).get("mem", {})
    if "WARN" in str(mem.get("pressure", "")) or "CRITICAL" in str(mem.get("pressure", "")):
        log.info("    >>> MEMORY PRESSURE DETECTED — this machine is swapping during inference")
        log.info("    >>> Fix: fuse LoRA, close background apps, or move to beefier hardware")
    else:
        print_result("    Pressure", mem.get("pressure", "unknown"))
        print_result("    Swap", mem.get("swap", "unknown"))

    log.info("")
    log.info("  Prompt tokens:")
    if s4:
        print_result("    Token count", s4["prompt_tokens"])
        if s4["prompt_tokens"] > 1000:
            log.info("    >>> High token count — prefill dominates latency. Trim system prompt.")

    log.info("")
    log.info("  Next steps: see Docs/HANDOFF_INFERENCE_SPEED_DIAGNOSTIC.md § Fix Paths")
    log.info("")


# ── Main ─────────────────────────────────────────────────────────

async def main():
    log.info("Luna Inference Speed Diagnostic")
    log.info(f"Project root: {ROOT}")
    log.info("")

    s1 = await step1_verify_model_path()
    s2 = await step2_baseline_no_lora()
    s3 = await step3_with_lora()
    s4 = await step4_prompt_tokens()

    print_summary(s1, s2, s3, s4)


if __name__ == "__main__":
    asyncio.run(main())
