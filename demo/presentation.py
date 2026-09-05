"""Formatting helpers for the Streamlit search experience."""

from __future__ import annotations


HARD_FILTER_LABELS = {
    "city": "City",
    "price_min": "Minimum price",
    "price_max": "Maximum price",
    "beds": "Bedrooms",
    "beds_min": "Bedrooms",
    "beds_max": "Bedrooms",
    "baths": "Bathrooms",
    "baths_min": "Bathrooms",
    "baths_max": "Bathrooms",
    "sqft": "Square feet",
    "sqft_min": "Minimum square feet",
    "sqft_max": "Maximum square feet",
}


def applied_filter_chips(parsed_query):
    hard_filters = parsed_query.get("hard_filters") or {}
    soft_signals = parsed_query.get("soft_signals") or {}

    hard = [
        _hard_filter_label(key, value)
        for key, value in hard_filters.items()
        if key in HARD_FILTER_LABELS
    ]
    preferences = [
        _preference_label(key, value)
        for key, value in soft_signals.items()
        if value
    ]
    return hard, preferences


def format_price(value):
    if value is None:
        return "Price unavailable"
    return f"${float(value):,.0f}"


def format_property_facts(result):
    facts = []
    if result.get("beds") is not None:
        facts.append(f"{result['beds']:g} bd")
    if result.get("baths") is not None:
        facts.append(f"{result['baths']:g} ba")
    if result.get("sqft") is not None:
        facts.append(f"{result['sqft']:,.0f} sqft")
    return " | ".join(facts) or "Details unavailable"


def feature_labels(result):
    return [match.get("value", "").replace("_", " ").title() for match in result.get("matched_signals", [])]


def compact_listing_label(result):
    address = result.get("address") or "Address unavailable"
    city = result.get("city") or ""
    return f"{address}, {city}".rstrip(", ")


def _hard_filter_label(key, value):
    if key == "price_max":
        return f"Up to {format_price(value)}"
    if key == "price_min":
        return f"From {format_price(value)}"
    if key in {"beds_min", "baths_min", "sqft_min"}:
        suffix = " bd" if key.startswith("beds") else " ba" if key.startswith("baths") else " sqft"
        return f"{value:g}+{suffix}"
    if key in {"beds_max", "baths_max", "sqft_max"}:
        suffix = " bd" if key.startswith("beds") else " ba" if key.startswith("baths") else " sqft"
        return f"Up to {value:g}{suffix}"
    if key == "sqft":
        return f"{value:,.0f} sqft"
    if key in {"beds", "baths"}:
        suffix = " bd" if key == "beds" else " ba"
        return f"{value:g}{suffix}"
    return str(value)


def _preference_label(key, value):
    values = value if isinstance(value, list) else [value]
    text = ", ".join(str(item).replace("_", " ") for item in values)
    if key.endswith("_exclude"):
        return f"Avoid: {text}"
    return text
