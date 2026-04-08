#!/usr/bin/env python3
"""
Luna Engine Entry Point
=======================

Start the engine and process messages.

Usage:
    python scripts/run.py                    # Rich console mode (default)
    python scripts/run.py --simple           # Simple interactive mode
    python scripts/run.py --message "Hello"  # Single message
    python scripts/run.py --server           # HTTP API server
    python scripts/run.py --server --port 8080
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env file if present
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, rely on shell environment

from luna.engine import LunaEngine, EngineConfig


async def run_interactive(engine: LunaEngine) -> None:
    """Run in interactive mode."""
    print("\n" + "="*60)
    print("  Luna Engine v2.0 - Phase 1")
    print("  Type a message and press Enter. Type 'quit' to exit.")
    print("="*60 + "\n")

    # Response handler
    async def on_response(text: str, data: dict) -> None:
        # Build model indicator
        if data.get("delegated"):
            model_tag = "⚡ delegated"
        elif data.get("local"):
            model_tag = "● local"
        elif data.get("fallback"):
            model_tag = "☁ cloud"
        else:
            model_tag = data.get("model", "unknown")

        print(f"\n[Luna]: {text}")
        print(f"  ({data.get('output_tokens', 0)} tokens, {data.get('latency_ms', 0):.0f}ms, {model_tag})\n")
        print("> ", end="", flush=True)

    engine.on_response(on_response)

    # Start engine in background
    engine_task = asyncio.create_task(engine.run())

    # Wait a moment for engine to start
    await asyncio.sleep(0.5)

    try:
        while True:
            try:
                # Read input
                print("> ", end="", flush=True)
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                line = line.strip()

                if not line:
                    continue

                if line.lower() in ("quit", "exit", "q"):
                    break

                if line.lower() == "status":
                    status = engine.status()
                    print(f"\nStatus: {status}\n")
                    continue

                # Send message
                await engine.send_message(line)

            except EOFError:
                break

    finally:
        await engine.stop()
        await engine_task


async def run_single_message(engine: LunaEngine, message: str) -> None:
    """Process a single message."""
    response_received = asyncio.Event()
    response_text = None

    async def on_response(text: str, data: dict) -> None:
        nonlocal response_text
        response_text = text
        # Build model indicator
        if data.get("delegated"):
            model_tag = "⚡ delegated"
        elif data.get("local"):
            model_tag = "● local"
        elif data.get("fallback"):
            model_tag = "☁ cloud"
        else:
            model_tag = data.get("model", "unknown")

        print(f"\n[Luna]: {text}")
        print(f"\n({data.get('output_tokens', 0)} tokens, {data.get('latency_ms', 0):.0f}ms, {model_tag})")
        response_received.set()

    engine.on_response(on_response)

    # Start engine
    engine_task = asyncio.create_task(engine.run())

    # Wait for startup
    await asyncio.sleep(0.5)

    try:
        # Send message
        print(f"\n[You]: {message}")
        await engine.send_message(message)

        # Wait for response (with timeout)
        await asyncio.wait_for(response_received.wait(), timeout=30.0)

    except asyncio.TimeoutError:
        print("\nTimeout waiting for response")

    finally:
        await engine.stop()
        await engine_task


def _kill_stale_server(port: int) -> None:
    """Kill any stale process holding the given port (prevents Errno 48)."""
    import subprocess
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = result.stdout.strip().split()
        if pids:
            my_pid = str(os.getpid())
            stale = [p for p in pids if p != my_pid]
            if stale:
                print(f"  [port guard] Killing stale process(es) on :{port}: {', '.join(stale)}")
                subprocess.run(["kill", "-9"] + stale, timeout=5)
                import time
                time.sleep(0.5)  # Let OS release the socket
    except Exception as e:
        print(f"  [port guard] Could not check port {port}: {e}")


def run_server(host: str, port: int) -> None:
    """Run the HTTP API server."""
    import uvicorn
    from luna.api.server import app

    # Kill any stale process holding our port
    _kill_stale_server(port)

    print("\n" + "="*60)
    print("  Luna Engine v2.0 - HTTP API Server")
    print(f"  Running on http://{host}:{port}")
    print("  Endpoints:")
    print("    POST /message  - Send message to Luna")
    print("    GET  /status   - Engine status")
    print("    GET  /health   - Health check")
    print("="*60 + "\n")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


async def run_console(engine: LunaEngine) -> None:
    """Run the Rich-based console UI."""
    from luna.cli.console import LunaConsole

    # Start engine in background
    engine_task = asyncio.create_task(engine.run())

    # Wait for engine to start
    await asyncio.sleep(0.5)

    try:
        console = LunaConsole(engine)
        await console.run()
    finally:
        await engine.stop()
        await engine_task


def main():
    parser = argparse.ArgumentParser(description="Luna Engine v2.0")
    parser.add_argument("--message", "-m", help="Send a single message")
    parser.add_argument("--server", "-s", action="store_true", help="Run HTTP API server")
    parser.add_argument("--simple", action="store_true", help="Use simple interactive mode (no Rich)")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.debug else logging.WARNING  # Quieter for Rich console
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Quiet some noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Run in appropriate mode
    if args.server:
        # Enable diagnostics for key engine modules (default WARNING is too quiet)
        logging.getLogger("luna.engine").setLevel(logging.INFO)
        logging.getLogger("luna.substrate.aibrarian_engine").setLevel(logging.INFO)
        run_server(args.host, args.port)
    elif args.message:
        logging.getLogger().setLevel(logging.INFO)
        config = EngineConfig()
        engine = LunaEngine(config)
        asyncio.run(run_single_message(engine, args.message))
    elif args.simple:
        logging.getLogger().setLevel(logging.INFO)
        config = EngineConfig()
        engine = LunaEngine(config)
        asyncio.run(run_interactive(engine))
    else:
        # Default: Rich console
        config = EngineConfig()
        engine = LunaEngine(config)
        asyncio.run(run_console(engine))


if __name__ == "__main__":
    main()
