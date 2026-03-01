import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { GRID_LAYER_CONFIG } from '../config/gridLayer';

const GridContext = createContext(null);

/**
 * Hook to access grid state. Returns null if outside GridProvider.
 */
export function useGrid() {
  return useContext(GridContext);
}

/**
 * Determine zone from normalized coordinates.
 */
function getZone(nx, ny, zones) {
  if (zones.knowledge && nx < (zones.knowledge.maxNx || 0.33)) return 'knowledge';
  if (zones.meta && nx > (zones.meta.minNx || 0.66)) return 'meta';
  if (zones.input && ny > (zones.input.minNy || 0.92)) return 'input';
  if (zones.nav && ny < (zones.nav.maxNy || 0.05)) return 'nav';
  return 'conversation';
}

/**
 * Determine child components at a normalized position.
 */
function getChildren(nx, ny) {
  if (nx > 0.44 && nx < 0.56 && ny > 0.38 && ny < 0.62) return ['LunaOrb'];
  if (nx < 0.31 && ny > 0.12 && ny < 0.88) return ['KnowledgeSpine'];
  if (nx > 0.68 && ny > 0.08 && ny < 0.92) return ['MetaPanel'];
  if (ny > 0.92) return ['InputBar'];
  if (ny < 0.05) return ['NavBar'];
  return [];
}

/**
 * GridProvider — spatial index for the viewport.
 *
 * Provides a hierarchical grid of anchor points that components can
 * snap to. The grid subdivides: L0 (10×6) → L1 (20×12) → L2 (40×24) → L3 (80×48).
 */
export function GridProvider({ children, containerRef }) {
  const [level, setLevel] = useState(0);
  const [debugMode, setDebugMode] = useState(false);
  const gridRef = useRef({ points: [], cols: 0, rows: 0, cellW: 0, cellH: 0 });
  const logsRef = useRef([]);
  const [logVersion, setLogVersion] = useState(0);

  const { baseCols, baseRows, maxLevel, zones } = GRID_LAYER_CONFIG;

  const addLog = useCallback((msg) => {
    logsRef.current.unshift(msg);
    if (logsRef.current.length > 30) logsRef.current.pop();
    setLogVersion(v => v + 1);
  }, []);

  const buildGrid = useCallback((w, h, lvl) => {
    const m = Math.pow(2, lvl);
    const cols = baseCols * m;
    const rows = baseRows * m;
    const cellW = w / cols;
    const cellH = h / rows;
    const points = [];

    for (let r = 0; r <= rows; r++) {
      for (let c = 0; c <= cols; c++) {
        const x = c * cellW;
        const y = r * cellH;
        const nx = c / cols;
        const ny = r / rows;
        points.push({
          id: `${c}.${r}`,
          c, r, x, y, nx, ny,
          zone: getZone(nx, ny, zones),
          children: getChildren(nx, ny),
        });
      }
    }

    gridRef.current = { points, cols, rows, cellW, cellH };
    return gridRef.current;
  }, [baseCols, baseRows, zones]);

  // Rebuild grid on level change or container resize
  useEffect(() => {
    const container = containerRef?.current;
    if (!container) return;

    const rebuild = () => {
      const w = container.offsetWidth;
      const h = container.offsetHeight;
      if (w > 0 && h > 0) {
        buildGrid(w, h, level);
      }
    };

    rebuild();

    const observer = new ResizeObserver(rebuild);
    observer.observe(container);
    return () => observer.disconnect();
  }, [level, containerRef, buildGrid]);

  const find = useCallback((px, py) => {
    const { points } = gridRef.current;
    let best = null;
    let bestDist = Infinity;
    for (const p of points) {
      const d = (p.x - px) ** 2 + (p.y - py) ** 2;
      if (d < bestDist) {
        bestDist = d;
        best = p;
      }
    }
    return best ? { ...best, dist: Math.sqrt(bestDist) } : null;
  }, []);

  const queryZone = useCallback((zoneName) => {
    return gridRef.current.points.filter(p => p.zone === zoneName);
  }, []);

  const queryRadius = useCallback((px, py, radius) => {
    const r2 = radius * radius;
    return gridRef.current.points.filter(p =>
      (p.x - px) ** 2 + (p.y - py) ** 2 <= r2
    );
  }, []);

  const subdivide = useCallback(() => {
    setLevel(l => {
      const next = Math.min(l + 1, maxLevel);
      if (next !== l) addLog(`subdiv L${next}`);
      return next;
    });
  }, [maxLevel, addLog]);

  const coarsen = useCallback(() => {
    setLevel(l => {
      const next = Math.max(l - 1, 0);
      if (next !== l) addLog(`coarsen L${next}`);
      return next;
    });
  }, [addLog]);

  const resetGrid = useCallback(() => {
    setLevel(0);
    addLog('reset L0');
  }, [addLog]);

  const toggleDebug = useCallback(() => {
    setDebugMode(d => !d);
  }, []);

  const value = {
    grid: gridRef.current,
    level,
    debugMode,
    find,
    queryZone,
    queryRadius,
    subdivide,
    coarsen,
    reset: resetGrid,
    toggleDebug,
    logs: logsRef.current,
    logVersion,
    addLog,
  };

  return (
    <GridContext.Provider value={value}>
      {children}
    </GridContext.Provider>
  );
}

export default GridContext;
