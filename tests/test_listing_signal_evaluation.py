from scripts.evaluate_listing_signals import evaluate_records, values_match


def prediction(listing_id, text_signals, numeric_signals, keywords=None):
    return {
        "listing_id": listing_id,
        "text_signals": text_signals,
        "numeric_signals": numeric_signals,
        "keywords": keywords or [],
    }


def label(listing_id, structured, fallback, text_signals):
    return {
        "listing_id": listing_id,
        "structured_numeric_gold": structured,
        "remark_numeric_gold": fallback,
        "text_signal_gold": text_signals,
    }


def test_numeric_values_match_after_normalization():
    assert values_match(2.0, 2)
    assert values_match("2.5", 2.5)
    assert not values_match(2, 3)


def test_evaluation_keeps_structured_fields_ahead_of_text_fallback():
    results = evaluate_records(
        [
            prediction(
                1,
                {"amenities": []},
                {"price": 900000, "beds": 3, "lot_size": 7200},
            )
        ],
        [
            label(
                1,
                {"price": 900000, "beds": 3},
                {"price": 950000, "lot_size": 7200},
                {"amenities": []},
            )
        ],
    )

    assert results["structured_fields"]["accuracy"] == 1.0
    assert results["remark_numeric_fallback"]["accuracy"] == 1.0
    assert "price" not in results["remark_numeric_fallback"]["per_field"]


def test_free_text_uses_bucket_and_value_for_matching():
    results = evaluate_records(
        [
            prediction(
                1,
                {"amenities": ["pool"], "condition": ["updated"]},
                {},
                ["pool", "updated"],
            )
        ],
        [
            label(
                1,
                {},
                {},
                {"amenities": ["pool"], "condition": ["remodeled"]},
            )
        ],
    )

    free_text = results["free_text"]
    assert free_text["true_positive"] == 1
    assert free_text["false_positive"] == 1
    assert free_text["false_negative"] == 1
    assert free_text["precision"] == 0.5
    assert free_text["recall"] == 0.5
    assert free_text["exact_set_accuracy"] == 0.0


def test_keyword_integrity_checks_the_flattened_text_signals():
    results = evaluate_records(
        [
            prediction(
                1,
                {"amenities": ["pool"], "parking": [2]},
                {},
                ["pool"],
            )
        ],
        [label(1, {}, {}, {"amenities": ["pool"], "parking": [2]})],
    )

    assert results["keyword_integrity"]["accuracy"] == 1.0
