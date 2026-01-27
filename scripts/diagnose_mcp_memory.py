#!/usr/bin/env python3
"""
MCP Memory Tools Diagnostic Script

Traces the entire data flow from tool to engine and back.
Run this to find where results get dropped.
"""

import asyncio
import httpx
import sys
from pathlib import Path

# Setup path
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

ENGINE_API = "http://localhost:8000"
MCP_API = "http://localhost:8742"
TEST_QUERY = "taco"


async def check_engine_health():
    """Check if engine is running."""
    print("\n" + "="*60)
    print("STEP 1: Check Engine Health")
    print("="*60)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ENGINE_API}/health")
            print(f"  Engine status: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code == 200
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


async def check_mcp_api_health():
    """Check if MCP API is running."""
    print("\n" + "="*60)
    print("STEP 2: Check MCP API Health")
    print("="*60)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{MCP_API}/health")
            print(f"  MCP API status: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code == 200
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


async def test_engine_search_direct():
    """Test engine search directly."""
    print("\n" + "="*60)
    print("STEP 3: Test Engine Search Directly")
    print("="*60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ENGINE_API}/memory/search",
                json={"query": TEST_QUERY, "limit": 5}
            )
            print(f"  Status: {response.status_code}")
            data = response.json()
            print(f"  Results count: {data.get('count', 'N/A')}")
            print(f"  Results type: {type(data.get('results'))}")
            if data.get('results'):
                print(f"  First result keys: {data['results'][0].keys()}")
                print(f"  First result preview: {str(data['results'][0])[:200]}")
            return data
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


async def test_mcp_api_search():
    """Test MCP API search."""
    print("\n" + "="*60)
    print("STEP 4: Test MCP API Search")
    print("="*60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MCP_API}/memory/search",
                json={"query": TEST_QUERY, "limit": 5}
            )
            print(f"  Status: {response.status_code}")
            data = response.json()
            print(f"  Results count: {data.get('count', 'N/A')}")
            print(f"  Results type: {type(data.get('results'))}")
            if data.get('results'):
                print(f"  First result keys: {data['results'][0].keys()}")
                print(f"  First result preview: {str(data['results'][0])[:200]}")
            else:
                print(f"  WARNING: No results returned!")
                print(f"  Full response: {data}")
            return data
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


async def test_call_api_function():
    """Test the _call_api function directly."""
    print("\n" + "="*60)
    print("STEP 5: Test _call_api() Function")
    print("="*60)

    try:
        from luna_mcp.tools.memory import _call_api

        result = await _call_api(
            "POST",
            "/memory/search",
            json={"query": TEST_QUERY, "limit": 5}
        )

        print(f"  Return type: {type(result)}")
        print(f"  Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        print(f"  Results count: {len(result.get('results', []))}")

        if result.get('results'):
            print(f"  First result: {result['results'][0]}")
        else:
            print(f"  WARNING: No results!")
            print(f"  Full return value: {result}")

        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_memory_matrix_search_tool():
    """Test the actual tool function."""
    print("\n" + "="*60)
    print("STEP 6: Test memory_matrix_search() Tool")
    print("="*60)

    try:
        from luna_mcp.tools.memory import memory_matrix_search

        result = await memory_matrix_search(TEST_QUERY, limit=5)

        print(f"  Return type: {type(result)}")
        print(f"  Return length: {len(result)}")
        print(f"  Contains 'No memories found': {'No memories found' in result}")
        print(f"  Contains 'Error': {'Error' in result}")
        print(f"\n  Full output:\n{'-'*40}\n{result}\n{'-'*40}")

        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_api_url():
    """Check what URL the tools are using."""
    print("\n" + "="*60)
    print("STEP 7: Check get_api_url()")
    print("="*60)

    try:
        from luna_mcp.launcher import get_api_url, _api_port

        url = get_api_url()
        print(f"  get_api_url() returns: {url}")
        print(f"  _api_port value: {_api_port}")

        return url
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


async def main():
    print("="*60)
    print("MCP MEMORY TOOLS DIAGNOSTIC")
    print("="*60)
    print(f"Test query: '{TEST_QUERY}'")
    print(f"Engine API: {ENGINE_API}")
    print(f"MCP API: {MCP_API}")

    # Run all diagnostics
    engine_ok = await check_engine_health()
    if not engine_ok:
        print("\n❌ Engine not running! Start it first.")
        return

    mcp_ok = await check_mcp_api_health()
    if not mcp_ok:
        print("\n❌ MCP API not running! Say 'hey Luna' first.")
        return

    await test_get_api_url()
    engine_results = await test_engine_search_direct()
    mcp_results = await test_mcp_api_search()
    call_api_results = await test_call_api_function()
    tool_results = await test_memory_matrix_search_tool()

    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"  Engine search:     {'✅ Has results' if engine_results and engine_results.get('results') else '❌ No results'}")
    print(f"  MCP API search:    {'✅ Has results' if mcp_results and mcp_results.get('results') else '❌ No results'}")
    print(f"  _call_api():       {'✅ Has results' if call_api_results and call_api_results.get('results') else '❌ No results'}")
    print(f"  Tool function:     {'✅ Has results' if tool_results and 'No memories found' not in tool_results else '❌ No results'}")

    # Find the break point
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)

    if not engine_results or not engine_results.get('results'):
        print("  🔴 BREAK POINT: Engine search returns no results")
        print("     → Check Memory Matrix / database")
    elif not mcp_results or not mcp_results.get('results'):
        print("  🔴 BREAK POINT: MCP API proxy returns no results")
        print("     → Check src/luna_mcp/api.py /memory/search endpoint")
    elif not call_api_results or not call_api_results.get('results'):
        print("  🔴 BREAK POINT: _call_api() returns no results")
        print("     → Check src/luna_mcp/tools/memory.py _call_api function")
        print("     → Possibly hitting wrong URL or parsing issue")
    elif tool_results and 'No memories found' in tool_results:
        print("  🔴 BREAK POINT: Tool function formats empty results")
        print("     → Check memory_matrix_search() response handling")
        print("     → Likely issue with 'results' key or empty check logic")
    else:
        print("  ✅ All layers returning data correctly!")
        print("     → Issue may be in FastMCP layer or Claude Desktop")


if __name__ == "__main__":
    asyncio.run(main())
