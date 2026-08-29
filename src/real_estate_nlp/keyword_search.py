"""Small BM25 baseline for listing remarks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from rank_bm25 import BM25Okapi


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str):
    return TOKEN_PATTERN.findall(str(text).lower())


class BM25Searcher:
    def __init__(self):
        self.model = None
        self.metadata = []
        self.tokens = []
        self.positions_by_listing_id = {}

    def build(self, records: Iterable[dict], text_field: str = "remarks_cleaned"):
        self.metadata = []
        self.tokens = []

        for record in records:
            text = str(record.get(text_field) or record.get("remarks") or "").strip()
            if not text:
                continue
            item = dict(record)
            item["search_text"] = text
            self.metadata.append(item)
            self.tokens.append(tokenize(text))

        if not self.tokens:
            raise ValueError("Build an index from at least one non-empty listing text.")

        self.model = BM25Okapi(self.tokens)
        self._build_position_map()
        return self

    def search(self, query: str, top_k: int = 10):
        if self.model is None:
            raise ValueError("Build the BM25 index before searching.")

        scores = self.model.get_scores(tokenize(query))
        order = self._rank_positions(scores, range(len(scores)), top_k)

        results = []
        for rank, index in enumerate(order, start=1):
            item = dict(self.metadata[index])
            item["rank"] = rank
            item["score"] = float(scores[index])
            results.append(item)
        return results

    def search_candidates(self, query: str, candidate_ids: Iterable, top_k: int = 10):
        if self.model is None:
            raise ValueError("Build the BM25 index before searching.")

        positions = [
            position
            for listing_id in {str(value) for value in candidate_ids}
            for position in self.positions_by_listing_id.get(listing_id, [])
        ]
        if not positions:
            return []

        scores = self.model.get_batch_scores(tokenize(query), positions)
        order = self._rank_positions(scores, range(len(positions)), top_k, positions)

        results = []
        for rank, score_index in enumerate(order, start=1):
            item = dict(self.metadata[positions[score_index]])
            item["rank"] = rank
            item["score"] = float(scores[score_index])
            results.append(item)
        return results

    def save(self, output_dir: str | Path, name: str = "bm25"):
        if self.model is None:
            raise ValueError("Build an index before saving it.")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {"metadata": self.metadata, "tokens": self.tokens}
        with (output_dir / f"{name}.json").open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)

    def load(self, input_dir: str | Path, name: str = "bm25"):
        with (Path(input_dir) / f"{name}.json").open(encoding="utf-8") as handle:
            payload = json.load(handle)

        self.metadata = payload["metadata"]
        self.tokens = payload["tokens"]
        self.model = BM25Okapi(self.tokens)
        self._build_position_map()
        return self

    def _rank_positions(self, scores, positions, top_k, metadata_positions=None):
        metadata_positions = metadata_positions or list(positions)
        return sorted(
            positions,
            key=lambda index: (
                -float(scores[index]),
                self._listing_id(self.metadata[metadata_positions[index]]),
            ),
        )[:top_k]

    def _build_position_map(self):
        positions = {}
        for position, item in enumerate(self.metadata):
            positions.setdefault(self._listing_id(item), []).append(position)
        self.positions_by_listing_id = positions

    @staticmethod
    def _listing_id(item):
        return str(item.get("listing_id") or item.get("L_ListingID") or "")
