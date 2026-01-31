# Agent A3: ClusteringEngine Agent

**Task:** Implement automatic memory clustering  
**Dependencies:** A1 (Schema), A2 (ClusterManager)  
**Outputs:** `src/luna/memory/clustering_engine.py`, `src/luna/services/clustering_service.py`  
**Estimated Time:** 45 minutes

---

## Objective

Create the engine that automatically groups related memories into clusters using keyword-based semantic similarity.

---

## Implementation

Create `src/luna/memory/clustering_engine.py`:

```python
"""
ClusteringEngine - Automatic semantic grouping of memories.

MVP Strategy: Keyword-based clustering
- Uses FTS5 to find nodes with common keywords
- Groups nodes that share significant keyword overlap
- Fast, interpretable, no complex algorithms

Future: Add Louvain graph-based clustering
"""

import sqlite3
from typing import List, Dict, Set
from collections import defaultdict, Counter
from datetime import datetime
import numpy as np

from luna.memory.cluster_manager import ClusterManager


class ClusteringEngine:
    """Automatically groups related memories into clusters."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.cluster_mgr = ClusterManager(db_path)
        
        # Clustering parameters
        self.similarity_threshold = 0.82
        self.min_cluster_size = 3
        self.max_cluster_size = 50
        self.min_keyword_overlap = 0.4
        self.max_generic_frequency = 100  # Skip keywords in >100 nodes
        
        # Stopwords
        self.stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'as', 'by', 'is', 'was', 'are', 'were', 'be', 'been',
            'this', 'that', 'with', 'from', 'it', 'i', 'you', 'we', 'they',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'not', 'no', 'yes',
            'luna', 'user', 'assistant', 'message', 'response', 'question'
        }
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _extract_keywords(self, text: str, top_n: int = 15) -> List[str]:
        """Extract top keywords from text."""
        if not text:
            return []
        
        words = text.lower().split()
        word_counts = Counter()
        
        for word in words:
            # Clean punctuation
            word = ''.join(c for c in word if c.isalnum())
            if word and len(word) > 3 and word not in self.stopwords:
                word_counts[word] += 1
        
        return [word for word, _ in word_counts.most_common(top_n)]
    
    def cluster_by_keywords(self) -> List[Dict]:
        """
        Group memories by keyword co-occurrence.
        
        Returns:
            List of cluster dicts: {keyword, nodes}
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get all nodes with content
        cursor.execute("""
            SELECT id, content FROM memory_nodes 
            WHERE content IS NOT NULL AND content != ''
        """)
        
        nodes = cursor.fetchall()
        print(f"Analyzing {len(nodes)} nodes for clustering...")
        
        # Extract keywords per node
        node_keywords = {}
        for row in nodes:
            node_id = row['id']
            content = row['content']
            keywords = self._extract_keywords(content)
            if keywords:
                node_keywords[node_id] = set(keywords)
        
        # Build inverted index (keyword -> nodes)
        keyword_index = defaultdict(set)
        for node_id, keywords in node_keywords.items():
            for kw in keywords:
                keyword_index[kw].add(node_id)
        
        # Count keyword frequencies
        keyword_counts = Counter()
        for keywords in node_keywords.values():
            keyword_counts.update(keywords)
        
        conn.close()
        
        # Find clusters
        clusters = []
        processed_nodes = set()
        
        # Process keywords from most to least common (but not too common)
        for keyword, count in keyword_counts.most_common():
            # Skip too generic
            if count > self.max_generic_frequency:
                continue
            
            # Get candidate nodes
            candidates = keyword_index[keyword] - processed_nodes
            if len(candidates) < self.min_cluster_size:
                continue
            
            # Find nodes with high keyword overlap
            cluster_nodes = []
            for node_id in candidates:
                if node_id in processed_nodes:
                    continue
                
                node_kw = node_keywords[node_id]
                
                # Check overlap with other candidates
                good_overlaps = 0
                for other_id in candidates:
                    if other_id == node_id or other_id in processed_nodes:
                        continue
                    
                    other_kw = node_keywords[other_id]
                    overlap = len(node_kw & other_kw) / len(node_kw | other_kw)
                    
                    if overlap >= self.min_keyword_overlap:
                        good_overlaps += 1
                
                if good_overlaps >= self.min_cluster_size - 1:
                    cluster_nodes.append(node_id)
            
            # Create cluster if enough nodes
            if len(cluster_nodes) >= self.min_cluster_size:
                cluster_nodes = cluster_nodes[:self.max_cluster_size]
                clusters.append({
                    'keyword': keyword,
                    'nodes': cluster_nodes
                })
                processed_nodes.update(cluster_nodes)
        
        print(f"Found {len(clusters)} potential clusters")
        print(f"Clustered {len(processed_nodes)}/{len(node_keywords)} nodes")
        
        return clusters
    
    def _calculate_centroid(self, node_ids: List[str]) -> bytes:
        """Calculate centroid embedding from member embeddings."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        embeddings = []
        for node_id in node_ids:
            cursor.execute("""
                SELECT embedding FROM memory_nodes WHERE id = ?
            """, (node_id,))
            row = cursor.fetchone()
            if row and row['embedding']:
                try:
                    emb = np.frombuffer(row['embedding'], dtype=np.float32)
                    embeddings.append(emb)
                except:
                    pass
        
        conn.close()
        
        if not embeddings:
            return b''
        
        centroid = np.mean(embeddings, axis=0).astype(np.float32)
        return centroid.tobytes()
    
    def create_clusters_from_analysis(self, clusters: List[Dict]) -> List[str]:
        """Create cluster records in database."""
        created_ids = []
        
        for cluster_data in clusters:
            keyword = cluster_data['keyword']
            nodes = cluster_data['nodes']
            
            # Generate name and summary
            name = f"Cluster: {keyword.title()}"
            summary = f"Semantic grouping around '{keyword}' with {len(nodes)} related memories"
            
            # Calculate centroid
            centroid = self._calculate_centroid(nodes)
            
            # Create cluster
            cluster_id = self.cluster_mgr.create_cluster(
                name=name,
                summary=summary,
                centroid_embedding=centroid,
                initial_lock_in=0.15  # Start in drifting state
            )
            
            # Add members
            for node_id in nodes:
                self.cluster_mgr.add_member(
                    cluster_id=cluster_id,
                    node_id=node_id,
                    membership_strength=0.8
                )
            
            created_ids.append(cluster_id)
            print(f"  Created: {name} ({len(nodes)} members)")
        
        return created_ids
    
    def run_clustering(self) -> Dict:
        """Execute full clustering pipeline."""
        print("\n" + "="*50)
        print("CLUSTERING ENGINE - Starting")
        print("="*50 + "\n")
        
        # Find clusters
        clusters = self.cluster_by_keywords()
        
        if not clusters:
            print("No clusters found.")
            return {'clusters_created': 0, 'cluster_ids': []}
        
        # Create records
        print(f"\nCreating {len(clusters)} clusters...")
        created_ids = self.create_clusters_from_analysis(clusters)
        
        print(f"\n✅ Clustering complete: {len(created_ids)} clusters created")
        
        return {
            'clusters_created': len(created_ids),
            'cluster_ids': created_ids,
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    from pathlib import Path
    
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "luna_engine.db"
    engine = ClusteringEngine(str(db_path))
    result = engine.run_clustering()
    print(f"\nResult: {result}")
```

---

## Background Service

Create `src/luna/services/clustering_service.py`:

```python
"""
Background service that runs clustering periodically.
"""

import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


class ClusteringService:
    """Background service for periodic clustering."""
    
    def __init__(self, db_path: str, interval_hours: int = 1):
        self.db_path = db_path
        self.interval_seconds = interval_hours * 3600
        self.running = False
        
        # Lazy import to avoid circular deps
        self.engine = None
    
    def _get_engine(self):
        if self.engine is None:
            from luna.memory.clustering_engine import ClusteringEngine
            self.engine = ClusteringEngine(self.db_path)
        return self.engine
    
    def start(self):
        """Start the background service."""
        self.running = True
        logger.info(f"Clustering service starting (interval: {self.interval_seconds/3600}h)")
        
        while self.running:
            try:
                logger.info("Running clustering job...")
                engine = self._get_engine()
                result = engine.run_clustering()
                logger.info(f"Clustering complete: {result['clusters_created']} clusters")
                
                # Wait for next run
                time.sleep(self.interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Service stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Clustering error: {e}", exc_info=True)
                time.sleep(60)  # Retry in 1 minute
    
    def stop(self):
        """Stop the service."""
        self.running = False
        logger.info("Clustering service stopped")
    
    def run_once(self):
        """Run clustering once (for testing)."""
        engine = self._get_engine()
        return engine.run_clustering()


if __name__ == "__main__":
    import sys
    
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "luna_engine.db"
    service = ClusteringService(str(db_path), interval_hours=1)
    
    if "--once" in sys.argv:
        # Single run for testing
        result = service.run_once()
        print(f"Result: {result}")
    else:
        # Continuous service
        service.start()
```

---

## Validation

```bash
# Single run test
python -m luna.services.clustering_service --once

# Background service (Ctrl+C to stop)
python -m luna.services.clustering_service
```

---

## Success Criteria

- [ ] ClusteringEngine creates coherent clusters
- [ ] Keyword extraction works (no stopwords)
- [ ] Cluster names are interpretable
- [ ] Member counts are 3-50
- [ ] Background service runs without errors
- [ ] Centroid embeddings calculated
