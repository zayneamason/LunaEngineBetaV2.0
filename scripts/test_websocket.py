#!/usr/bin/env python3
"""Stress test WebSocket connection."""
import asyncio
import json
import time
import sys

try:
    import websockets
except ImportError:
    print("❌ websockets module not installed. Run: pip install websockets")
    sys.exit(1)

async def test_connection_stability():
    print("Testing WebSocket stability (10 seconds)...")
    uri = "ws://localhost:8000/ws/orb"
    try:
        async with websockets.connect(uri) as ws:
            print(f"✅ Connected to {uri}")
            messages = 0
            start = time.time()
            while time.time() - start < 10:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    messages += 1
                    if messages <= 5:
                        try:
                            data = json.loads(msg)
                            print(f"  [{messages}] {data.get('type', 'unknown')}: {str(data)[:80]}")
                        except:
                            print(f"  [{messages}] Raw: {msg[:80]}")
                except asyncio.TimeoutError:
                    print(f"  ⚠️ No message for 2s (total: {messages})")
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"  ❌ Connection closed: {e}")
                    return False
            print(f"✅ Stable: {messages} messages in 10s")
            return True
    except ConnectionRefusedError:
        print(f"❌ Connection refused - is server running on {uri}?")
        return False
    except Exception as e:
        print(f"❌ Failed: {type(e).__name__}: {e}")
        return False

async def test_rapid_reconnect():
    print("\nTesting rapid reconnect (5 cycles)...")
    uri = "ws://localhost:8000/ws/orb"
    success = 0
    for i in range(5):
        try:
            async with websockets.connect(uri) as ws:
                await asyncio.wait_for(ws.recv(), timeout=2)
                success += 1
                print(f"  [{i+1}] ✅ Connected and received message")
        except Exception as e:
            print(f"  [{i+1}] ❌ Failed: {e}")
        await asyncio.sleep(0.3)
    print(f"{'✅' if success == 5 else '❌'} {success}/5 successful reconnects")
    return success == 5

async def test_message_send():
    print("\nTesting message send...")
    uri = "ws://localhost:8000/ws/orb"
    try:
        async with websockets.connect(uri) as ws:
            # Try sending a message
            test_msg = json.dumps({"type": "ping", "timestamp": time.time()})
            await ws.send(test_msg)
            print(f"  Sent: {test_msg}")
            # Wait for any response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3)
                print(f"  ✅ Received response: {response[:100]}")
                return True
            except asyncio.TimeoutError:
                print("  ⚠️ No response to ping (may be expected)")
                return True
    except Exception as e:
        print(f"  ❌ Send test failed: {e}")
        return False

async def main():
    print("="*50)
    print("  WEBSOCKET DIAGNOSTIC")
    print("="*50)
    results = {
        "stability": await test_connection_stability(),
        "reconnect": await test_rapid_reconnect(),
        "send": await test_message_send(),
    }
    print("\n" + "="*50)
    print("  SUMMARY")
    print("="*50)
    for test, passed in results.items():
        print(f"  {'✅' if passed else '❌'} {test}")

if __name__ == "__main__":
    asyncio.run(main())
