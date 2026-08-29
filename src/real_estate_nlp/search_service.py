"""Core retrieval and ranking service for public listing search."""

from __future__ import annotations

import math
import time
from collections import defaultdict

from src.real_estate_nlp.answerability_checker import AnswerabilityChecker
from src.real_estate_nlp.listing_repository import ListingRepository
from src.real_estate_nlp.query_parser import QueryParser
from src.real_estate_nlp.schema_validator import SchemaValidator
from src.real_estate_nlp.search_snapshot import SearchSnapshot, SnapshotValidationError


VALID_SORTS = {"relevance", "price_asc", "price_desc"}
VALID_VARIANTS = {
    "dense_only",
    "dense_signal",
    "dense_bm25_signal_rrf",
    "hybrid_cross_encoder",
}


class SearchUnavailableError(RuntimeError):
    """Raised when the service cannot safely produce a search result."""


class CrossEncoderReranker:
    """Lazy wrapper around a Cross Encoder for the final candidate window."""

    def __init__(self, model_name="cross-encoder/ms-marco-MiniLM-L6-v2", model=None):
        self.model_name = model_name
        self.model = model

    def rerank(self, query, records):
        if not records:
            return {}
        if self.model is None:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(self.model_name)

        pairs = [(query, self._document(record)) for record in records]
        scores = self.model.predict(pairs)
        return {record["listing_id"]: float(score) for record, score in zip(records, scores)}

    @staticmethod
    def _document(record):
        signal_text = "; ".join(
            f"{bucket}: {', '.join(values)}"
            for bucket, values in sorted((record.get("text_signals") or {}).items())
            if values
        )
        parts = [record.get("summary") or record.get("remarks_cleaned") or ""]
        if signal_text:
            parts.append(f"Features: {signal_text}")
        return "\n".join(parts)


class SearchService:
    """Coordinate parsing, eligibility, retrieval, fusion, and presentation."""

    def __init__(
        self,
        snapshot,
        repository,
        parser=None,
        validator=None,
        answerability_checker=None,
        reranker=None,
        enable_cross_encoder=False,
        candidate_k=100,
        rrf_k=60,
        negative_signal_penalty=0.002,
    ):
        self.snapshot = snapshot
        self.repository = repository
        self.parser = parser or QueryParser()
        self.validator = validator or SchemaValidator()
        self.answerability_checker = answerability_checker or AnswerabilityChecker(self.parser, self.validator)
        self.reranker = reranker or (CrossEncoderReranker() if enable_cross_encoder else None)
        self.enable_cross_encoder = enable_cross_encoder
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self.negative_signal_penalty = negative_signal_penalty

    @classmethod
    def from_active_snapshot(cls, repository=None, search_root="data/models/search", **kwargs):
        try:
            snapshot = SearchSnapshot.load_active(search_root)
        except SnapshotValidationError as error:
            raise SearchUnavailableError(str(error)) from error
        return cls(snapshot, repository or ListingRepository.from_env(), **kwargs)

    def search(self, query, top_k=10, sort_by=None):
        return self._search(query, top_k, sort_by, "dense_bm25_signal_rrf")

    def search_experiment(self, query, variant, top_k=10, sort_by=None):
        if variant not in VALID_VARIANTS:
            raise ValueError(f"Unsupported search variant: {variant}")
        return self._search(query, top_k, sort_by, variant)

    def _search(self, query, top_k, sort_by, variant):
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        started_at = time.perf_counter()
        parsed = self.parser.parse(query)
        answerable, message = self.answerability_checker.check_pre_query(query, parsed=parsed)
        base_meta = {
            "snapshot_id": self.snapshot.snapshot_id,
            "variant": variant,
            "timings_ms": {},
            "degraded_components": [],
        }
        if not answerable:
            base_meta["timings_ms"]["total"] = self._elapsed_ms(started_at)
            return self._response(False, message, [], parsed, base_meta)

        effective_sort = self._effective_sort(sort_by, parsed)
        base_meta["effective_sort"] = effective_sort
        hard_filters = {
            key: value
            for key, value in parsed["hard_filters"].items()
            if key in ListingRepository.FILTERS
        }
        base_meta["applied_hard_filters"] = hard_filters
        eligible_ids = self._eligible_ids(hard_filters)
        base_meta["eligible_count"] = len(eligible_ids)
        if not eligible_ids:
            base_meta["timings_ms"]["total"] = self._elapsed_ms(started_at)
            return self._response(True, "No listings match your criteria.", [], parsed, base_meta)

        if effective_sort != "relevance":
            ranked = self._price_ranked(query, parsed["soft_signals"], eligible_ids, top_k, effective_sort, variant, base_meta)
        else:
            ranked = self._rank_relevance(query, parsed["soft_signals"], eligible_ids, top_k, variant, base_meta)

        base_meta["timings_ms"]["total"] = self._elapsed_ms(started_at)
        message = "Results found." if ranked else "No listings match your criteria."
        return self._response(True, message, ranked, parsed, base_meta)

    def _eligible_ids(self, hard_filters):
        if not hard_filters:
            return set(self.snapshot.pass_listing_ids)
        try:
            database_ids = self.repository.find_candidate_ids(hard_filters)
        except Exception as error:
            raise SearchUnavailableError("Structured eligibility is unavailable.") from error
        return {str(listing_id) for listing_id in database_ids} & self.snapshot.pass_listing_ids

    def _rank_relevance(self, query, soft_signals, eligible_ids, top_k, variant, meta):
        sources = self._retrieve_sources(query, soft_signals, eligible_ids, variant, meta)
        if not sources:
            raise SearchUnavailableError("No retrieval source is available.")

        fused = self._fuse_sources(sources, soft_signals)
        ordered = sorted(
            fused.values(),
            key=lambda item: (-item["score"], item["listing_id"]),
        )
        if variant == "hybrid_cross_encoder" and self.enable_cross_encoder:
            ordered = self._rerank(query, ordered, meta)
        return [self._result(item, rank) for rank, item in enumerate(ordered[:top_k], start=1)]

    def _price_ranked(self, query, soft_signals, eligible_ids, top_k, sort_by, variant, meta):
        buckets = defaultdict(list)
        missing = []
        for listing_id in eligible_ids:
            price = self._numeric_value(self.snapshot.catalog_by_id[listing_id].get("price"))
            if price is None:
                missing.append(listing_id)
            else:
                buckets[price].append(listing_id)

        prices = sorted(buckets, reverse=sort_by == "price_desc")
        ordered = []
        for price in prices:
            remaining = top_k - len(ordered)
            if remaining <= 0:
                break
            group_ids = set(buckets[price])
            ranked = self._rank_relevance(query, soft_signals, group_ids, max(remaining, 1), variant, meta)
            ordered.extend(ranked)
            ranked_ids = {item["listing_id"] for item in ranked}
            for listing_id in sorted(group_ids - ranked_ids):
                ordered.append(
                    self._result(
                        {"listing_id": listing_id, "score": 0.0, "source_ranks": {}, "matches": [], "excluded": []},
                        len(ordered) + 1,
                    )
                )
                if len(ordered) == top_k:
                    break

        if len(ordered) < top_k:
            for listing_id in sorted(missing):
                ordered.append(self._result({"listing_id": listing_id, "score": 0.0, "source_ranks": {}, "matches": [], "excluded": []}, len(ordered) + 1))
                if len(ordered) == top_k:
                    break

        for rank, item in enumerate(ordered, start=1):
            item["rank"] = rank
        return ordered

    def _retrieve_sources(self, query, soft_signals, eligible_ids, variant, meta):
        sources = {}
        source_methods = []
        if variant in {"dense_only", "dense_signal", "dense_bm25_signal_rrf", "hybrid_cross_encoder"}:
            source_methods.append(("dense", lambda: self.snapshot.semantic.search_candidates(query, eligible_ids, self.candidate_k)))
        if variant in {"dense_bm25_signal_rrf", "hybrid_cross_encoder"}:
            source_methods.append(("bm25", lambda: self.snapshot.bm25.search_candidates(query, eligible_ids, self.candidate_k)))
        if variant in {"dense_signal", "dense_bm25_signal_rrf", "hybrid_cross_encoder"}:
            source_methods.append(("signals", lambda: self.snapshot.signals.search(soft_signals, eligible_ids, self.candidate_k)))

        for name, method in source_methods:
            started_at = time.perf_counter()
            try:
                sources[name] = method()
            except Exception:
                if name not in meta["degraded_components"]:
                    meta["degraded_components"].append(name)
            finally:
                meta["timings_ms"][name] = round(
                    meta["timings_ms"].get(name, 0) + self._elapsed_ms(started_at),
                    2,
                )
        return sources

    def _fuse_sources(self, sources, soft_signals):
        fused = {}
        for source_name, results in sources.items():
            for item in results:
                listing_id = str(item["listing_id"])
                entry = fused.setdefault(
                    listing_id,
                    {"listing_id": listing_id, "score": 0.0, "source_ranks": {}, "matches": [], "excluded": []},
                )
                entry["score"] += 1 / (self.rrf_k + item["rank"])
                entry["source_ranks"][source_name] = item["rank"]
                if source_name == "signals":
                    entry["matches"] = item.get("matches", [])

        exclusions = self.snapshot.signals.exclusion_matches(soft_signals, fused)
        for listing_id, matches in exclusions.items():
            fused[listing_id]["excluded"] = matches
            fused[listing_id]["score"] -= self.negative_signal_penalty * len(matches)
        return fused

    def _rerank(self, query, ordered, meta):
        if self.reranker is None:
            if "cross_encoder" not in meta["degraded_components"]:
                meta["degraded_components"].append("cross_encoder")
            return ordered

        window = ordered[: self.candidate_k]
        records = [self._reranker_record(item) for item in window]
        started_at = time.perf_counter()
        try:
            scores = self.reranker.rerank(query, records)
        except Exception:
            if "cross_encoder" not in meta["degraded_components"]:
                meta["degraded_components"].append("cross_encoder")
            return ordered
        finally:
            meta["timings_ms"]["cross_encoder"] = self._elapsed_ms(started_at)

        reranked = sorted(
            window,
            key=lambda item: (-scores.get(item["listing_id"], float("-inf")), -item["score"], item["listing_id"]),
        )
        return reranked + ordered[self.candidate_k :]

    def _reranker_record(self, item):
        listing_id = item["listing_id"]
        record = dict(self.snapshot.catalog_by_id[listing_id])
        record["summary"] = self.snapshot.summaries_by_id.get(listing_id, "")
        record["text_signals"] = self.snapshot.signals.signals_by_listing_id.get(listing_id, {})
        return record

    def _result(self, item, rank):
        listing_id = item["listing_id"]
        record = dict(self.snapshot.catalog_by_id[listing_id])
        record.update(
            {
                "summary": self.snapshot.summaries_by_id.get(listing_id, ""),
                "rank": rank,
                "score": float(item["score"]),
                "source_ranks": item["source_ranks"],
                "matched_signals": item["matches"],
                "excluded_signals": item["excluded"],
            }
        )
        return record

    @staticmethod
    def _response(ok, message, results, parsed, meta):
        return {"ok": ok, "message": message, "parsed_query": parsed, "results": results, "meta": meta}

    @staticmethod
    def _effective_sort(sort_by, parsed):
        if sort_by is not None:
            if sort_by not in VALID_SORTS:
                raise ValueError(f"Unsupported sort_by: {sort_by}")
            return sort_by
        parsed_sort = parsed.get("filters", {}).get("sort")
        return parsed_sort if parsed_sort in VALID_SORTS else "relevance"

    @staticmethod
    def _numeric_value(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _elapsed_ms(started_at):
        return round((time.perf_counter() - started_at) * 1000, 2)
