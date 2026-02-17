"""Retrieval tuning parameters — persisted to sandbox_config.json."""

from dataclasses import dataclass, field, asdict
from pathlib import Path
import json

CONFIG_PATH = Path(__file__).parent.parent / "sandbox_config.json"


@dataclass
class RetrievalParams:
    decay: float = 0.5
    min_activation: float = 0.15
    max_hops: int = 2
    token_budget: int = 3000
    sim_threshold: float = 0.3
    fts5_limit: int = 20
    vector_limit: int = 20
    rrf_k: int = 60
    lock_in_node_weight: float = 0.4
    lock_in_access_weight: float = 0.3
    lock_in_edge_weight: float = 0.2
    lock_in_age_weight: float = 0.1
    cluster_sim_threshold: float = 0.82

    def save(self, path: Path = CONFIG_PATH):
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "RetrievalParams":
        if path.exists():
            data = json.loads(path.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()

    def to_dict(self) -> dict:
        return asdict(self)
