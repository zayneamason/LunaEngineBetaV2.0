"""Local embeddings via all-MiniLM-L6-v2 (384 dimensions). Lazy-loaded."""

import threading
import struct

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def vector_to_blob(vector: list[float]) -> bytes:
    return struct.pack(f'{len(vector)}f', *vector)


def blob_to_vector(blob: bytes) -> list[float]:
    return list(struct.unpack(f'{len(blob) // 4}f', blob))


class EmbeddingGenerator:
    def __init__(self):
        self._model = None
        self._load_lock = threading.Lock()
        self.dim = EMBEDDING_DIM

    def _load(self):
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME)

    def encode(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.dim
        self._load()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load()
        results = [[0.0] * self.dim for _ in range(len(texts))]
        non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
        if non_empty:
            indices, clean_texts = zip(*non_empty)
            embeddings = self._model.encode(list(clean_texts), normalize_embeddings=True)
            for idx, emb in zip(indices, embeddings):
                results[idx] = emb.tolist()
        return results


_instance = None
_lock = threading.Lock()


def get_embedder() -> EmbeddingGenerator:
    global _instance
    with _lock:
        if _instance is None:
            _instance = EmbeddingGenerator()
        return _instance
