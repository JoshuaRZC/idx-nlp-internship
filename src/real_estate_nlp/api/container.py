"""Application-scoped component lifecycle management."""

from __future__ import annotations

import logging

from src.real_estate_nlp.api.config import ApiSettings
from src.real_estate_nlp.api.redis_store import RedisStore
from src.real_estate_nlp.compliance_checker import ComplianceChecker
from src.real_estate_nlp.entity_extractor import EntityExtractor
from src.real_estate_nlp.listing_summarizer import ListingSummarizer
from src.real_estate_nlp.query_intent_classifier import QueryIntentClassifier
from src.real_estate_nlp.query_parser import QueryParser
from src.real_estate_nlp.search_service import SearchService


LOGGER = logging.getLogger(__name__)


class ApiContainer:
    """Own shared NLP components and report whether the process is ready."""

    def __init__(
        self,
        settings=None,
        search_service=None,
        entity_extractor=None,
        summarizer=None,
        compliance_checker=None,
        intent_classifier=None,
        store=None,
    ):
        self.settings = settings or ApiSettings.from_env()
        self.search_service = search_service
        self.entity_extractor = entity_extractor
        self.summarizer = summarizer
        self.compliance_checker = compliance_checker
        self.intent_classifier = intent_classifier
        self.store = store
        self.ready = False
        self.startup_error = None

    def start(self):
        self.ready = False
        self.startup_error = None
        try:
            self.store = self.store or RedisStore.from_url(
                self.settings.redis_url,
                self.settings.cache_namespace,
            )
            self.store.ping()

            self.intent_classifier = self.intent_classifier or QueryIntentClassifier.load(
                self.settings.intent_model_dir
            )
            parser = QueryParser(intent_classifier=self.intent_classifier)
            self.search_service = self.search_service or SearchService.from_active_snapshot(
                parser=parser,
                search_root=self.settings.search_root,
            )
            self.entity_extractor = self.entity_extractor or EntityExtractor()
            self.summarizer = self.summarizer or ListingSummarizer()
            self.compliance_checker = self.compliance_checker or ComplianceChecker()
            self.search_service.warm_up(include_cross_encoder=True)
            self.ready = True
            LOGGER.info("API startup completed for snapshot=%s", self.snapshot_id)
        except Exception as error:
            self.startup_error = str(error)
            LOGGER.exception("API startup failed")

    def stop(self):
        if self.store is not None:
            try:
                self.store.close()
            except Exception:
                LOGGER.warning("Redis connection close failed", exc_info=True)

    @property
    def snapshot_id(self):
        snapshot = getattr(self.search_service, "snapshot", None)
        return getattr(snapshot, "snapshot_id", None)
