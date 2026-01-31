"""
MCP Server - Claude Code integration for Persona Forge.

Exposes forge tools as MCP tools for Claude Code and Claude Desktop.

Usage:
    # Run the server directly
    python -m persona_forge.mcp.server

    # Or import and use programmatically
    from persona_forge.mcp import mcp
    mcp.run()

Available Tools:
    Dataset Tools:
        - forge_load(path) - Load training data from JSONL
        - forge_assay() - Analyze current dataset
        - forge_gaps() - Get synthesis targets from assay
        - forge_mint(interaction_type, count) - Generate synthetic examples
        - forge_export(output_path, train_split) - Export training data
        - forge_status() - Get current session state

    Character Tools:
        - character_list() - List available profiles
        - character_load(profile_name) - Load a profile
        - character_modulate(trait_name, delta) - Adjust a trait
        - character_save(path) - Save current profile
        - character_show() - Get current profile info

    Voight-Kampff Tools:
        - vk_run(model_id, suite_name, verbose) - Run test suite
        - vk_list() - List available test suites
        - vk_probes(suite_name) - Get probes in a suite
"""

from .server import mcp, main

__all__ = ["mcp", "main"]
