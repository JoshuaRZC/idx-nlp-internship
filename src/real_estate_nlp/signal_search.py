"""In-memory retrieval over normalized listing signals."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from src.real_estate_nlp.signal_schema import normalize_value


BUCKET_ALIASES = {
    "room": "rooms",
}

VALUE_BUCKET_OVERRIDES = {
    ("amenities", "garage"): ("parking", "garage"),
    ("amenities", "driveway"): ("parking", "driveway"),
    ("amenities", "rv parking"): ("parking", "rv parking"),
}


class SignalSearcher:
    """Rank listings by overlap with extracted soft signals."""

    def __init__(self):
        self.signals_by_listing_id = {}
        self.postings = {}

    def build(self, records: Iterable[dict]):
        self.signals_by_listing_id = {}
        postings = defaultdict(lambda: defaultdict(set))

        for record in records:
            listing_id = str(record.get("listing_id") or "")
            if not listing_id:
                continue
            text_signals = record.get("text_signals") or {}
            normalized = {}
            for bucket, values in text_signals.items():
                target_bucket = BUCKET_ALIASES.get(bucket, bucket)
                normalized_values = sorted({normalize_value(value) for value in values if value})
                normalized[target_bucket] = normalized_values
                for value in normalized_values:
                    postings[target_bucket][value].add(listing_id)
            self.signals_by_listing_id[listing_id] = normalized

        self.postings = {
            bucket: {value: sorted(ids) for value, ids in values.items()}
            for bucket, values in postings.items()
        }
        return self

    def search(self, soft_signals: dict, candidate_ids: Iterable, top_k: int = 100):
        results = self.match(soft_signals, candidate_ids)
        for rank, item in enumerate(results[:top_k], start=1):
            item["rank"] = rank
        return results[:top_k]

    def match(self, soft_signals: dict, candidate_ids: Iterable):
        candidate_ids = {str(value) for value in candidate_ids}
        if not candidate_ids:
            return []

        positive_pairs = self._signal_pairs(soft_signals, excluded=False)
        if not positive_pairs:
            return []

        matched = defaultdict(list)
        for bucket, value in positive_pairs:
            for listing_id in self._matching_ids(bucket, value):
                if listing_id in candidate_ids:
                    matched[listing_id].append({"bucket": bucket, "value": value})

        results = []
        for listing_id, matches in matched.items():
            results.append(
                {
                    "listing_id": listing_id,
                    "score": float(len(matches)),
                    "matches": sorted(matches, key=lambda item: (item["bucket"], item["value"])),
                }
            )
        results.sort(key=lambda item: (-item["score"], item["listing_id"]))
        return results

    def positive_signal_count(self, soft_signals: dict):
        return len(self._signal_pairs(soft_signals, excluded=False))

    def exclusion_matches(self, soft_signals: dict, listing_ids: Iterable):
        listing_ids = {str(value) for value in listing_ids}
        matches = defaultdict(list)
        for bucket, value in self._signal_pairs(soft_signals, excluded=True):
            for listing_id in self._matching_ids(bucket, value):
                if listing_id in listing_ids:
                    matches[listing_id].append({"bucket": bucket, "value": value})
        return {listing_id: values for listing_id, values in matches.items()}

    def save(self, output_dir: str | Path, name: str = "signals"):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / f"{name}.json").open("w", encoding="utf-8") as handle:
            json.dump({"signals": self.signals_by_listing_id}, handle, ensure_ascii=False)

    def load(self, input_dir: str | Path, name: str = "signals"):
        with (Path(input_dir) / f"{name}.json").open(encoding="utf-8") as handle:
            payload = json.load(handle)
        records = [
            {"listing_id": listing_id, "text_signals": text_signals}
            for listing_id, text_signals in payload["signals"].items()
        ]
        return self.build(records)

    def _matching_ids(self, bucket, value):
        values = self._matching_values(bucket, value)
        postings = self.postings.get(bucket, {})
        return {listing_id for item in values for listing_id in postings.get(item, [])}

    @staticmethod
    def _matching_values(bucket, value):
        if bucket == "amenities" and value == "pool":
            return {"pool", "private pool", "community pool"}
        if bucket == "location_features" and value == "view":
            return {"view", "ocean view", "water view", "mountain view", "city lights view"}
        return {value}

    @staticmethod
    def _signal_pairs(soft_signals, excluded):
        pairs = []
        suffix = "_exclude"
        for key, values in (soft_signals or {}).items():
            is_exclusion = key.endswith(suffix)
            if is_exclusion != excluded or not isinstance(values, list):
                continue
            bucket = key[: -len(suffix)] if is_exclusion else key
            bucket = BUCKET_ALIASES.get(bucket, bucket)
            for value in values:
                normalized_value = normalize_value(value)
                bucket, normalized_value = VALUE_BUCKET_OVERRIDES.get(
                    (bucket, normalized_value),
                    (bucket, normalized_value),
                )
                if normalized_value:
                    pairs.append((bucket, normalized_value))
        return pairs
