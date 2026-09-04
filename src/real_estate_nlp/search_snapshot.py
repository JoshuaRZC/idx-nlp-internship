"""Build, validate, and load versioned public search snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from src.real_estate_nlp.compliance_checker import ComplianceChecker
from src.real_estate_nlp.keyword_search import BM25Searcher
from src.real_estate_nlp.listing_summarizer import ListingSummarizer
from src.real_estate_nlp.semantic_search import DEFAULT_MODEL_NAME, SemanticSearcher, json_safe
from src.real_estate_nlp.signal_extractor import SignalExtractor
from src.real_estate_nlp.signal_search import SignalSearcher
from src.real_estate_nlp.text_cleaner import TextCleaner


CATALOG_FIELDS = ("listing_id", "address", "city", "price", "beds", "baths", "sqft", "remarks_cleaned")


class SnapshotValidationError(ValueError):
    """Raised when a snapshot is incomplete, corrupted, or not publishable."""


class SearchSnapshot:
    """Loaded pass-only data and retrieval artifacts for one search version."""

    def __init__(self, snapshot_dir, manifest, catalog, summaries, semantic, bm25, signals):
        self.snapshot_dir = Path(snapshot_dir)
        self.manifest = manifest
        self.catalog_by_id = {str(item["listing_id"]): item for item in catalog}
        self.summaries_by_id = {str(item["listing_id"]): item["summary"] for item in summaries}
        self.pass_listing_ids = set(self.catalog_by_id)
        self.retrievable_listing_ids = {
            str(item.get("listing_id") or item.get("L_ListingID"))
            for item in semantic.metadata
        }
        self.semantic = semantic
        self.bm25 = bm25
        self.signals = signals

    @property
    def snapshot_id(self):
        return self.manifest["snapshot_id"]

    @classmethod
    def load_active(cls, search_root="data/models/search"):
        search_root = Path(search_root)
        pointer_path = search_root / "active.json"
        if not pointer_path.exists():
            raise SnapshotValidationError("No active public search snapshot is available.")
        with pointer_path.open(encoding="utf-8") as handle:
            pointer = json.load(handle)
        snapshot_id = pointer.get("snapshot_id")
        candidates = []
        if pointer.get("snapshot_path"):
            candidates.append(Path(pointer["snapshot_path"]))
        if snapshot_id:
            candidates.append(search_root.parent / "search_snapshots" / snapshot_id)

        for snapshot_dir in candidates:
            if snapshot_dir.exists():
                return cls.load(snapshot_dir)
        raise SnapshotValidationError("The active search snapshot is not available at its configured path.")

    @classmethod
    def load(cls, snapshot_dir):
        snapshot_dir = Path(snapshot_dir)
        manifest = validate_snapshot(snapshot_dir)
        catalog = read_jsonl(snapshot_dir / "catalog.jsonl")
        summaries = read_jsonl(snapshot_dir / "summaries.jsonl")
        semantic = SemanticSearcher().load(snapshot_dir / "semantic", "listings")
        bm25 = BM25Searcher().load(snapshot_dir / "bm25", "listings")
        signals = SignalSearcher().load(snapshot_dir / "signals", "listings")
        return cls(snapshot_dir, manifest, catalog, summaries, semantic, bm25, signals)


class SearchSnapshotBuilder:
    """Create a coherent public search snapshot from one source record set."""

    def __init__(
        self,
        taxonomy_path="data/processed/taxonomy.json",
        model_name=DEFAULT_MODEL_NAME,
        compliance_checker=None,
        text_cleaner=None,
        signal_extractor=None,
        summarizer=None,
        semantic_searcher=None,
    ):
        self.compliance_checker = compliance_checker or ComplianceChecker()
        self.text_cleaner = text_cleaner or TextCleaner()
        self.signal_extractor = signal_extractor or SignalExtractor(taxonomy_path=taxonomy_path)
        self.summarizer = summarizer or ListingSummarizer()
        self.semantic_searcher = semantic_searcher or SemanticSearcher(model_name=model_name)
        self.model_name = model_name

    def build(self, records, snapshot_root, snapshot_id=None, activate=True):
        records = list(records)
        snapshot_root = Path(snapshot_root)
        snapshot_id = snapshot_id or self._snapshot_id(records)
        final_dir = snapshot_root / snapshot_id
        if final_dir.exists():
            raise FileExistsError(f"Snapshot already exists: {final_dir}")

        temporary_dir = snapshot_root / f".{snapshot_id}.tmp"
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        temporary_dir.mkdir(parents=True)

        try:
            audit, public_records = self._screen_records(records)
            if not public_records:
                raise SnapshotValidationError("Compliance scan produced no publishable listings.")
            signals = self.signal_extractor.extract_many(public_records)
            signal_by_id = {str(item["listing_id"]): item for item in signals}
            summaries = [
                {
                    "listing_id": str(record["listing_id"]),
                    "summary": self.summarizer.summarize(record, signal_by_id[str(record["listing_id"])]),
                }
                for record in public_records
            ]

            write_jsonl(audit, temporary_dir / "compliance_audit.jsonl")
            write_jsonl(public_records, temporary_dir / "catalog.jsonl")
            write_jsonl(summaries, temporary_dir / "summaries.jsonl")

            self.semantic_searcher.build_index(public_records).save(temporary_dir / "semantic", "listings")
            BM25Searcher().build(public_records).save(temporary_dir / "bm25", "listings")
            SignalSearcher().build(signals).save(temporary_dir / "signals", "listings")

            manifest = self._manifest(temporary_dir, snapshot_id, len(audit), len(public_records))
            write_json(manifest, temporary_dir / "manifest.json")
            validate_snapshot(temporary_dir)
            os.replace(temporary_dir, final_dir)
        except Exception:
            if temporary_dir.exists():
                shutil.rmtree(temporary_dir)
            raise

        if activate:
            activate_snapshot(final_dir, snapshot_root.parent / "search")
        return final_dir

    def _screen_records(self, records):
        audit = []
        public_records = []
        for record in records:
            normalized = self._normalize_record(record)
            decision = self.compliance_checker.check_listing(record.get("remarks") or record.get("L_Remarks"))
            audit.append({"listing_id": normalized["listing_id"], **decision})
            if decision["status"] == "pass":
                public_records.append(normalized)
        return audit, public_records

    def _normalize_record(self, record):
        source = dict(record)
        values = {
            "listing_id": self._first(source, "listing_id", "L_ListingID"),
            "address": self._first(source, "address", "L_Address"),
            "city": self._first(source, "city", "L_City"),
            "price": self._first(source, "price", "L_SystemPrice"),
            "beds": self._first(source, "beds", "L_Keyword2"),
            "baths": self._first(source, "baths", "LM_Dec_3"),
            "sqft": self._first(source, "sqft", "LM_Int2_3"),
        }
        values["listing_id"] = str(values["listing_id"])
        values["remarks_cleaned"] = self.text_cleaner.clean_text(
            self._first(source, "remarks", "L_Remarks")
        )
        return {key: json_safe(value) for key, value in values.items()}

    def _manifest(self, snapshot_dir, snapshot_id, source_count, public_count):
        files = {
            path.relative_to(snapshot_dir).as_posix(): sha256(path)
            for path in sorted(snapshot_dir.rglob("*"))
            if path.is_file()
        }
        with (snapshot_dir / "semantic" / "listings_metadata.json").open(encoding="utf-8") as handle:
            retrievable_count = len(json.load(handle)["metadata"])
        return {
            "snapshot_id": snapshot_id,
            "built_at": datetime.now(UTC).isoformat(),
            "source_listing_count": source_count,
            "public_listing_count": public_count,
            "retrievable_listing_count": retrievable_count,
            "compliance_rule_version": self.compliance_checker.rule_version,
            "dense_model": self.model_name,
            "files": files,
        }

    @staticmethod
    def _snapshot_id(records):
        digest = hashlib.sha256(
            "|".join(str(record.get("listing_id") or record.get("L_ListingID") or "") for record in records).encode()
        ).hexdigest()[:10]
        return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{digest}"

    @staticmethod
    def _first(record, *keys):
        for key in keys:
            value = record.get(key)
            if value is not None:
                return value
        return None


def activate_snapshot(snapshot_dir, search_root="data/models/search"):
    snapshot_dir = Path(snapshot_dir)
    validate_snapshot(snapshot_dir)
    search_root = Path(search_root)
    search_root.mkdir(parents=True, exist_ok=True)
    pointer = {
        "snapshot_id": snapshot_dir.name,
        "snapshot_path": str(snapshot_dir.resolve()),
        "activated_at": datetime.now(UTC).isoformat(),
    }
    temporary_path = search_root / ".active.tmp"
    write_json(pointer, temporary_path)
    os.replace(temporary_path, search_root / "active.json")


def validate_snapshot(snapshot_dir):
    snapshot_dir = Path(snapshot_dir)
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise SnapshotValidationError("Snapshot manifest is missing.")
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    required = {"catalog.jsonl", "summaries.jsonl", "compliance_audit.jsonl", "semantic/listings.faiss", "semantic/listings_embeddings.npy", "semantic/listings_metadata.json", "bm25/listings.json", "signals/listings.json"}
    files = set(manifest.get("files", {}))
    if missing := required - files:
        raise SnapshotValidationError(f"Snapshot manifest is missing files: {sorted(missing)}")
    for relative_path, expected_checksum in manifest["files"].items():
        path = snapshot_dir / relative_path
        if not path.exists() or sha256(path) != expected_checksum:
            raise SnapshotValidationError(f"Snapshot checksum failed: {relative_path}")

    catalog = read_jsonl(snapshot_dir / "catalog.jsonl")
    audit = read_jsonl(snapshot_dir / "compliance_audit.jsonl")
    summaries = read_jsonl(snapshot_dir / "summaries.jsonl")
    with (snapshot_dir / "semantic" / "listings_metadata.json").open(encoding="utf-8") as handle:
        semantic_ids = {str(item.get("listing_id")) for item in json.load(handle)["metadata"]}
    with (snapshot_dir / "bm25" / "listings.json").open(encoding="utf-8") as handle:
        bm25_ids = {str(item.get("listing_id")) for item in json.load(handle)["metadata"]}
    with (snapshot_dir / "signals" / "listings.json").open(encoding="utf-8") as handle:
        signal_ids = set(json.load(handle)["signals"])
    public_ids = {str(item["listing_id"]) for item in catalog}
    passed_ids = {str(item["listing_id"]) for item in audit if item["status"] == "pass"}
    if not public_ids <= passed_ids:
        raise SnapshotValidationError("Public catalog contains a non-pass listing.")
    if len(public_ids) != len(catalog):
        raise SnapshotValidationError("Public catalog contains duplicate listing IDs.")
    if {str(item["listing_id"]) for item in summaries} != public_ids:
        raise SnapshotValidationError("Summary artifact does not match the public catalog.")
    if signal_ids != public_ids:
        raise SnapshotValidationError("Signal artifact does not match the public catalog.")
    if semantic_ids != bm25_ids or not semantic_ids <= public_ids:
        raise SnapshotValidationError("Text retrieval artifacts do not match the public catalog.")
    if len(catalog) != manifest["public_listing_count"]:
        raise SnapshotValidationError("Public listing count does not match manifest.")
    if len(audit) != manifest["source_listing_count"]:
        raise SnapshotValidationError("Source listing count does not match manifest.")
    if len(semantic_ids) != manifest["retrievable_listing_count"]:
        raise SnapshotValidationError("Retrievable listing count does not match manifest.")
    return manifest


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(records, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=json_safe) + "\n")


def write_json(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_safe)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
