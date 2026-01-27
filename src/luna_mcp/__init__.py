"""
Luna-Hub-MCP-V1 — MCP Server for Luna Engine V2
================================================

This package provides the MCP (Model Context Protocol) server that bridges
Claude Desktop with Luna Engine. It runs a dedicated MCP API layer on port 8001.

Components:
- server.py: FastMCP entry point (run with: python -m luna_mcp.server)
- api.py: MCP API FastAPI server (port 8001)
- launcher.py: Auto-launch MCP API on "hey Luna"
- memory_log.py: Memory Matrix logging system
- tools/: Tool modules (filesystem, memory, state, git)
- security.py: Path validation and extension checks
- models.py: Pydantic models for all tools

Activation:
- "hey Luna" → Activates Luna context, auto-launches MCP API
- "later Luna" → Deactivates, flushes memories, closes port
"""

__version__ = "1.0.0"
__all__ = ["server", "api", "launcher", "memory_log", "models", "security"]
