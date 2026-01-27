"""
Unit tests for MCP memory tools data flow.

Tests each layer independently to isolate where data gets dropped.
"""

import pytest
import httpx
import asyncio
from unittest.mock import patch, AsyncMock

# Test configuration
ENGINE_API = "http://localhost:8000"
MCP_API = "http://localhost:8742"


class TestEngineAPIDirectly:
    """Test the engine API works correctly."""

    @pytest.mark.asyncio
    async def test_engine_search_returns_results(self):
        """Engine API should return results for known query."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ENGINE_API}/memory/search",
                json={"query": "taco", "limit": 5}
            )

        assert response.status_code == 200
        data = response.json()

        print(f"Engine API response: {data}")

        assert "results" in data
        assert "count" in data
        assert data["count"] > 0, "Engine should have taco memories"
        assert len(data["results"]) > 0


class TestMCPAPIDirectly:
    """Test the MCP API proxy works correctly."""

    @pytest.mark.asyncio
    async def test_mcp_api_search_returns_results(self):
        """MCP API should proxy results from engine."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MCP_API}/memory/search",
                json={"query": "taco", "limit": 5}
            )

        assert response.status_code == 200
        data = response.json()

        print(f"MCP API response: {data}")

        assert "results" in data
        assert "count" in data
        assert data["count"] > 0, "MCP API should proxy taco memories"
        assert len(data["results"]) > 0

    @pytest.mark.asyncio
    async def test_mcp_api_response_structure(self):
        """Verify response structure matches what tools expect."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MCP_API}/memory/search",
                json={"query": "taco", "limit": 5}
            )

        data = response.json()

        # Check structure
        assert isinstance(data.get("results"), list)

        if data["results"]:
            result = data["results"][0]
            print(f"Result structure: {result.keys()}")

            # Check expected fields
            assert "id" in result or "node_id" in result
            assert "content" in result
            # Note: might be 'type' or 'node_type' - check which!
            has_type = "type" in result or "node_type" in result
            assert has_type, f"Result missing type field: {result.keys()}"


class TestMCPToolsDirectly:
    """Test the MCP tool functions directly (bypassing FastMCP)."""

    @pytest.mark.asyncio
    async def test_memory_matrix_search_function(self):
        """Test the actual tool function."""
        # Import the tool
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.tools.memory import memory_matrix_search

        result = await memory_matrix_search("taco", limit=5)

        print(f"Tool function result:\n{result}")

        # Should NOT say "No memories found"
        assert "No memories found" not in result, f"Tool returned no results: {result}"
        assert "Error" not in result, f"Tool returned error: {result}"

        # Should have formatted results
        assert "Search Results" in result or "[" in result

    @pytest.mark.asyncio
    async def test_luna_smart_fetch_function(self):
        """Test the smart fetch tool function."""
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.tools.memory import luna_smart_fetch

        result = await luna_smart_fetch("taco", budget_preset="balanced")

        print(f"Smart fetch result:\n{result}")

        # Should have some content
        assert "Error" not in result, f"Tool returned error: {result}"


class TestCallAPIFunction:
    """Test the _call_api helper directly."""

    @pytest.mark.asyncio
    async def test_call_api_returns_dict(self):
        """Verify _call_api returns proper dict."""
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.tools.memory import _call_api

        result = await _call_api(
            "POST",
            "/memory/search",
            json={"query": "taco", "limit": 5}
        )

        print(f"_call_api result type: {type(result)}")
        print(f"_call_api result: {result}")

        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) > 0


class TestResponseFormatting:
    """Test that response formatting handles the data correctly."""

    def test_format_with_node_type_key(self):
        """Test formatting when response uses 'node_type' key."""
        response = {
            "results": [
                {"id": "abc", "node_type": "FACT", "content": "Test content"},
                {"id": "def", "node_type": "ACTION", "content": "More content"},
            ],
            "count": 2
        }

        # Simulate the formatting logic
        results = response.get('results', [])
        assert len(results) == 2

        for r in results:
            node_type = r.get('node_type', r.get('type', '?'))
            assert node_type != '?', f"Failed to get type from: {r.keys()}"

    def test_format_with_type_key(self):
        """Test formatting when response uses 'type' key."""
        response = {
            "results": [
                {"id": "abc", "type": "FACT", "content": "Test content"},
            ],
            "count": 1
        }

        results = response.get('results', [])
        for r in results:
            node_type = r.get('node_type', r.get('type', '?'))
            assert node_type == 'FACT'


class TestGetAPIURL:
    """Test the get_api_url() function."""

    def test_get_api_url_returns_correct_url(self):
        """Verify we're hitting the right URL."""
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.launcher import get_api_url

        url = get_api_url()
        print(f"get_api_url() returns: {url}")

        # Should be MCP API, not engine
        assert "8742" in url or "8001" in url, f"Unexpected URL: {url}"
        assert "localhost" in url or "127.0.0.1" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
