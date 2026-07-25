"""Embedding-based listing search with FAISS."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def safe_model_name(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("_")


def json_safe(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def normalize_l2(embeddings: np.ndarray):
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return embeddings / norms


class SemanticSearcher:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model=None,
        local_files_only: bool = False,
        batch_size: int = 16,
    ):
        self.model_name = model_name
        self.model = model
        self.local_files_only = local_files_only
        self.batch_size = batch_size
        self.index = None
        self.metadata = []
        self.embeddings = None

    def build_index(self, records: Iterable[dict], text_field: str = "remarks_cleaned"):
        self.metadata = []
        texts = []

        for record in records:
            text = str(record.get(text_field) or record.get("remarks") or "").strip()
            if not text:
                continue
            item = dict(record)
            item["search_text"] = text
            self.metadata.append(item)
            texts.append(text)

        embeddings = normalize_l2(self._encode(texts))

        import faiss

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        self.embeddings = embeddings

        return self

    def search(self, query: str, top_k: int = 10):
        self._require_index()
        query_embedding = normalize_l2(self._encode([query]))

        scores, indices = self.index.search(query_embedding, top_k)
        return self._format_results(scores[0], indices[0])

    def search_candidates(self, query: str, candidate_ids: Iterable, top_k: int = 10):
        self._require_index()
        candidate_ids = {str(value) for value in candidate_ids}
        query_embedding = normalize_l2(self._encode([query]))

        positions = [
            i
            for i, item in enumerate(self.metadata)
            if str(item.get("listing_id") or item.get("L_ListingID")) in candidate_ids
        ]
        if not positions:
            return []

        candidate_embeddings = self.embeddings[positions]
        scores = candidate_embeddings @ query_embedding[0]
        order = np.argsort(-scores)[:top_k]

        results = []
        for rank, pos in enumerate(order, start=1):
            item = dict(self.metadata[positions[pos]])
            item["rank"] = rank
            item["score"] = float(scores[pos])
            results.append(item)
        return results

    def encode_queries(self, queries: Iterable[str]):
        return normalize_l2(self._encode(list(queries)))

    def save(self, output_dir: str | Path, name: str):
        self._require_index()
        import faiss

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(output_dir / f"{name}.faiss"))
        np.save(output_dir / f"{name}_embeddings.npy", self.embeddings)

        payload = {
            "model_name": self.model_name,
            "count": len(self.metadata),
            "metadata": [
                {key: json_safe(value) for key, value in item.items()}
                for item in self.metadata
            ],
        }
        with open(output_dir / f"{name}_metadata.json", "w") as f:
            json.dump(payload, f, indent=2)

    def load(self, input_dir: str | Path, name: str):
        input_dir = Path(input_dir)

        with open(input_dir / f"{name}_metadata.json") as f:
            payload = json.load(f)

        self.model_name = payload["model_name"]
        self.metadata = payload["metadata"]
        if self.model is None:
            self._load_model()

        import faiss

        self.index = faiss.read_index(str(input_dir / f"{name}.faiss"))
        self.embeddings = np.load(input_dir / f"{name}_embeddings.npy")
        return self

    def artifact_dir(self, base_dir: str | Path = "data/models/semantic"):
        return Path(base_dir) / safe_model_name(self.model_name)

    def _encode(self, texts: list[str]):
        if self.model is None:
            self._load_model()

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=len(texts) > 500,
        )
        return np.asarray(embeddings, dtype="float32")

    def _load_model(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            self.model_name,
            local_files_only=self.local_files_only,
        )

    def _format_results(self, scores, indices):
        results = []
        for rank, (score, index) in enumerate(zip(scores, indices), start=1):
            if index < 0:
                continue
            item = dict(self.metadata[int(index)])
            item["rank"] = rank
            item["score"] = float(score)
            results.append(item)
        return results

    def _require_index(self):
        if self.index is None or self.embeddings is None:
            raise ValueError("Build or load an index before searching.")
