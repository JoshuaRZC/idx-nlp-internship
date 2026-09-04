"""Core retrieval and ranking service for public listing search."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import math
import time

from src.real_estate_nlp.answerability_checker import AnswerabilityChecker
from src.real_estate_nlp.listing_repository import ListingRepository
from src.real_estate_nlp.query_parser import QueryParser
from src.real_estate_nlp.schema_validator import SchemaValidator
from src.real_estate_nlp.search_snapshot import SearchSnapshot, SnapshotValidationError


VALID_SORTS = {"relevance", "price_asc", "price_desc"}
VALID_VARIANTS = {
    "bm25_only",
    "dense_only",
    "dense_signal",
    "dense_bm25_signal_rrf",
    "hybrid_cross_encoder",
}


class SearchUnavailableError(RuntimeError):
    """Raised when the service cannot safely produce a search result."""


class CrossEncoderReranker:
    """Lazy wrapper around a Cross Encoder for the final candidate window."""

    MAX_REMARK_CHARS = 1_500
    MAX_SUMMARY_CHARS = 350
    MAX_DOCUMENT_CHARS = 2_400

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
        facts = " | ".join(
            f"{name}: {record[name]}"
            for name in ("city", "price", "beds", "baths", "sqft")
            if record.get(name) is not None
        )
        signal_text = "; ".join(
            f"{bucket}: {', '.join(values)}"
            for bucket, values in sorted((record.get("text_signals") or {}).items())
            if values
        )
        remarks = (record.get("remarks_cleaned") or "").strip()
        summary = (record.get("summary") or "").strip()
        parts = []
        if facts:
            parts.append(f"Listing facts: {facts}")
        if remarks:
            parts.append(f"Remarks: {remarks[:CrossEncoderReranker.MAX_REMARK_CHARS]}")
        if signal_text:
            parts.append(f"Features: {signal_text}")
        if summary:
            parts.append(f"Summary: {summary[:CrossEncoderReranker.MAX_SUMMARY_CHARS]}")
        return "\n".join(parts)[:CrossEncoderReranker.MAX_DOCUMENT_CHARS]


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
        enable_cross_encoder=True,
        candidate_k=None,
        dense_candidate_k=100,
        bm25_candidate_k=100,
        signal_all_match_limit=200,
        signal_candidate_k=200,
        rerank_k=50,
        rrf_k=60,
        negative_signal_penalty=0.002,
        signal_match_weight=1.0,
        parallel_retrieval=True,
        retrieval_workers=2,
    ):
        self.snapshot = snapshot
        self.repository = repository
        self.parser = parser or QueryParser()
        self.validator = validator or SchemaValidator()
        self.answerability_checker = answerability_checker or AnswerabilityChecker(self.parser, self.validator)
        self.reranker = reranker or (CrossEncoderReranker() if enable_cross_encoder else None)
        self.enable_cross_encoder = enable_cross_encoder
        if candidate_k is not None:
            dense_candidate_k = candidate_k
            bm25_candidate_k = candidate_k
            signal_candidate_k = candidate_k
        self.dense_candidate_k = dense_candidate_k
        self.bm25_candidate_k = bm25_candidate_k
        self.signal_all_match_limit = signal_all_match_limit
        self.signal_candidate_k = signal_candidate_k
        self.rerank_k = rerank_k
        self.rrf_k = rrf_k
        self.negative_signal_penalty = negative_signal_penalty
        self.signal_match_weight = signal_match_weight
        if retrieval_workers < 1:
            raise ValueError("retrieval_workers must be at least 1")
        self.parallel_retrieval = parallel_retrieval
        self.retrieval_workers = retrieval_workers

    @classmethod
    def from_active_snapshot(cls, repository=None, search_root="data/models/search", **kwargs):
        try:
            snapshot = SearchSnapshot.load_active(search_root)
        except SnapshotValidationError as error:
            raise SearchUnavailableError(str(error)) from error
        return cls(snapshot, repository or ListingRepository.from_env(), **kwargs)

    def search(self, query, top_k=10, sort_by=None):
        return self._search(query, top_k, sort_by, "hybrid_cross_encoder")

    def search_experiment(self, query, variant, top_k=10, sort_by=None):
        if variant not in VALID_VARIANTS:
            raise ValueError(f"Unsupported search variant: {variant}")
        return self._search(query, top_k, sort_by, variant)

    def warm_up(self, include_cross_encoder=False):
        started_at = time.perf_counter()
        try:
            self.snapshot.semantic.warm_up()
        except Exception as error:
            raise SearchUnavailableError("Semantic model warm-up failed.") from error
        timings = {"dense_warm_up": self._elapsed_ms(started_at)}

        if include_cross_encoder:
            if self.reranker is None:
                raise SearchUnavailableError("Cross Encoder is not enabled.")
            listing_id = next(iter(self._retrievable_ids()))
            started_at = time.perf_counter()
            try:
                self.reranker.rerank("listing search warmup", [self._reranker_record({"listing_id": listing_id})])
            except Exception as error:
                raise SearchUnavailableError("Cross Encoder warm-up failed.") from error
            timings["cross_encoder_cold_start"] = self._elapsed_ms(started_at)

        return {"timings_ms": timings}

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
            "candidate_config": {
                "dense": self.dense_candidate_k,
                "bm25": self.bm25_candidate_k,
                "signal_all_match_limit": self.signal_all_match_limit,
                "signals": self.signal_candidate_k,
                "rerank": self.rerank_k,
            },
            "parallel_retrieval": self.parallel_retrieval,
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
        hard_filter_started_at = time.perf_counter()
        eligible_ids = self._eligible_ids(hard_filters)
        self._add_timing(base_meta, "hard_filter", hard_filter_started_at)
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
        retrieval = self._retrieve_sources(query, soft_signals, eligible_ids, variant, meta)
        if not retrieval["sources"]:
            raise SearchUnavailableError("No retrieval source is available.")

        fusion_started_at = time.perf_counter()
        fused = self._fuse_sources(
            retrieval["sources"],
            soft_signals,
            retrieval["signal_matches"],
            retrieval["signals_enabled"],
        )
        self._add_timing(meta, "rrf_fusion", fusion_started_at)
        meta.setdefault("candidate_counts", {})["rrf_union"] = len(fused)
        ordered = sorted(
            fused.values(),
            key=lambda item: (-item["score"], item["listing_id"]),
        )
        for rank, item in enumerate(ordered, start=1):
            item["pre_rerank_rank"] = rank
            item.setdefault("rrf_score", item["score"])
        if variant == "hybrid_cross_encoder" and self.enable_cross_encoder:
            ordered = self._rerank(query, ordered, meta)
        for rank, item in enumerate(ordered, start=1):
            item["post_rerank_rank"] = rank
        results = [self._result(item, rank) for rank, item in enumerate(ordered[:top_k], start=1)]
        return self._append_structured_fallback(results, eligible_ids, soft_signals, top_k)

    def _price_ranked(self, query, soft_signals, eligible_ids, top_k, sort_by, variant, meta):
        if not self._has_meaningful_soft_requirement(soft_signals):
            meta["price_sort_mode"] = "pure_field"
            meta["price_tiers"] = {"field_price": len(eligible_ids)}
            return self._price_results(
                self._sorted_by_price(eligible_ids, sort_by),
                top_k,
                "field_price",
                "field_sort",
            )

        meta["price_sort_mode"] = "soft_preference_tiers"
        signal_started_at = time.perf_counter()
        try:
            matches = self.snapshot.signals.match(soft_signals, eligible_ids)
        except Exception:
            self._mark_degraded(meta, "signals")
            matches = []
        finally:
            self._add_timing(meta, "signals", signal_started_at)

        required_matches = self.snapshot.signals.positive_signal_count(soft_signals)
        complete = [item for item in matches if required_matches and item["score"] >= required_matches]
        partial = [item for item in matches if item not in complete]
        meta["signal_selection"] = {
            "strategy": "price_tiers",
            "match_count": len(matches),
            "complete_match_count": len(complete),
            "partial_match_count": len(partial),
            "selected_count": len(matches),
        }

        tier_rows = []
        used_ids = set()
        for tier_name, tier_matches in (("signal_complete", complete), ("signal_partial", partial)):
            match_by_id = {item["listing_id"]: item for item in tier_matches}
            for listing_id in self._sorted_signal_matches(
                match_by_id,
                sort_by,
                use_match_strength=tier_name == "signal_partial",
            ):
                if len(tier_rows) == top_k:
                    break
                item = match_by_id[listing_id]
                tier_rows.append(
                    self._price_item(
                        listing_id,
                        tier_name,
                        "signal_match",
                        matches=item["matches"],
                    )
                )
                used_ids.add(listing_id)

        fallback = {}
        if len(tier_rows) < top_k:
            fallback = self._price_fallback_candidates(query, eligible_ids, meta)
            for listing_id in self._sorted_by_price(set(fallback) - used_ids, sort_by):
                if len(tier_rows) == top_k:
                    break
                tier_rows.append(
                    self._price_item(
                        listing_id,
                        "semantic_lexical_fallback",
                        "text_retrieval",
                        source_ranks=fallback[listing_id],
                    )
                )
                used_ids.add(listing_id)

        if len(tier_rows) < top_k:
            for listing_id in self._sorted_by_price(set(eligible_ids) - used_ids, sort_by):
                tier_rows.append(self._price_item(listing_id, "remaining_eligible", "remaining_eligible"))
                used_ids.add(listing_id)
                if len(tier_rows) == top_k:
                    break

        meta["price_tiers"] = {
            "signal_complete": len(complete),
            "signal_partial": len(partial),
            "semantic_lexical_fallback": len(fallback),
            "remaining_eligible": len(set(eligible_ids) - set(fallback) - {item["listing_id"] for item in matches}),
        }
        return [self._result(item, rank) for rank, item in enumerate(tier_rows, start=1)]

    def _price_fallback_candidates(self, query, eligible_ids, meta):
        candidates = {}
        query_embedding = None

        started_at = time.perf_counter()
        try:
            query_embedding = self.snapshot.semantic.encode_query(query)
            for item in self.snapshot.semantic.search_candidates_by_embedding(
                query_embedding,
                eligible_ids,
                self.dense_candidate_k,
            ):
                candidates.setdefault(item["listing_id"], {})["dense"] = item["rank"]
        except Exception:
            self._mark_degraded(meta, "dense")
        finally:
            self._add_timing(meta, "dense", started_at)

        started_at = time.perf_counter()
        try:
            for item in self.snapshot.bm25.search_candidates(query, eligible_ids, self.bm25_candidate_k):
                candidates.setdefault(item["listing_id"], {})["bm25"] = item["rank"]
        except Exception:
            self._mark_degraded(meta, "bm25")
        finally:
            self._add_timing(meta, "bm25", started_at)

        meta["fallback_candidate_count"] = len(candidates)
        meta.setdefault("candidate_counts", {})["semantic_lexical_fallback"] = len(candidates)
        return candidates

    def _price_results(self, listing_ids, top_k, match_tier, retrieval_status):
        return [
            self._result(self._price_item(listing_id, match_tier, retrieval_status), rank)
            for rank, listing_id in enumerate(listing_ids[:top_k], start=1)
        ]

    @staticmethod
    def _price_item(listing_id, match_tier, retrieval_status, matches=None, source_ranks=None):
        return {
            "listing_id": listing_id,
            "source_ranks": source_ranks or {},
            "matches": matches or [],
            "excluded": [],
            "signal_status": "selected" if matches else "not_used",
            "match_tier": match_tier,
            "retrieval_status": retrieval_status,
        }

    def _sorted_by_price(self, listing_ids, sort_by):
        return sorted(listing_ids, key=lambda listing_id: self._price_sort_key(listing_id, sort_by))

    def _sorted_signal_matches(self, matches_by_id, sort_by, use_match_strength):
        return sorted(
            matches_by_id,
            key=lambda listing_id: (
                -matches_by_id[listing_id]["score"] if use_match_strength else 0,
                *self._price_sort_key(listing_id, sort_by),
            ),
        )

    def _price_sort_key(self, listing_id, sort_by):
        price = self._numeric_value(self.snapshot.catalog_by_id[listing_id].get("price"))
        if price is None:
            return (1, 0, listing_id)
        return (0, price if sort_by == "price_asc" else -price, listing_id)

    def _retrieve_sources(self, query, soft_signals, eligible_ids, variant, meta):
        retrieval_started_at = time.perf_counter()
        sources = {}
        signal_matches = {}
        signals_enabled = variant in {"dense_signal", "dense_bm25_signal_rrf", "hybrid_cross_encoder"}
        uses_dense = variant in {"dense_only", "dense_signal", "dense_bm25_signal_rrf", "hybrid_cross_encoder"}
        uses_bm25 = variant in {"bm25_only", "dense_bm25_signal_rrf", "hybrid_cross_encoder"}
        tasks = {}
        if uses_dense:
            tasks["dense"] = lambda: self._retrieve_dense(query, eligible_ids)
        if uses_bm25:
            tasks["bm25"] = lambda: self.snapshot.bm25.search_candidates(
                query,
                eligible_ids,
                self.bm25_candidate_k,
            )
        if signals_enabled:
            tasks["signals"] = lambda: self.snapshot.signals.match(soft_signals, eligible_ids)

        task_results, ran_in_parallel = self._run_retrieval_tasks(tasks)
        meta["retrieval_execution"] = "parallel" if ran_in_parallel else "serial"

        dense_result = task_results.get("dense")
        query_embedding = None
        if dense_result:
            self._record_elapsed(meta, "dense", dense_result["elapsed_ms"])
            if dense_result["failed"]:
                self._mark_degraded(meta, "dense")
            else:
                query_embedding = dense_result["value"]["query_embedding"]
                sources["dense"] = dense_result["value"]["results"]

        bm25_result = task_results.get("bm25")
        if bm25_result:
            self._record_elapsed(meta, "bm25", bm25_result["elapsed_ms"])
            if bm25_result["failed"]:
                self._mark_degraded(meta, "bm25")
            else:
                sources["bm25"] = bm25_result["value"]

        signal_result = task_results.get("signals")
        if signal_result:
            self._record_elapsed(meta, "signals", signal_result["elapsed_ms"])
            if signal_result["failed"]:
                self._mark_degraded(meta, "signals")
                meta["signal_selection"] = {
                    "strategy": "unavailable",
                    "match_count": 0,
                    "selected_count": 0,
                }
            else:
                matches = signal_result["value"]
                signal_matches = {item["listing_id"]: item["matches"] for item in matches}
                selection_started_at = time.perf_counter()
                try:
                    sources["signals"], selection = self._select_signal_candidates(
                        query,
                        matches,
                        query_embedding,
                    )
                    meta["signal_selection"] = selection
                except Exception:
                    self._mark_degraded(meta, "signals")
                    meta["signal_selection"] = {
                        "strategy": "unavailable",
                        "match_count": 0,
                        "selected_count": 0,
                    }
                finally:
                    self._add_timing(meta, "signals", selection_started_at)
        else:
            meta["signal_selection"] = {
                "strategy": "not_used",
                "match_count": 0,
                "selected_count": 0,
            }

        meta.setdefault("candidate_counts", {}).update(
            {name: len(results) for name, results in sources.items()}
        )
        self._add_timing(meta, "retrieval_wall", retrieval_started_at)
        return {
            "sources": sources,
            "signal_matches": signal_matches,
            "signals_enabled": signals_enabled,
        }

    def _retrieve_dense(self, query, eligible_ids):
        query_embedding = self.snapshot.semantic.encode_query(query)
        return {
            "query_embedding": query_embedding,
            "results": self.snapshot.semantic.search_candidates_by_embedding(
                query_embedding,
                eligible_ids,
                self.dense_candidate_k,
            ),
        }

    def _run_retrieval_tasks(self, tasks):
        run_in_parallel = self.parallel_retrieval and len(tasks) > 1
        if not run_in_parallel:
            return {name: self._run_retrieval_task(task) for name, task in tasks.items()}, False

        workers = min(self.retrieval_workers, len(tasks))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="listing-retrieval") as executor:
            futures = {name: executor.submit(self._run_retrieval_task, task) for name, task in tasks.items()}
            return {name: future.result() for name, future in futures.items()}, True

    @staticmethod
    def _run_retrieval_task(task):
        started_at = time.perf_counter()
        try:
            return {
                "value": task(),
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "failed": False,
            }
        except Exception:
            return {
                "value": None,
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "failed": True,
            }

    def _select_signal_candidates(self, query, matches, query_embedding):
        selection = {
            "match_count": len(matches),
            "selected_count": 0,
            "strategy": "no_query_signals",
        }
        if not matches:
            return [], selection

        if len(matches) <= self.signal_all_match_limit:
            selected = [dict(item) for item in matches]
            selection["strategy"] = "all_matches"
        else:
            match_ids = {item["listing_id"] for item in matches}
            selected_ids = []
            if query_embedding is not None:
                ranked = self.snapshot.semantic.search_candidates_by_embedding(
                    query_embedding,
                    match_ids,
                    self.signal_candidate_k,
                )
                selected_ids = [item["listing_id"] for item in ranked]
                selection["strategy"] = "dense_secondary"
            else:
                try:
                    ranked = self.snapshot.bm25.search_candidates(query, match_ids, self.signal_candidate_k)
                    selected_ids = [item["listing_id"] for item in ranked]
                    selection["strategy"] = "bm25_secondary"
                except Exception:
                    selection["strategy"] = "match_score_fallback"
                    selection["secondary_ranker"] = "unavailable"

            if not selected_ids:
                selected_ids = [item["listing_id"] for item in matches[: self.signal_candidate_k]]
            match_by_id = {item["listing_id"]: item for item in matches}
            selected = [dict(match_by_id[listing_id]) for listing_id in selected_ids]

        for rank, item in enumerate(selected, start=1):
            item["rank"] = rank
        selection["selected_count"] = len(selected)
        return selected, selection

    def _fuse_sources(self, sources, soft_signals, signal_matches, signals_enabled):
        fused = {}
        for source_name, results in sources.items():
            for item in results:
                listing_id = str(item["listing_id"])
                entry = fused.setdefault(
                    listing_id,
                    {
                        "listing_id": listing_id,
                        "score": 0.0,
                        "rrf_score": 0.0,
                        "signal_boost": 0.0,
                        "source_ranks": {},
                        "matches": [],
                        "excluded": [],
                    },
                )
                if source_name == "signals":
                    entry["matches"] = item.get("matches", [])
                    entry["signal_selected"] = True
                    boost = self._signal_boost(item.get("score", 1.0))
                    entry["signal_boost"] += boost
                    entry["score"] += boost
                else:
                    entry["source_ranks"][source_name] = item["rank"]
                    contribution = 1 / (self.rrf_k + item["rank"])
                    entry["rrf_score"] += contribution
                    entry["score"] += contribution

        for listing_id, entry in fused.items():
            if not signals_enabled:
                entry["signal_status"] = "not_used"
            elif entry.get("signal_selected"):
                entry["signal_status"] = "selected"
            elif listing_id in signal_matches:
                entry["signal_status"] = "not_selected"
            else:
                entry["signal_status"] = "no_match"

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

        window = ordered[: self.rerank_k]
        records = [self._reranker_record(item) for item in window]
        started_at = time.perf_counter()
        try:
            scores = self.reranker.rerank(query, records)
        except Exception:
            if "cross_encoder" not in meta["degraded_components"]:
                meta["degraded_components"].append("cross_encoder")
            return ordered
        finally:
            meta["timings_ms"]["cross_encoder_rerank"] = self._elapsed_ms(started_at)

        reranked = sorted(
            window,
            key=lambda item: (-scores.get(item["listing_id"], float("-inf")), -item["score"], item["listing_id"]),
        )
        meta.setdefault("candidate_counts", {})["rerank_window"] = len(window)
        for item in window:
            item["cross_encoder_score"] = scores.get(item["listing_id"])
        return reranked + ordered[self.rerank_k :]

    def _reranker_record(self, item):
        listing_id = item["listing_id"]
        record = dict(self.snapshot.catalog_by_id[listing_id])
        record["summary"] = self.snapshot.summaries_by_id.get(listing_id, "")
        record["text_signals"] = self.snapshot.signals.signals_by_listing_id.get(listing_id, {})
        return record

    def _result(self, item, rank):
        listing_id = item["listing_id"]
        record = dict(self.snapshot.catalog_by_id[listing_id])
        record.update({
            "summary": self.snapshot.summaries_by_id.get(listing_id, ""),
            "rank": rank,
            "source_ranks": item["source_ranks"],
            "matched_signals": item["matches"],
            "excluded_signals": item["excluded"],
            "signal_status": item.get("signal_status", "not_used"),
            "retrieval_status": item.get(
                "retrieval_status",
                "text_retrieval" if listing_id in self._retrievable_ids() else "structured_fallback",
            ),
            "retrieval_evidence": item.get("retrieval_evidence") or self._retrieval_evidence(item),
        })
        if "score" in item:
            record["score"] = float(item["score"])
        if "rrf_score" in item:
            record["rrf_score"] = float(item["rrf_score"])
        if "signal_boost" in item:
            record["signal_boost"] = float(item["signal_boost"])
        for key in ("match_tier", "pre_rerank_rank", "post_rerank_rank", "cross_encoder_score"):
            if key in item:
                record[key] = item[key]
        return record

    def _append_structured_fallback(self, results, eligible_ids, soft_signals, top_k):
        if len(results) >= top_k or self._has_meaningful_soft_requirement(soft_signals):
            return results

        existing_ids = {item["listing_id"] for item in results}
        textless_ids = sorted(
            set(eligible_ids) - self._retrievable_ids() - existing_ids,
        )
        for listing_id in textless_ids:
            results.append(
                self._result(
                    {
                        "listing_id": listing_id,
                        "score": 0.0,
                        "source_ranks": {},
                        "matches": [],
                        "excluded": [],
                        "signal_status": "not_used",
                        "retrieval_status": "structured_fallback",
                    },
                    len(results) + 1,
                )
            )
            if len(results) == top_k:
                break
        return results

    def _has_meaningful_soft_requirement(self, soft_signals):
        for key, value in (soft_signals or {}).items():
            if key.endswith("_exclude"):
                continue
            values = value if isinstance(value, list) else [value]
            values = [str(item).lower() for item in values if item]
            if not values:
                continue
            if key == "property_type" and set(values) <= {"house", "home", "homes"}:
                continue
            return True
        return False

    @staticmethod
    def _retrieval_evidence(item):
        pieces = []
        for source in ("dense", "bm25"):
            if source in item["source_ranks"]:
                pieces.append(f"{source} #{item['source_ranks'][source]}")
        for match in item.get("matches", []):
            pieces.append(f"signal: {match['value']}")
        if not pieces:
            status = item.get("retrieval_status")
            if status:
                pieces.append(status.replace("_", " "))
        return "; ".join(pieces)

    def _signal_boost(self, match_strength):
        return self.signal_match_weight * float(match_strength) / (self.rrf_k + 1)

    def _retrievable_ids(self):
        listing_ids = getattr(self.snapshot, "retrievable_listing_ids", None)
        if listing_ids is not None:
            return listing_ids
        return {
            str(item.get("listing_id") or item.get("L_ListingID"))
            for item in getattr(self.snapshot.semantic, "metadata", [])
        }

    @staticmethod
    def _mark_degraded(meta, component):
        if component not in meta.setdefault("degraded_components", []):
            meta["degraded_components"].append(component)

    def _add_timing(self, meta, name, started_at):
        self._record_elapsed(meta, name, self._elapsed_ms(started_at))

    @staticmethod
    def _record_elapsed(meta, name, elapsed_ms):
        meta["timings_ms"][name] = round(meta["timings_ms"].get(name, 0) + elapsed_ms, 2)

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
