import json
from collections import Counter, defaultdict

from scripts.evaluate_query_intent_classifier import evaluate_items
from src.real_estate_nlp.query_intent_classifier import QueryIntentClassifier
from src.real_estate_nlp.query_parser import QueryParser


def load_labels():
    with open("data/processed/query_intent_labels.json") as f:
        return json.load(f)["items"]


def training_examples():
    rows = {
        "browsing": [
            "show homes in irvine",
            "homes with a pool",
            "condos in pasadena",
            "three bedroom houses",
            "listings under 900k",
            "townhomes with a patio",
            "homes near parks",
            "updated homes in corona",
            "houses with a garage",
            "places in long beach",
        ],
        "researching": [
            "which city has lower property taxes",
            "compare condos and townhomes",
            "what should I know before buying",
            "how much are typical hoa fees",
            "is a pool worth the maintenance",
            "what areas have shorter commutes",
            "how do I estimate closing costs",
            "when is the best time to buy",
            "what makes a good rental property",
            "how should I compare two listings",
        ],
        "high_intent_inquiry": [
            "schedule a tour in irvine",
            "open houses this weekend",
            "I need to move next month",
            "help me make an offer",
            "contact an agent today",
            "find homes available now",
            "book a viewing tomorrow",
            "show new listings this week",
            "I am ready to buy a home",
            "help me close quickly",
        ],
    }
    queries = []
    labels = []
    for label, values in rows.items():
        queries.extend(values)
        labels.extend([label] * len(values))
    return queries, labels


def test_query_intent_dataset_is_balanced_and_split_by_family():
    items = load_labels()

    assert len(items) == 504
    assert Counter(item["label"] for item in items) == {
        "browsing": 168,
        "researching": 168,
        "high_intent_inquiry": 168,
    }
    assert Counter(item["split"] for item in items) == {
        "train": 360,
        "dev": 72,
        "test": 72,
    }
    assert len({item["id"] for item in items}) == len(items)

    family_splits = defaultdict(set)
    for item in items:
        family_splits[item["template_family"]].add(item["split"])
    assert all(len(splits) == 1 for splits in family_splits.values())


def test_classifier_replaces_city_names_before_vectorization():
    classifier = QueryIntentClassifier(cities=["Irvine", "Newport Beach"])

    prepared = classifier._prepare_query("homes in Newport Beach and Irvine")

    assert "newport" not in prepared.lower()
    assert "irvine" not in prepared.lower()
    assert prepared.lower().count("city") == 2


def test_classifier_returns_a_calibrated_intent_envelope():
    queries, labels = training_examples()
    classifier = QueryIntentClassifier().fit(queries, labels)

    result = classifier.predict("can I schedule a showing tomorrow")

    assert result["label"] in QueryIntentClassifier.LABELS
    assert 0 <= result["confidence"] <= 1
    assert result["is_uncertain"] is (result["confidence"] < 0.60)


def test_classifier_save_and_load_preserves_predictions(tmp_path):
    queries, labels = training_examples()
    classifier = QueryIntentClassifier().fit(queries, labels)
    expected = classifier.predict("what should I know before buying a condo")
    classifier.save(tmp_path)

    restored = QueryIntentClassifier.load(tmp_path)

    assert restored.predict("what should I know before buying a condo") == expected


def test_query_parser_keeps_existing_output_without_classifier():
    result = QueryParser(cities=["Irvine"]).parse("homes in Irvine under 900k")

    assert "language_intent" not in result
    assert result["hard_filters"] == {"city": "Irvine", "price_max": 900_000}


def test_query_parser_adds_language_intent_only_when_configured():
    class StubClassifier:
        def predict(self, query):
            return {"label": "browsing", "confidence": 0.81, "is_uncertain": False}

    parser = QueryParser(cities=["Irvine"], intent_classifier=StubClassifier())

    result = parser.parse("homes in Irvine under 900k")

    assert result["language_intent"] == {
        "label": "browsing",
        "confidence": 0.81,
        "is_uncertain": False,
    }
    assert parser.parse("homes in Irvine", flat=True) == {"city": "Irvine"}


def test_evaluation_reports_metrics_and_errors():
    class StubClassifier:
        def predict_many(self, queries):
            return [
                {"label": "browsing", "confidence": 0.80, "is_uncertain": False},
                {"label": "researching", "confidence": 0.55, "is_uncertain": True},
            ]

    items = [
        {"id": "intent_a", "query": "show homes in Irvine", "label": "browsing"},
        {"id": "intent_b", "query": "what are typical HOA fees", "label": "high_intent_inquiry"},
    ]

    results = evaluate_items(items, StubClassifier())

    assert results["queries_evaluated"] == 2
    assert results["accuracy"] == 0.5
    assert results["confidence"]["uncertain_count"] == 1
    assert results["errors"][0]["id"] == "intent_b"
