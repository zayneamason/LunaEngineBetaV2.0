import { useState, useEffect, useRef } from 'react';

/**
 * useExtractions — fetches Scribe extraction data from the shared turn cache.
 *
 * Returns the latest extractions (facts, decisions, actions, etc.) and the
 * entities mentioned in those extractions. This data powers the T-shape
 * knowledge panels (KnowledgeBar + TPanels).
 *
 * Polls /api/cache/shared-turn every 3 seconds while connected.
 */
export function useExtractions(isConnected) {
  const [extractions, setExtractions] = useState([]);
  const [entities, setEntities] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [turnId, setTurnId] = useState(null);
  const lastTurnRef = useRef(null);

  useEffect(() => {
    if (!isConnected) return;

    const fetchCache = async () => {
      try {
        const res = await fetch('/api/cache/shared-turn');
        if (!res.ok) return;

        const data = await res.json();
        const newTurnId = data.turn_id || null;

        // Only update if the turn changed
        if (newTurnId && newTurnId === lastTurnRef.current) return;
        lastTurnRef.current = newTurnId;
        setTurnId(newTurnId);

        // Gather all extractions from scribed data
        const scribed = data.scribed || {};
        const allExtractions = [];

        const categories = [
          { key: 'facts', type: 'FACT' },
          { key: 'decisions', type: 'DECISION' },
          { key: 'actions', type: 'ACTION' },
          { key: 'problems', type: 'PROBLEM' },
          { key: 'observations', type: 'OBSERVATION' },
        ];

        for (const { key, type } of categories) {
          const items = scribed[key] || [];
          for (const item of items) {
            allExtractions.push({
              type: item.type || type,
              content: item.content || '',
              confidence: item.confidence ?? null,
              lock_in: item.lock_in ?? null,
              entities: item.entities || [],
              provenance: item.provenance || null,
            });
          }
        }

        setExtractions(allExtractions);

        // Collect unique entities mentioned across all extractions
        const entityMap = new Map();
        for (const ext of allExtractions) {
          for (const ent of ext.entities || []) {
            const name = typeof ent === 'string' ? ent : ent.name;
            if (name && !entityMap.has(name)) {
              entityMap.set(name, typeof ent === 'object' ? ent : { name: ent, type: 'concept' });
            }
          }
        }
        setEntities(Array.from(entityMap.values()));

        // Try to fetch graph neighbors for the entities
        if (entityMap.size > 0) {
          try {
            const names = Array.from(entityMap.keys()).slice(0, 5);
            const edgeRes = await fetch('/api/graph/neighbors', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ entities: names, limit: 10 }),
            });
            if (edgeRes.ok) {
              const edgeData = await edgeRes.json();
              setRelationships(edgeData.edges || edgeData.relationships || []);
            }
          } catch {
            // Graph neighbors endpoint may not exist yet — that's fine
          }
        } else {
          setRelationships([]);
        }
      } catch {
        // Silent fail — extraction data is optional
      }
    };

    fetchCache();
    const id = setInterval(fetchCache, 3000);
    return () => clearInterval(id);
  }, [isConnected]);

  return { extractions, entities, relationships, turnId };
}
