"""
Luna Engine Tool System
========================

The tool registry and execution system for Luna's agentic capabilities.

This module provides:
- Tool: A dataclass defining a tool Luna can execute
- ToolResult: The result of executing a tool
- ToolRegistry: Registry for managing and executing tools

Based on Part XIV (Agentic Architecture) of the Luna Engine Bible.

Usage:
    from luna.tools import Tool, ToolResult, ToolRegistry
    from luna.tools.file_tools import register_file_tools
    from luna.tools.memory_tools import register_memory_tools, set_memory_matrix

    # Create registry
    registry = ToolRegistry()

    # Register built-in tools
    register_file_tools(registry)
    register_memory_tools(registry)

    # Connect memory matrix
    set_memory_matrix(memory_matrix)

    # Execute a tool
    result = await registry.execute("read_file", {"path": "/some/file.txt"})
"""

from .registry import Tool, ToolResult, ToolRegistry
from .file_tools import (
    read_file_tool,
    write_file_tool,
    list_directory_tool,
    file_exists_tool,
    get_file_info_tool,
    register_file_tools,
    ALL_FILE_TOOLS,
)
from .memory_tools import (
    memory_query_tool,
    memory_store_tool,
    memory_context_tool,
    memory_stats_tool,
    register_memory_tools,
    set_memory_matrix,
    get_memory_matrix,
    ALL_MEMORY_TOOLS,
)

__all__ = [
    # Core classes
    "Tool",
    "ToolResult",
    "ToolRegistry",
    # File tools
    "read_file_tool",
    "write_file_tool",
    "list_directory_tool",
    "file_exists_tool",
    "get_file_info_tool",
    "register_file_tools",
    "ALL_FILE_TOOLS",
    # Memory tools
    "memory_query_tool",
    "memory_store_tool",
    "memory_context_tool",
    "memory_stats_tool",
    "register_memory_tools",
    "set_memory_matrix",
    "get_memory_matrix",
    "ALL_MEMORY_TOOLS",
]


def create_default_registry() -> ToolRegistry:
    """
    Create a ToolRegistry with all default tools registered.

    Note: Memory tools require set_memory_matrix() to be called
    before they can be used.

    Returns:
        ToolRegistry with all built-in tools
    """
    registry = ToolRegistry()
    register_file_tools(registry)
    register_memory_tools(registry)
    return registry
