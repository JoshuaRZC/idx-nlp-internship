from web.presentation import applied_filter_chips, format_price, format_property_facts


def test_applied_filter_chips_separate_hard_filters_and_preferences():
    hard, preferences = applied_filter_chips(
        {
            "hard_filters": {"city": "Irvine", "price_max": 900000, "beds_min": 3},
            "soft_signals": {"amenities": ["pool"], "condition_exclude": ["fixer upper"]},
        }
    )

    assert hard == ["Irvine", "Up to $900,000", "3+ bd"]
    assert preferences == ["pool", "Avoid: fixer upper"]


def test_listing_fact_formatting_uses_public_fields_only():
    result = {"price": 875000, "beds": 3, "baths": 2.5, "sqft": 1850}

    assert format_price(result["price"]) == "$875,000"
    assert format_property_facts(result) == "3 bd | 2.5 ba | 1,850 sqft"
