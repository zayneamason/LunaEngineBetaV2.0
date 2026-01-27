"""
Auto-launcher for Luna MCP API
==============================

Starts the MCP API server on demand, with:
- Port conflict detection
- Automatic port fallback (8001 → 8002 → 8003 → 8004 → 8005)
- Health check before returning
- Graceful shutdown on MCP exit
"""

import asyncio
import subprocess
import sys
import socket
import time
import atexit
from pathlib import Path
from typing import Optional
import httpx

# Configuration
DEFAULT_PORT = 8742  # Unique port to avoid conflicts
MAX_PORT_ATTEMPTS = 5
HEALTH_CHECK_TIMEOUT = 10.0
HEALTH_CHECK_INTERVAL = 0.3

# Global state
_api_process: Optional[subprocess.Popen] = None
_api_port: Optional[int] = None


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def find_available_port(start_port: int = DEFAULT_PORT, max_attempts: int = MAX_PORT_ATTEMPTS) -> int:
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts - 1}")


async def check_api_health(port: int, timeout: float = HEALTH_CHECK_TIMEOUT) -> bool:
    """Check if MCP API is healthy."""
    url = f"http://127.0.0.1:{port}/health"
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            try:
                response = await client.get(url, timeout=1.0)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    return False


def start_api_server(port: int) -> subprocess.Popen:
    """Start the MCP API server as a subprocess."""
    src_path = Path(__file__).parent.parent.resolve()

    process = subprocess.Popen(
        [sys.executable, "-m", "luna_mcp.api", "--port", str(port)],
        cwd=str(src_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # Don't inherit parent's stdin to avoid blocking
        stdin=subprocess.DEVNULL,
    )

    return process


def stop_api_server():
    """Stop the MCP API server."""
    global _api_process
    if _api_process and _api_process.poll() is None:
        _api_process.terminate()
        try:
            _api_process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _api_process.kill()
        _api_process = None


# Register cleanup on exit
atexit.register(stop_api_server)


async def ensure_api_running() -> int:
    """
    Ensure MCP API is running, starting it if necessary.

    Returns the port the API is running on.
    """
    global _api_process, _api_port

    # Check if already running (our process)
    if _api_process and _api_process.poll() is None:
        if _api_port and await check_api_health(_api_port, timeout=2.0):
            return _api_port

    # Check if already running (external process)
    for port in range(DEFAULT_PORT, DEFAULT_PORT + MAX_PORT_ATTEMPTS):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("api") == "mcp":
                        _api_port = port
                        return port
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

    # Start new server
    port = find_available_port()
    _api_process = start_api_server(port)

    # Wait for health check
    if await check_api_health(port):
        _api_port = port
        return port
    else:
        stop_api_server()
        raise RuntimeError(f"MCP API failed to start on port {port}")


def get_api_url() -> str:
    """Get the MCP API URL."""
    if _api_port:
        return f"http://127.0.0.1:{_api_port}"
    return f"http://127.0.0.1:{DEFAULT_PORT}"


def get_current_port() -> Optional[int]:
    """Get the current MCP API port, or None if not running."""
    return _api_port
