#!/usr/bin/env python3
"""Quick test to check entity context initialization."""
import asyncio
import sys
sys.path.insert(0, 'src')

async def test():
    from luna.actors.director import DirectorActor, ENTITY_CONTEXT_AVAILABLE
    
    print(f"ENTITY_CONTEXT_AVAILABLE: {ENTITY_CONTEXT_AVAILABLE}")
    
    d = DirectorActor(name="test_director", engine=None)
    print(f"Director created, _entity_context: {d._entity_context}")
    
    # Try to ensure entity context (will fail without engine)
    result = await d._ensure_entity_context()
    print(f"_ensure_entity_context() returned: {result}")
    print(f"After ensure, _entity_context: {d._entity_context}")
    
    # Now let's simulate with a real engine
    print("\n--- Testing with full engine ---")
    from luna.engine import LunaEngine
    
    engine = LunaEngine()
    await engine.start()
    
    # Get the director from the engine
    director = engine.get_actor("director")
    if director:
        print(f"Got director from engine")
        print(f"director._entity_context: {director._entity_context}")
        
        # Try ensure again
        result = await director._ensure_entity_context()
        print(f"_ensure_entity_context() with engine: {result}")
        print(f"After ensure, _entity_context: {director._entity_context}")
    else:
        print("No director actor found in engine")
    
    await engine.stop()

if __name__ == "__main__":
    asyncio.run(test())
