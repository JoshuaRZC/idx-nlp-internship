import pandas as pd

from scripts.evaluate_listing_summaries import evaluate_items
from scripts.generate_listing_summaries import build_summaries
from scripts.select_listing_summary_eval_sample import select_sample
from src.real_estate_nlp.answerability_checker import AnswerabilityChecker
from src.real_estate_nlp.listing_summarizer import ListingSummarizer


def signals(**buckets):
    names = (
        "amenities",
        "condition",
        "interior_features",
        "exterior_features",
        "location_features",
        "financing_terms",
        "transaction_features",
        "investment_features",
        "rooms",
        "property_type",
        "parking",
    )
    return {"text_signals": {name: buckets.get(name, []) for name in names}}


def listing(**overrides):
    record = {
        "listing_id": "A1",
        "city": "Irvine",
        "price": 950000,
        "beds": 3,
        "baths": 2.5,
        "remarks": "Bright home with a private pool. The kitchen has quartz countertops.",
    }
    record.update(overrides)
    return record


def test_hybrid_summary_uses_mls_facts_and_two_distinct_features():
    summary = ListingSummarizer().summarize(
        listing(),
        signals(amenities=["pool"], interior_features=["quartz countertops"]),
    )

    assert summary == (
        "This 3-bed, 2.5-bath listing in Irvine is listed at $950,000. "
        "Highlights include a pool and quartz countertops."
    )


def test_hybrid_summary_prefers_structured_values_over_conflicting_remarks():
    summary = ListingSummarizer().summarize(
        listing(remarks="This 4 bedroom home is offered for $800,000 with a pool."),
        signals(amenities=["pool"]),
    )

    assert "3-bed, 2.5-bath" in summary
    assert "$950,000" in summary
    assert "4-bed" not in summary
    assert "$800,000" not in summary


def test_feature_selection_favors_diversity_before_a_second_bucket_value():
    summary = ListingSummarizer().summarize(
        listing(),
        signals(amenities=["pool", "spa"], interior_features=["fireplace"]),
    )

    assert "pool" in summary
    assert "fireplace" in summary
    assert "spa" not in summary


def test_summary_formats_location_and_condition_signals_as_natural_phrases():
    summary = ListingSummarizer().summarize(
        listing(remarks=""),
        signals(location_features=["downtown"], condition=["well maintained"], parking=[2]),
    )

    assert summary.endswith("Highlights include a downtown location and a well-maintained home.")
    assert "a 2" not in summary


def test_extractive_summary_keeps_original_order_and_skips_boilerplate_when_possible():
    remarks = "First sentence mentions a pool. Call listing agent for details. Final sentence has a fireplace."

    summary = ListingSummarizer().extractive_summary(
        remarks,
        entities=[{"value": "pool"}, {"value": "fireplace"}],
    )

    assert summary == "First sentence mentions a pool. Final sentence has a fireplace."


def test_summary_handles_empty_listing_text_without_inventing_features():
    summary = ListingSummarizer().summarize(
        listing(city=None, price=None, beds=None, baths=None, remarks=""),
        signals(),
    )

    assert summary == "This listing."


def test_summary_treats_zero_beds_and_baths_as_missing_values():
    summary = ListingSummarizer().summarize(
        listing(city="Indio", price=239000, beds=0, baths=0, remarks=""),
        signals(),
    )

    assert summary == "This listing in Indio is listed at $239,000."


def test_batch_helper_returns_one_summary_per_listing():
    records = [listing(listing_id="A1"), listing(listing_id="A2", city="Pasadena")]
    output = build_summaries(records, {"A1": signals(amenities=["pool"]), "A2": signals()})

    assert [row["listing_id"] for row in output] == ["A1", "A2"]
    assert "pool" in output[0]["summary"]
    assert "Pasadena" in output[1]["summary"]


def test_sample_selection_produces_frozen_dev_and_test_splits():
    records = [listing(listing_id=str(index), remarks="A long listing remark. " * 20) for index in range(50)]
    signal_map = {str(index): signals(amenities=["pool"], interior_features=["fireplace"]) for index in range(50)}

    sample = select_sample(records, signal_map)

    assert len(sample) == 50
    assert sample["split"].value_counts().to_dict() == {"test": 30, "dev": 20}
    assert sample["listing_id"].is_unique


def test_evaluation_reports_rouge_and_fact_coverage():
    items = [
        {
            "id": "summary_1",
            "listing_id": "A1",
            "split": "test",
            "reference_summary": "This 3-bed home in Irvine is listed at $950,000. Highlights include a pool.",
            "facts": {"price": 950000, "beds": 3, "baths": None, "city": "Irvine"},
            "feature_gold": ["pool"],
        }
    ]
    summaries = {"A1": "This 3-bed home in Irvine is listed at $950,000. Highlights include a pool."}

    result = evaluate_items(items, summaries, "test")

    assert result["rouge_l"] == 1.0
    assert result["fact_coverage"] == 1.0
    assert result["rows"][0]["fact_checks"] == {
        "price": True,
        "beds": True,
        "city": True,
        "pool": True,
    }


class StubParser:
    def __init__(self, filters):
        self.filters = filters

    def parse(self, query):
        return {"filters": self.filters}


class StubValidator:
    def __init__(self, valid=True):
        self.valid = valid

    def validate_query(self, filters):
        return self.valid, [] if self.valid else ["price_max is outside the supported range"]


def test_answerability_checker_distinguishes_searches_and_unsupported_questions():
    checker = AnswerabilityChecker(StubParser({"city": "Irvine"}), StubValidator())
    assert checker.check_pre_query("show homes in Irvine") == (True, "Query is answerable.")

    checker = AnswerabilityChecker(StubParser({}), StubValidator())
    assert checker.check_pre_query("how do I bake bread") == (
        False,
        "This doesn't appear to be a real estate listing search.",
    )
    assert checker.check_pre_query("What does DOM mean?") == (
        False,
        "This is a real estate question, but it cannot be answered by the current listing search.",
    )


def test_answerability_checker_reports_invalid_and_empty_results():
    checker = AnswerabilityChecker(StubParser({"price_max": 1}), StubValidator(valid=False))
    assert checker.check_pre_query("homes under $1") == (
        False,
        "Query references invalid data: price_max is outside the supported range",
    )

    checker = AnswerabilityChecker(StubParser({}), StubValidator())
    assert checker.check_post_query(pd.DataFrame()) == (False, "No listings match your criteria.")
    assert checker.check_post_query(pd.DataFrame({"price": [None]})) == (
        False,
        "Query returned no meaningful listing data.",
    )
    assert checker.check_post_query(pd.DataFrame({"price": [950000]})) == (True, "Results found.")
