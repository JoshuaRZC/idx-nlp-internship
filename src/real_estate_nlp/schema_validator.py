from pathlib import Path

import pandas as pd

from src.real_estate_nlp.query_parser import QueryParser


class SchemaValidator:
    ALLOWED_FILTERS = {
        "city",
        "county",
        "price_min",
        "price_max",
        "beds",
        "beds_min",
        "beds_max",
        "beds_preferred",
        "baths",
        "baths_min",
        "baths_max",
        "sqft",
        "sqft_min",
        "sqft_max",
        "private_pool",
        "fireplace",
        "has_view",
        "property_type",
        "property_type_exclude",
        "amenities",
        "amenities_exclude",
        "interior_features",
        "interior_features_exclude",
        "exterior_features",
        "exterior_features_exclude",
        "location_features",
        "location_features_exclude",
        "condition",
        "condition_exclude",
        "transaction_features",
        "investment_features",
        "use_case",
        "style_preference",
        "price_preference",
        "size_preference",
        "summary_focus",
        "open_house_date",
        "open_house_time",
        "sort",
    }

    LIST_FILTERS = {
        "property_type",
        "property_type_exclude",
        "amenities",
        "amenities_exclude",
        "interior_features",
        "interior_features_exclude",
        "exterior_features",
        "exterior_features_exclude",
        "location_features",
        "location_features_exclude",
        "condition",
        "condition_exclude",
        "transaction_features",
        "investment_features",
        "use_case",
        "style_preference",
        "summary_focus",
    }

    PRICE_MIN = 50_000
    PRICE_MAX = 100_000_000
    COUNT_MIN = 0
    COUNT_MAX = 20
    SQFT_MIN = 100
    SQFT_MAX = 50_000

    def __init__(
        self,
        cities=None,
        city_list_path=QueryParser.DEFAULT_CITY_LIST_PATH,
        listing_sample_path=None,
    ):
        self.valid_cities = set(cities or QueryParser(city_list_path=city_list_path).cities)
        sample_path = Path(listing_sample_path) if listing_sample_path else None
        if sample_path and sample_path.exists():
            city_values = pd.read_csv(sample_path, usecols=["L_City"])["L_City"].dropna()
            self.valid_cities.update(city.strip() for city in city_values.astype(str) if city.strip())

    def validate_query(self, filters):
        if "filters" in filters:
            filters = filters["filters"]

        errors = []
        for key in filters:
            if key not in self.ALLOWED_FILTERS:
                errors.append(f"Unsupported filter: {key}")

        self._validate_city(filters, errors)
        self._validate_price(filters, errors)
        self._validate_counts(filters, errors)
        self._validate_sqft(filters, errors)
        self._validate_booleans(filters, errors)
        self._validate_list_fields(filters, errors)
        self._validate_ranges(filters, errors)

        return len(errors) == 0, errors

    def _validate_city(self, filters, errors):
        city = filters.get("city")
        if city and city not in self.valid_cities:
            errors.append(f"City '{city}' not found in known city list")

    def _validate_price(self, filters, errors):
        for key in ["price_min", "price_max"]:
            if key not in filters:
                continue
            value = filters[key]
            if not isinstance(value, int):
                errors.append(f"{key} must be an integer")
            elif value < self.PRICE_MIN or value > self.PRICE_MAX:
                errors.append(f"{key}={value} is outside the supported range")

    def _validate_counts(self, filters, errors):
        for key in ["beds", "beds_min", "beds_max", "beds_preferred", "baths", "baths_min", "baths_max"]:
            if key not in filters:
                continue
            value = filters[key]
            if not isinstance(value, (int, float)):
                errors.append(f"{key} must be numeric")
            elif value < self.COUNT_MIN or value > self.COUNT_MAX:
                errors.append(f"{key}={value} is outside the supported range")

    def _validate_sqft(self, filters, errors):
        for key in ["sqft", "sqft_min", "sqft_max"]:
            if key not in filters:
                continue
            value = filters[key]
            if not isinstance(value, int):
                errors.append(f"{key} must be an integer")
            elif value < self.SQFT_MIN or value > self.SQFT_MAX:
                errors.append(f"{key}={value} is outside the supported range")

    def _validate_booleans(self, filters, errors):
        for key in ["private_pool", "fireplace", "has_view"]:
            if key in filters and not isinstance(filters[key], bool):
                errors.append(f"{key} must be boolean")

    def _validate_list_fields(self, filters, errors):
        for key in self.LIST_FILTERS:
            if key in filters and not isinstance(filters[key], list):
                errors.append(f"{key} must be a list")

    def _validate_ranges(self, filters, errors):
        if filters.get("price_min") and filters.get("price_max"):
            if filters["price_min"] > filters["price_max"]:
                errors.append("price_min cannot be greater than price_max")
        if filters.get("beds_min") and filters.get("beds_max"):
            if filters["beds_min"] > filters["beds_max"]:
                errors.append("beds_min cannot be greater than beds_max")
        if filters.get("baths_min") and filters.get("baths_max"):
            if filters["baths_min"] > filters["baths_max"]:
                errors.append("baths_min cannot be greater than baths_max")
        if filters.get("sqft_min") and filters.get("sqft_max"):
            if filters["sqft_min"] > filters["sqft_max"]:
                errors.append("sqft_min cannot be greater than sqft_max")
