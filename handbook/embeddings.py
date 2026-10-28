from threading import Lock
import numpy as np
from .config import EMBEDDING_MODEL


class Embedder:
    def __init__(self, cache_dir):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=str(cache_dir), threads=2)
        self.lock = Lock()

    def documents(self, texts):
        with self.lock:
            return normalize(np.array(list(self.model.passage_embed(texts, batch_size=16)), dtype=np.float32))

    def query(self, question):
        with self.lock:
            return normalize(np.array(list(self.model.query_embed(question)), dtype=np.float32))[0]


def normalize(vectors):
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)
