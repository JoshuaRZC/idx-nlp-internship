"""Language-based intent classification for real estate search queries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class QueryIntentClassifier:
    LABELS = ("browsing", "researching", "high_intent_inquiry")
    DEFAULT_CITY_LIST_PATH = "data/processed/valid_cities.json"

    def __init__(
        self,
        max_features: int = 2_000,
        confidence_threshold: float = 0.60,
        c: float = 1.0,
        class_weight=None,
        min_df: int = 1,
        sublinear_tf: bool = False,
        cities=None,
        city_list_path: str | Path = DEFAULT_CITY_LIST_PATH,
    ):
        self.max_features = max_features
        self.confidence_threshold = confidence_threshold
        self.c = c
        self.class_weight = class_weight
        self.min_df = min_df
        self.sublinear_tf = sublinear_tf
        self.city_list_path = self._project_path(city_list_path)
        self.cities = sorted(cities or self._load_city_list(), key=len, reverse=True)
        self.city_pattern = self._city_pattern()
        self.model = None

    def fit(self, queries: Iterable[str], labels: Iterable[str]):
        queries = list(queries)
        labels = np.asarray(list(labels))
        unknown = set(labels) - set(self.LABELS)
        if unknown:
            raise ValueError(f"Unsupported intent labels: {sorted(unknown)}")

        base_model = Pipeline(
            [
                (
                    "vectorizer",
                    TfidfVectorizer(
                        ngram_range=(1, 2),
                        max_features=self.max_features,
                        min_df=self.min_df,
                        sublinear_tf=self.sublinear_tf,
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1_000,
                        C=self.c,
                        class_weight=self.class_weight,
                    ),
                ),
            ]
        )
        self.model = CalibratedClassifierCV(base_model, method="sigmoid", cv=5)
        self.model.fit(self._prepare_queries(queries), labels)
        return self

    def train(self, queries: Iterable[str], labels: Iterable[str]):
        return self.fit(queries, labels)

    def predict(self, query: str):
        self._require_model()
        probabilities = self.model.predict_proba(self._prepare_queries([query]))[0]
        index = probabilities.argmax()
        confidence = float(probabilities[index])
        return {
            "label": str(self.model.classes_[index]),
            "confidence": confidence,
            "is_uncertain": confidence < self.confidence_threshold,
        }

    def predict_many(self, queries: Iterable[str]):
        return [self.predict(query) for query in queries]

    def save(self, model_dir: str | Path):
        self._require_model()
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, model_dir / "classifier.joblib")
        (model_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "labels": list(self.LABELS),
                    "max_features": self.max_features,
                    "confidence_threshold": self.confidence_threshold,
                    "c": self.c,
                    "class_weight": self.class_weight,
                    "min_df": self.min_df,
                    "sublinear_tf": self.sublinear_tf,
                    "cities": self.cities,
                },
                indent=2,
            )
        )

    @classmethod
    def load(cls, model_dir: str | Path):
        model_dir = Path(model_dir)
        metadata = json.loads((model_dir / "metadata.json").read_text())
        classifier = cls(
            max_features=metadata["max_features"],
            confidence_threshold=metadata["confidence_threshold"],
            c=metadata.get("c", 1.0),
            class_weight=metadata.get("class_weight"),
            min_df=metadata.get("min_df", 1),
            sublinear_tf=metadata.get("sublinear_tf", False),
            cities=metadata.get("cities"),
        )
        classifier.model = joblib.load(model_dir / "classifier.joblib")
        return classifier

    def _require_model(self):
        if self.model is None:
            raise RuntimeError("Train or load the query intent classifier before predicting.")

    def _project_path(self, path):
        path = Path(path)
        if path.exists() or path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path

    def _load_city_list(self):
        if not self.city_list_path.exists():
            return []
        return json.loads(self.city_list_path.read_text()).get("cities", [])

    def _city_pattern(self):
        if not self.cities:
            return None
        terms = "|".join(re.escape(city) for city in self.cities)
        return re.compile(rf"\b(?:{terms})\b", flags=re.IGNORECASE)

    def _prepare_queries(self, queries):
        return [self._prepare_query(query) for query in queries]

    def _prepare_query(self, query):
        text = str(query)
        if self.city_pattern is not None:
            text = self.city_pattern.sub(" city ", text)
        return text
