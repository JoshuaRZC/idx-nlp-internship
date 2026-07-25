"""Small BM25 baseline for listing remarks."""

from __future__ import annotations

import re
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

        self.model = BM25Okapi(self.tokens)
        return self

    def search(self, query: str, top_k: int = 10):
        if self.model is None:
            raise ValueError("Build the BM25 index before searching.")

        scores = self.model.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for rank, index in enumerate(order, start=1):
            item = dict(self.metadata[index])
            item["rank"] = rank
            item["score"] = float(scores[index])
            results.append(item)
        return results
