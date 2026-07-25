import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.keyword_search import BM25Searcher, tokenize
from src.real_estate_nlp.semantic_search import SemanticSearcher, safe_model_name


class FakeEmbeddingModel:
    def encode(self, texts, batch_size=16, show_progress_bar=False):
        return np.array([self._embed(text) for text in texts], dtype="float32")

    def _embed(self, text):
        text = text.lower()
        vector = np.zeros(4, dtype="float32")
        if "pool" in text:
            vector[0] += 1
        if "ocean" in text or "view" in text:
            vector[1] += 1
        if "garage" in text:
            vector[2] += 1
        if not vector.any():
            vector[3] = 1
        return vector


def sample_records():
    return [
        {
            "listing_id": "A",
            "city": "Irvine",
            "remarks_cleaned": "private pool and outdoor entertaining space",
        },
        {
            "listing_id": "B",
            "city": "Malibu",
            "remarks_cleaned": "ocean view condo near the beach",
        },
        {
            "listing_id": "C",
            "city": "Pasadena",
            "remarks_cleaned": "detached garage with storage",
        },
    ]


def test_safe_model_name_removes_path_separator():
    assert (
        safe_model_name("sentence-transformers/all-MiniLM-L6-v2")
        == "sentence-transformers_all-MiniLM-L6-v2"
    )


def test_semantic_search_returns_ranked_results():
    searcher = SemanticSearcher(model=FakeEmbeddingModel()).build_index(sample_records())

    results = searcher.search("home with pool", top_k=2)

    assert len(results) == 2
    assert results[0]["listing_id"] == "A"
    assert isinstance(results[0]["score"], float)
    assert results[0]["rank"] == 1


def test_semantic_search_can_rank_candidate_ids_only():
    searcher = SemanticSearcher(model=FakeEmbeddingModel()).build_index(sample_records())

    results = searcher.search_candidates("ocean view", candidate_ids=["A", "B"], top_k=2)

    assert [item["listing_id"] for item in results] == ["B", "A"]


def test_semantic_index_save_and_load(tmp_path):
    searcher = SemanticSearcher(model=FakeEmbeddingModel()).build_index(sample_records())
    searcher.save(tmp_path, "sample")

    loaded = SemanticSearcher(model=FakeEmbeddingModel()).load(tmp_path, "sample")
    results = loaded.search("garage", top_k=1)

    assert results[0]["listing_id"] == "C"
    assert loaded.model_name == searcher.model_name


def test_bm25_search_returns_keyword_match_first():
    searcher = BM25Searcher().build(sample_records())

    results = searcher.search("ocean view", top_k=2)

    assert results[0]["listing_id"] == "B"
    assert results[0]["score"] > results[1]["score"]


def test_keyword_tokenizer_keeps_simple_real_estate_terms():
    assert tokenize("3-bed home with ocean-view!") == [
        "3",
        "bed",
        "home",
        "with",
        "ocean",
        "view",
    ]


def test_semantic_searcher_keeps_runtime_model_options():
    searcher = SemanticSearcher(local_files_only=True, batch_size=8)

    assert searcher.local_files_only is True
    assert searcher.batch_size == 8
