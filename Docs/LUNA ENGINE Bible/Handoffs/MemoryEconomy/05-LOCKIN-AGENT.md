# Agent A5: LockIn Agent

**Task:** Implement lock-in dynamics (calculation, decay, state transitions)  
**Dependencies:** A1 (Schema), A2 (ClusterManager)  
**Outputs:** `src/luna/memory/lock_in.py`, `src/luna/services/lockin_service.py`  
**Estimated Time:** 45 minutes

---

## Objective

Implement the lock-in calculation system with:
- Logarithmic access boost (1→5 matters more than 100→105)
- State-dependent decay rates
- Background update service

---

## Lock-In Formula

From Gemini's corrections:

```
lock_in = (
    w_node * avg_member_lock_in +
    w_access * log_access_factor +
    w_edge * avg_edge_strength +
    w_age * age_factor
) * decay_factor

Where:
- w_node = 0.40
- w_access = 0.30
- w_edge = 0.20
- w_age = 0.10

- log_access_factor = min(log(access_count + 1) / log(11), 1.0)
- decay_factor = exp(-λ * seconds_since_access)
- λ varies by state (crystallized decays slowest)
```

---

## Implementation

Create `src/luna/memory/lock_in.py`:

```python
"""
Lock-in dynamics for Memory Economy.

Handles:
- Lock-in calculation with Gemini corrections
- State transitions based on thresholds
- Decay over time (state-dependent rates)
"""

import math
import sqlite3
from datetime import datetime
from typing import Dict, Optional

from luna.memory.cluster_manager import ClusterManager, get_state_from_lock_in


# State thresholds (from architecture)
STATE_THRESHOLDS = {
    'drifting': 0.20,
    'fluid': 0.70,
    'settled': 0.85,
    # crystallized = above 0.85
}

# Lock-in component weights
WEIGHTS = {
    'node': 0.40,
    'access': 0.30,
    'edge': 0.20,
    'age': 0.10,
}

# Decay rates by state (per second)
# Lower = slower decay = more persistent
DECAY_LAMBDAS = {
    'crystallized': 0.00001,  # Negligible decay
    'settled': 0.0001,
    'fluid': 0.001,
    'drifting': 0.01,  # Rapid decay
}


class LockInCalculator:
    """Calculates and updates cluster lock-in values."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.cluster_mgr = ClusterManager(db_path)
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def calculate_cluster_lock_in(self, cluster_id: str) -> float:
        """
        Calculate lock-in for a cluster using Gemini's corrected formula.
        
        Components:
        1. Average node lock-in (weighted by membership)
        2. Logarithmic access boost
        3. Edge strength to other clusters
        4. Age factor (newer = higher)
        
        Then apply decay based on time since last access.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get cluster data
        cursor.execute("""
            SELECT access_count, created_at, last_accessed_at, state
            FROM clusters WHERE cluster_id = ?
        """, (cluster_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 0.0
        
        access_count = row['access_count'] or 0
        created_at = row['created_at']
        last_accessed_at = row['last_accessed_at']
        current_state = row['state']
        
        # ==================== COMPONENT 1: Node Lock-In ====================
        cursor.execute("""
            SELECT n.lock_in_coefficient, cm.membership_strength
            FROM cluster_members cm
            JOIN memory_nodes n ON cm.node_id = n.id
            WHERE cm.cluster_id = ?
        """, (cluster_id,))
        
        members = cursor.fetchall()
        
        if not members:
            conn.close()
            return 0.0
        
        # Weighted average of member lock-ins
        total_weight = sum(m['membership_strength'] for m in members)
        if total_weight > 0:
            weighted_node_strength = sum(
                (m['lock_in_coefficient'] or 0.5) * m['membership_strength']
                for m in members
            ) / total_weight
        else:
            weighted_node_strength = 0.5
        
        # ==================== COMPONENT 2: Access Factor ====================
        # Logarithmic: log(access_count + 1) / log(11)
        # Caps at 1.0 when access_count = 10
        # Emphasizes early accesses (1→5) over late (100→105)
        access_factor = min(math.log(access_count + 1) / math.log(11), 1.0)
        
        # ==================== COMPONENT 3: Edge Strength ====================
        cursor.execute("""
            SELECT AVG(strength * lock_in) as avg_edge
            FROM cluster_edges
            WHERE from_cluster = ? OR to_cluster = ?
        """, (cluster_id, cluster_id))
        
        edge_row = cursor.fetchone()
        edge_factor = edge_row['avg_edge'] if edge_row['avg_edge'] else 0.5
        
        # ==================== COMPONENT 4: Age Factor ====================
        # Newer clusters get a slight boost
        try:
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age_days = (datetime.now() - created_dt.replace(tzinfo=None)).days
            age_factor = 1.0 / (1.0 + age_days / 30.0)  # Decays over 30 days
        except:
            age_factor = 0.5
        
        conn.close()
        
        # ==================== CALCULATE BASE LOCK-IN ====================
        lock_in = (
            WEIGHTS['node'] * weighted_node_strength +
            WEIGHTS['access'] * access_factor +
            WEIGHTS['edge'] * edge_factor +
            WEIGHTS['age'] * age_factor
        )
        
        # ==================== APPLY DECAY ====================
        if last_accessed_at:
            try:
                last_access_dt = datetime.fromisoformat(
                    last_accessed_at.replace('Z', '+00:00')
                )
                offline_seconds = (
                    datetime.now() - last_access_dt.replace(tzinfo=None)
                ).total_seconds()
                
                # Get decay rate for current state
                lambda_decay = DECAY_LAMBDAS.get(current_state, 0.001)
                
                # Exponential decay: lock_in *= exp(-λ * time)
                decay_factor = math.exp(-lambda_decay * offline_seconds)
                lock_in *= decay_factor
                
            except Exception:
                pass  # Skip decay if timestamp parsing fails
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, lock_in))
    
    def update_cluster(self, cluster_id: str) -> Dict:
        """
        Recalculate and update lock-in for a cluster.
        
        Returns:
            Dict with old and new values
        """
        # Get current state
        old_cluster = self.cluster_mgr.get_cluster(cluster_id)
        if not old_cluster:
            return {'error': 'Cluster not found'}
        
        old_lock_in = old_cluster.lock_in
        old_state = old_cluster.state
        
        # Calculate new lock-in
        new_lock_in = self.calculate_cluster_lock_in(cluster_id)
        new_state = get_state_from_lock_in(new_lock_in)
        
        # Update
        self.cluster_mgr.update_lock_in(cluster_id, new_lock_in)
        
        return {
            'cluster_id': cluster_id,
            'old_lock_in': old_lock_in,
            'new_lock_in': new_lock_in,
            'old_state': old_state,
            'new_state': new_state,
            'state_changed': old_state != new_state
        }
    
    def update_all_clusters(self) -> Dict:
        """Update lock-in for all clusters."""
        clusters = self.cluster_mgr.list_clusters(limit=10000)
        
        results = {
            'total': len(clusters),
            'updated': 0,
            'state_changes': [],
        }
        
        for cluster in clusters:
            update = self.update_cluster(cluster.cluster_id)
            results['updated'] += 1
            
            if update.get('state_changed'):
                results['state_changes'].append({
                    'cluster_id': cluster.cluster_id,
                    'name': cluster.name,
                    'from': update['old_state'],
                    'to': update['new_state']
                })
        
        return results


if __name__ == "__main__":
    from pathlib import Path
    
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "luna_engine.db"
    calc = LockInCalculator(str(db_path))
    
    print("Updating all clusters...")
    result = calc.update_all_clusters()
    
    print(f"\nUpdated: {result['updated']}/{result['total']} clusters")
    
    if result['state_changes']:
        print("\nState changes:")
        for change in result['state_changes']:
            print(f"  {change['name']}: {change['from']} → {change['to']}")
```

---

## Background Service

Create `src/luna/services/lockin_service.py`:

```python
"""
Background service that updates cluster lock-in values periodically.
"""

import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


class LockInService:
    """Background service for periodic lock-in updates."""
    
    def __init__(self, db_path: str, interval_minutes: int = 5):
        self.db_path = db_path
        self.interval_seconds = interval_minutes * 60
        self.running = False
        self.calculator = None
    
    def _get_calculator(self):
        if self.calculator is None:
            from luna.memory.lock_in import LockInCalculator
            self.calculator = LockInCalculator(self.db_path)
        return self.calculator
    
    def start(self):
        """Start the lock-in update service."""
        self.running = True
        logger.info(f"Lock-in service starting (interval: {self.interval_seconds/60}min)")
        
        while self.running:
            try:
                logger.info("Updating lock-in values...")
                calc = self._get_calculator()
                result = calc.update_all_clusters()
                
                logger.info(f"Updated {result['updated']} clusters")
                if result['state_changes']:
                    for change in result['state_changes']:
                        logger.info(f"  State change: {change['name']} {change['from']}→{change['to']}")
                
                time.sleep(self.interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Service stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Lock-in update error: {e}", exc_info=True)
                time.sleep(60)
    
    def stop(self):
        """Stop the service."""
        self.running = False
        logger.info("Lock-in service stopped")
    
    def run_once(self):
        """Run update once (for testing)."""
        calc = self._get_calculator()
        return calc.update_all_clusters()


if __name__ == "__main__":
    import sys
    
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "luna_engine.db"
    service = LockInService(str(db_path), interval_minutes=5)
    
    if "--once" in sys.argv:
        result = service.run_once()
        print(f"Result: {result}")
    else:
        service.start()
```

---

## Validation

```bash
# Single run
python -m luna.services.lockin_service --once

# Background service
python -m luna.services.lockin_service
```

---

## Success Criteria

- [ ] Lock-in calculation uses all 4 components
- [ ] Logarithmic access boost verified (1→5 > 100→105)
- [ ] Decay rates vary by state
- [ ] State transitions happen at correct thresholds
- [ ] Background service runs without errors
- [ ] Crystallized clusters resist decay
