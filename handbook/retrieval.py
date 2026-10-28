import json
import re
import numpy as np
from .config import EMBEDDING_DIM, EMBEDDING_MODEL, SCHEMA_VERSION
from .embeddings import Embedder
from .ingest import sha256


class Retriever:
    def __init__(self, data_dir, embedder=None):
        indexes = data_dir / "indexes"
        pointer = indexes / "CURRENT"
        if not pointer.exists():
            raise ValueError("Index missing. Run python -m handbook index, then restart the app.")
        version = pointer.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{16}", version):
            raise ValueError("Invalid index version pointer.")
        folder = indexes / version
        self.manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if (
            self.manifest["schema"] != SCHEMA_VERSION
            or self.manifest["embedding_model"] != EMBEDDING_MODEL
            or self.manifest["dimension"] != EMBEDDING_DIM
        ):
            raise ValueError("Incompatible index. Rebuild it with python -m handbook index.")
        for filename, key in [("chunks.json", "chunks_sha256"), ("vectors.npy", "vectors_sha256")]:
            if sha256(folder / filename) != self.manifest[key]:
                raise ValueError("Index integrity check failed. Rebuild the index.")
        self.chunks = json.loads((folder / "chunks.json").read_text(encoding="utf-8"))
        self.vectors = np.load(folder / "vectors.npy", allow_pickle=False)
        if self.vectors.shape != (len(self.chunks), EMBEDDING_DIM) or not np.isfinite(self.vectors).all():
            raise ValueError("Invalid vector matrix.")
        self.embedder = embedder or Embedder(data_dir / "cache")

    def search(self, question, top_k=5):
        query = self.embedder.query(question)
        scores = self.vectors @ query
        hits = []
        pages = {}
        # Up to two chunks per page prevents one long page occupying every slot.
        for index in np.argsort(-scores, kind="stable"):
            chunk = self.chunks[int(index)]
            if pages.get(chunk["page"], 0) >= 2:
                continue
            pages[chunk["page"]] = pages.get(chunk["page"], 0) + 1
            hits.append(
                {
                    **chunk,
                    "score": round(float(scores[index]), 4),
                    "url": self.manifest["source"]["url"] + f"#page={chunk['page']}",
                }
            )
            if len(hits) == top_k:
                break
        return hits
