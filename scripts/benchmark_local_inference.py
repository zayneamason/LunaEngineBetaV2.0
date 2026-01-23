"""Benchmark local inference speed."""
import asyncio
import time

async def benchmark():
    from luna.inference.local import LocalInference

    inf = LocalInference()

    print("Loading model...")
    start = time.time()
    await inf.load_model()
    print(f"Model loaded in {time.time() - start:.1f}s")

    # Warmup
    print("Warmup...")
    async for _ in inf.generate_stream("Hello", max_tokens=10):
        pass

    # Benchmark
    prompts = [
        "What is 2+2?",
        "Explain gravity in one sentence.",
    ]

    for prompt in prompts:
        print(f"\nPrompt: {prompt}")
        tokens = 0
        start = time.time()

        async for token in inf.generate_stream(prompt, max_tokens=50):
            tokens += 1
            print(token, end="", flush=True)

        elapsed = time.time() - start
        tok_per_sec = tokens / elapsed if elapsed > 0 else 0
        print(f"\n→ {tokens} tokens in {elapsed:.1f}s = {tok_per_sec:.1f} tok/s")

    print("\n" + "="*50)
    print("TARGET: 50+ tok/s (ideal), 20+ tok/s (minimum)")

if __name__ == "__main__":
    asyncio.run(benchmark())
