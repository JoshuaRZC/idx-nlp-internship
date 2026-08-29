class AnswerabilityChecker:
    """Explain whether a request can be handled by the listing-search pipeline."""

    REAL_ESTATE_TERMS = {
        "bath",
        "bed",
        "cap rate",
        "closing costs",
        "comp",
        "condo",
        "dom",
        "escrow",
        "garage",
        "hoa",
        "home",
        "house",
        "listing",
        "price",
        "property",
        "pool",
        "real estate",
        "sqft",
        "square feet",
        "townhome",
    }

    SEARCH_TERMS = {
        "browse",
        "find",
        "homes in",
        "listings in",
        "search",
        "show",
    }

    def __init__(self, parser, schema_validator):
        self.parser = parser
        self.validator = schema_validator

    def check_pre_query(self, query, parsed=None):
        text = str(query or "").strip()
        if not text:
            return False, "Please enter a listing search request."

        parsed = parsed if parsed is not None else self.parser.parse(text)
        filters = parsed.get("filters", parsed) if isinstance(parsed, dict) else parsed
        has_listing_signal = bool(filters) or self._contains_any(text, self.SEARCH_TERMS)

        if not has_listing_signal:
            if self._contains_any(text, self.REAL_ESTATE_TERMS):
                return (
                    False,
                    "This is a real estate question, but it cannot be answered by the current listing search.",
                )
            return False, "This doesn't appear to be a real estate listing search."

        valid, errors = self.validator.validate_query(filters)
        if not valid:
            return False, f"Query references invalid data: {'; '.join(errors)}"

        return True, "Query is answerable."

    def check_post_query(self, results_df):
        if len(results_df) == 0:
            return False, "No listings match your criteria."
        if results_df.isnull().all().all():
            return False, "Query returned no meaningful listing data."
        return True, "Results found."

    @staticmethod
    def _contains_any(query, terms):
        text = query.lower()
        return any(term in text for term in terms)
