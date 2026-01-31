#!/bin/bash
# Persona Forge MCP Server Launcher
# Run this script to start the MCP server

cd "$(dirname "$0")"
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m persona_forge.mcp.server
