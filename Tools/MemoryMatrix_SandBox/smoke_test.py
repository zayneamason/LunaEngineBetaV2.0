"""Smoke test for Observatory Sandbox — run from MemoryMatrix_SandBox directory."""
import asyncio
import os
import sys
import time

async def smoke_test():
    from mcp_server.event_bus import EventBus
    from mcp_server.sandbox_matrix import SandboxMatrix
    from mcp_server.search import search_fts5, search_vector, search_hybrid
    from mcp_server.activation import spreading_activation
    from mcp_server.lock_in import recompute_all_lock_ins
    from mcp_server.clusters import assemble_constellation
    from mcp_server.config import RetrievalParams
    from pathlib import Path

    test_db = '/tmp/observatory_full_smoke.db'
    if os.path.exists(test_db):
        os.remove(test_db)

    bus = EventBus()
    matrix = SandboxMatrix(bus, db_path=Path(test_db))
    await matrix.initialize()
    print('1. Matrix initialized')

    t0 = time.time()
    await matrix.seed('small_graph')
    stats = await matrix.stats()
    print(f'2. Seeded small_graph in {(time.time()-t0)*1000:.0f}ms: '
          f'{stats["node_count"]} nodes, {stats["edge_count"]} edges, {stats["cluster_count"]} clusters')
    print(f'   Types: {stats["type_distribution"]}')
    print(f'   Lock-in dist: {stats["lock_in_distribution"]}')

    params = RetrievalParams.load()

    t0 = time.time()
    fts = await search_fts5(matrix, 'Luna engine', params)
    print(f'3. FTS5 search: {len(fts)} results in {(time.time()-t0)*1000:.0f}ms')
    for r in fts[:3]:
        print(f'   [{r["score"]:.3f}] {r["node"]["id"]}: {r["node"]["content"][:60]}')

    t0 = time.time()
    vec = await search_vector(matrix, 'robot body servo', params)
    print(f'4. Vector search: {len(vec)} results in {(time.time()-t0)*1000:.0f}ms')
    for r in vec[:3]:
        print(f'   [{r["score"]:.4f}] {r["node"]["id"]}: {r["node"]["content"][:60]}')

    t0 = time.time()
    hyb = await search_hybrid(matrix, 'memory sovereignty', params)
    print(f'5. Hybrid search: {len(hyb)} results in {(time.time()-t0)*1000:.0f}ms')
    for r in hyb[:3]:
        print(f'   [{r["score"]:.6f}] {r["node"]["id"]}')

    seed_ids = [r['node']['id'] for r in hyb[:5]]
    t0 = time.time()
    activated = await spreading_activation(matrix, seed_ids, params)
    print(f'6. Activation: {len(activated)} nodes in {(time.time()-t0)*1000:.0f}ms')
    for a in activated[:5]:
        print(f'   [{a["activation"]:.3f}] hop={a["hop"]} {a["node_id"]}')

    t0 = time.time()
    li = await recompute_all_lock_ins(matrix, params)
    print(f'7. Lock-in recompute: {li["nodes_updated"]} updated, '
          f'{li["state_transitions"]} transitions in {(time.time()-t0)*1000:.0f}ms')

    t0 = time.time()
    const = await assemble_constellation(matrix, activated, params)
    print(f'8. Constellation: {len(const["nodes"])} selected, '
          f'{const["total_tokens"]} tokens ({const["budget_used"]*100:.1f}% budget), '
          f'{const["dropped"]} dropped')

    event_count = len(bus.recent(n=2000))
    print(f'9. Events recorded: {event_count}')

    await matrix.close()
    os.remove(test_db)
    print()
    print('ALL SMOKE TESTS PASSED')

if __name__ == '__main__':
    asyncio.run(smoke_test())
