import json
import re
from pathlib import Path


class QueryParser:
    DEFAULT_TAXONOMY_PATH = "data/processed/taxonomy.json"
    DEFAULT_CITY_LIST_PATH = "data/processed/valid_cities.json"

    MONEY_PATTERN = r"\$?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|m|million|millions)?"
    SQFT_PATTERN = r"\d{3,6}(?:,\d{3})?"

    NUMBER_WORDS = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    KNOWN_CITIES = [
        "Anaheim",
        "Chino Hills",
        "Corona",
        "Irvine",
        "Long Beach",
        "Los Angeles",
        "Newport Beach",
        "Palm Springs",
        "Pasadena",
        "Riverside",
        "San Diego",
        "Santa Monica",
        "Torrance",
    ]

    COUNTY_ALIASES = {
        "orange county": "Orange",
        "los angeles county": "Los Angeles",
        "riverside county": "Riverside",
        "san diego county": "San Diego",
    }

    PHRASE_RULES = [
        ("not a fixer", "condition_exclude", "fixer upper"),
        ("not fixer", "condition_exclude", "fixer upper"),
        ("not a full teardown", "condition_exclude", "teardown"),
        ("no major repairs", "condition_exclude", "major repairs"),
        ("do not want a project", "condition_exclude", ["project", "fixer upper"]),
        ("don't want a project", "condition_exclude", ["project", "fixer upper"]),
        ("not interested in condos", "property_type_exclude", "condo"),
        ("not tiny condos", "property_type_exclude", "condo"),
        ("not tiny", "size_preference", "not tiny"),
        ("not just community pool", "amenities_exclude", "community pool"),
        ("not on a busy street", "location_features_exclude", "busy street"),
        ("not just a tiny patio", "exterior_features_exclude", "tiny patio"),
        ("not just steep hillside", "exterior_features_exclude", "steep hillside"),
        ("steep hillside", "exterior_features_exclude", "steep hillside"),
        ("new construction", "condition", "new construction"),
        ("brand new", "condition", "new construction"),
        ("move-in ready", "condition", "move-in ready"),
        ("move in ready", "condition", "move-in ready"),
        ("clean and ready", "condition", "move-in ready"),
        ("turnkey", "condition", "turnkey"),
        ("updated kitchen and bathrooms", "condition", "updated"),
        ("updated kitchen and bathrooms", "interior_features", ["updated kitchen", "updated bathrooms"]),
        ("remodeled kitchen", "interior_features", "remodeled kitchen"),
        ("updated kitchen", "interior_features", "updated kitchen"),
        ("updated bathrooms", "interior_features", "updated bathrooms"),
        ("updated bathroom", "interior_features", "updated bathroom"),
        ("tastefully renovated", "condition", "renovated"),
        ("renovated", "condition", "renovated"),
        ("remodeled", "condition", "remodeled"),
        ("fixer upper", "condition", "fixer upper"),
        ("fixer", "condition", "fixer upper"),
        ("cosmetic upside", "condition", "cosmetic upside"),
        ("needs renovation", "condition", "needs renovation"),
        ("modern", "condition", "modern"),
        ("reasonable", "price_preference", "reasonable"),
        ("older homes", "style_preference", "older home"),
        ("older home", "style_preference", "older home"),
        ("single family residence", "property_type", "single family"),
        ("single family home", "property_type", "single family"),
        ("single family homes", "property_type", "single family"),
        ("single family", "property_type", "single family"),
        ("detached homes", "property_type", "detached home"),
        ("detached home", "property_type", "detached home"),
        ("townhomes", "property_type", "townhouse"),
        ("townhome", "property_type", "townhouse"),
        ("townhouses", "property_type", "townhouse"),
        ("townhouse", "property_type", "townhouse"),
        ("condominiums", "property_type", "condo"),
        ("condos", "property_type", "condo"),
        ("condo", "property_type", "condo"),
        ("duplexes", "property_type", "duplex"),
        ("duplex", "property_type", "duplex"),
        ("multi-family", "property_type", "multi-family"),
        ("multi family", "property_type", "multi-family"),
        ("multi-unit", "property_type", "multi-family"),
        ("single story", "property_type", "single story"),
        ("houses", "property_type", "house"),
        ("house", "property_type", "house"),
        ("home office", "room", "home office"),
        ("primary suite", "room", "primary suite"),
        ("primary bedroom", "room", "primary bedroom"),
        ("primary bed", "room", "primary bedroom"),
        ("downstairs bedroom", "room", "downstairs bedroom"),
        ("guest room", "room", "guest room"),
        ("separate bedrooms", "room", "separate bedrooms"),
        ("pool and spa", "amenities", ["pool", "spa"]),
        ("community with pool", "amenities", "community pool"),
        ("community pool", "amenities", "community pool"),
        ("private pool", "amenities", "private pool"),
        ("swimming pool", "amenities", "pool"),
        ("pool", "amenities", "pool"),
        ("spa", "amenities", "spa"),
        ("garage plus driveway", "amenities", ["garage", "driveway"]),
        ("attached garage", "amenities", "attached garage"),
        ("garage", "amenities", "garage"),
        ("space for an ev charger", "amenities", ["ev charger", "garage"]),
        ("driveway", "amenities", "driveway"),
        ("multiple cars", "amenities", "multiple parking spaces"),
        ("multiple parking spaces", "amenities", "multiple parking spaces"),
        ("rv parking", "amenities", "rv parking"),
        ("fireplace", "amenities", "fireplace"),
        ("central air", "amenities", "central air"),
        ("solar panels", "amenities", "solar panels"),
        ("ev charger", "amenities", "ev charger"),
        ("charging", "amenities", "ev charger"),
        ("gym", "amenities", "gym"),
        ("clubhouse", "amenities", "clubhouse"),
        ("tennis courts", "amenities", "tennis court"),
        ("tennis court", "amenities", "tennis court"),
        ("outdoor entertaining", "amenities", "outdoor entertaining"),
        ("outdoor entertainment", "amenities", "outdoor entertaining"),
        ("hardwood floors", "interior_features", "hardwood floors"),
        ("open floor plan", "interior_features", "open floor plan"),
        ("open floorplan", "interior_features", "open floor plan"),
        ("does not feel chopped up", "interior_features", "open floor plan"),
        ("living areas flow together", "interior_features", ["kitchen dining living flow", "open floor plan"]),
        ("flow together", "interior_features", "kitchen dining living flow"),
        ("quartz countertops", "interior_features", "quartz countertops"),
        ("stainless steel appliances", "interior_features", "stainless steel appliances"),
        ("walk-in closet", "interior_features", "walk-in closet"),
        ("walk in closet", "interior_features", "walk-in closet"),
        ("high ceilings", "interior_features", "high ceilings"),
        ("natural light", "interior_features", "natural light"),
        ("bright home", "interior_features", "natural light"),
        ("kitchen island", "interior_features", "kitchen island"),
        ("newer finishes", "interior_features", "newer finishes"),
        ("some character", "style_preference", "character"),
        ("backyard", "exterior_features", "backyard"),
        ("balcony", "exterior_features", "balcony"),
        ("covered patio", "exterior_features", "covered patio"),
        ("patio", "exterior_features", "patio"),
        ("large lot", "exterior_features", "large lot"),
        ("landscaped yard", "exterior_features", "landscaped yard"),
        ("private backyard", "exterior_features", "private backyard"),
        ("room to add a pool", "exterior_features", "room for pool"),
        ("outdoor space that works for kids", "exterior_features", ["backyard", "outdoor entertaining"]),
        ("outdoor space", "exterior_features", "outdoor entertaining"),
        ("weekend bbq", "exterior_features", "outdoor entertaining"),
        ("weekend BBQs", "exterior_features", "outdoor entertaining"),
        ("privacy outside", "exterior_features", "private outdoor space"),
        ("usable land", "exterior_features", "usable land"),
        ("ocean views", "location_features", "ocean view"),
        ("ocean view", "location_features", "ocean view"),
        ("mountain views", "location_features", "mountain view"),
        ("mountain view", "location_features", "mountain view"),
        ("city lights view", "location_features", "city lights view"),
        ("canyon view", "location_features", "canyon view"),
        ("canyon or ocean views", "location_features", ["canyon view", "ocean view"]),
        ("near the beach", "location_features", "near beach"),
        ("near beach", "location_features", "near beach"),
        ("near the coast", "location_features", "near coast"),
        ("not too far from the freeway", "location_features", "near freeway"),
        ("coastal", "location_features", "coastal"),
        ("cul de sac", "location_features", "cul de sac"),
        ("close to schools", "location_features", "near schools"),
        ("near schools", "location_features", "near schools"),
        ("close to restaurants", "location_features", "near restaurants"),
        ("restaurants", "location_features", "near restaurants"),
        ("close to shopping", "location_features", "near shopping"),
        ("near shopping", "location_features", "near shopping"),
        ("good shopping", "location_features", "near shopping"),
        ("shopping", "location_features", "near shopping"),
        ("parks", "location_features", "near parks"),
        ("quiet", "location_features", "quiet location"),
        ("private", "location_features", "private"),
        ("walkability", "location_features", "walkable"),
        ("walkable", "location_features", "walkable"),
        ("freeway", "location_features", "near freeway"),
        ("low hoa", "transaction_features", "low hoa"),
        ("low homeowners association", "transaction_features", "low hoa"),
        ("low maintenance", "transaction_features", "low maintenance"),
        ("adu potential", "investment_features", "adu potential"),
        ("rental income", "investment_features", "rental income"),
        ("tenant occupied", "investment_features", "tenant occupied"),
        ("tenants", "investment_features", "tenant occupied"),
        ("guest house", "investment_features", "guest house"),
        ("separate entrance", "investment_features", "separate entrance"),
        ("add value", "investment_features", "value add"),
        ("value add", "investment_features", "value add"),
        ("renovations", "condition", "needs renovation"),
        ("house hack", "investment_features", "house hack"),
        ("rentable unit", "investment_features", "rentable unit"),
        ("short term rental", "investment_features", "short term rental"),
        ("upside", "investment_features", "upside"),
        ("main house", "investment_features", "main house"),
        ("adu", "investment_features", "adu"),
        ("rental flexibility", "investment_features", "rental flexibility"),
        ("live in one and rent the other", "property_type", ["duplex", "multi-family"]),
        ("live in one and rent the other", "investment_features", ["owner occupy", "rental income"]),
        ("works like a single family home but with less yard maintenance", "property_type", ["townhouse", "condo"]),
        ("less yard maintenance", "use_case", "low maintenance"),
        ("enough rooms for kids", "use_case", "family"),
        ("family-friendly", "use_case", "family"),
        ("family friendly", "use_case", "family"),
        ("family buyer", "use_case", "family"),
        ("kids", "use_case", "kids"),
        ("dogs", "use_case", "pets"),
        ("pets", "use_case", "pets"),
        ("entertaining", "use_case", "entertaining"),
        ("bbqs", "use_case", "barbecue"),
        ("barbecue", "use_case", "barbecue"),
        ("bbq", "use_case", "barbecue"),
        ("multi-generational", "use_case", "multi-generational"),
        ("parents can stay downstairs", "room", "downstairs bedroom"),
        ("parents can stay downstairs", "use_case", "multi-generational"),
    ]

    SQL_FIELDS = {
        "city": ("L_City", "="),
        "price_min": ("L_SystemPrice", ">="),
        "price_max": ("L_SystemPrice", "<="),
        "beds": ("L_Keyword2", "="),
        "beds_min": ("L_Keyword2", ">="),
        "beds_max": ("L_Keyword2", "<="),
        "baths": ("LM_Dec_3", "="),
        "baths_min": ("LM_Dec_3", ">="),
        "baths_max": ("LM_Dec_3", "<="),
        "sqft": ("LM_Int2_3", "="),
        "sqft_min": ("LM_Int2_3", ">="),
        "sqft_max": ("LM_Int2_3", "<="),
        "private_pool": ("PoolPrivateYN", "="),
        "fireplace": ("FireplaceYN", "="),
        "has_view": ("ViewYN", "="),
    }

    HARD_FILTER_FIELDS = set(SQL_FIELDS)
    SQL_CONTROL_FIELDS = {"sort"}

    TEXT_FILTER_FIELDS = [
        "property_type",
        "amenities",
        "interior_features",
        "exterior_features",
        "location_features",
        "condition",
        "transaction_features",
        "investment_features",
        "room",
    ]

    SCALAR_FILTERS = {
        "open_house_date",
        "open_house_time",
        "price_preference",
        "size_preference",
        "sort",
    }

    def __init__(
        self,
        taxonomy_path=DEFAULT_TAXONOMY_PATH,
        cities=None,
        city_list_path=DEFAULT_CITY_LIST_PATH,
    ):
        self.taxonomy_path = self._project_path(taxonomy_path)
        self.city_list_path = self._project_path(city_list_path)
        self.cities = sorted(cities or self._load_city_list() or self.KNOWN_CITIES, key=len, reverse=True)
        self.phrase_rules = self._build_phrase_rules()

    def _project_path(self, path):
        path = Path(path)
        if path.exists() or path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path

    def _load_city_list(self):
        if not self.city_list_path.exists():
            return []

        with self.city_list_path.open() as f:
            payload = json.load(f)
        return [city for city in payload.get("cities", []) if isinstance(city, str) and city.strip()]

    def _parse_filters(self, query):
        text = self._normalize_query(query)
        filters = {}

        self._merge(filters, self._parse_price(text))
        self._merge(filters, self._parse_beds_baths(text))
        self._merge(filters, self._parse_sqft(text))
        self._merge(filters, self._parse_location(text))
        self._merge(filters, self._parse_open_house(text))
        self._merge(filters, self._parse_sort(text))
        self._merge(filters, self._parse_summary_focus(text))
        self._merge(filters, self._parse_phrases(text))
        self._merge(filters, self._parse_structured_feature_flags(text))

        return self._deduplicate_filters(filters)

    def parse(self, query, flat=False):
        filters = self._parse_filters(query)
        if flat:
            return filters

        hard_filters, soft_signals = self.split_filters(filters)
        return {
            "intent": self._infer_intent(query, filters),
            "filters": filters,
            "hard_filters": hard_filters,
            "soft_signals": soft_signals,
        }

    def parse_query(self, query):
        return self.parse(query)

    def split_filters(self, filters):
        if "hard_filters" in filters and "soft_signals" in filters:
            return filters["hard_filters"], filters["soft_signals"]
        if "filters" in filters:
            filters = filters["filters"]

        hard_filters = {}
        soft_signals = {}
        for key, value in filters.items():
            if key in self.HARD_FILTER_FIELDS or key in self.SQL_CONTROL_FIELDS:
                hard_filters[key] = value
            else:
                soft_signals[key] = value

        return hard_filters, soft_signals

    def to_sql(self, filters, limit=None, include_soft_signals=False):
        if include_soft_signals:
            if "filters" in filters:
                filters = filters["filters"]
        else:
            filters, _ = self.split_filters(filters)

        conditions = []
        params = []

        for key, (column, operator) in self.SQL_FIELDS.items():
            if key not in filters:
                continue
            conditions.append(f"{column} {operator} %s")
            params.append(filters[key])

        for key in self.TEXT_FILTER_FIELDS:
            for value in filters.get(key, []):
                conditions.append("L_Remarks LIKE %s ESCAPE '\\\\'")
                params.append(self._like_param(value))

            exclude_key = f"{key}_exclude"
            for value in filters.get(exclude_key, []):
                conditions.append("L_Remarks NOT LIKE %s ESCAPE '\\\\'")
                params.append(self._like_param(value))

        sql = "SELECT * FROM rets_property"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if filters.get("sort") == "price_asc":
            sql += " ORDER BY L_SystemPrice ASC"
        elif filters.get("sort") == "price_desc":
            sql += " ORDER BY L_SystemPrice DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        return sql, params

    def _parse_price(self, text):
        filters = {}
        range_patterns = [
            rf"\bbetween\s+({self.MONEY_PATTERN})\s+and\s+({self.MONEY_PATTERN})",
            rf"\bfrom\s+({self.MONEY_PATTERN})\s+to\s+({self.MONEY_PATTERN})",
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text)
            if match:
                filters["price_min"] = self._parse_money(match.group(1))
                filters["price_max"] = self._parse_money(match.group(2))
                return filters

        max_pattern = rf"\b(?:under|below|less than|no more than|up to|for less than|still under)\s+({self.MONEY_PATTERN})"
        if match := re.search(max_pattern, text):
            filters["price_max"] = self._parse_money(match.group(1))

        min_pattern = rf"\b(?:over|above|more than|at least|minimum|min|from)\s+({self.MONEY_PATTERN})"
        if match := re.search(min_pattern, text):
            value = self._parse_money(match.group(1))
            if value >= 50_000:
                filters["price_min"] = value

        around_pattern = rf"\b(?:around|about|near)\s+({self.MONEY_PATTERN})"
        if match := re.search(around_pattern, text):
            value = self._parse_money(match.group(1))
            if value >= 50_000 and "price_max" not in filters:
                filters["price_max"] = value

        return filters

    def _parse_beds_baths(self, text):
        filters = {}
        bed_pattern = r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\+?\s*(?:bedroom|bedrooms|beds?|br|bd)\b"
        bath_pattern = r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\+?\s*(?:bathroom|bathrooms|baths?|ba)\b"

        if match := re.search(r"\b(?:at least|minimum|min|more than|over)\s+" + bed_pattern, text):
            filters["beds_min"] = self._parse_count(match.group(1))
        elif match := re.search(r"\bexactly\s+" + bed_pattern, text):
            filters["beds"] = self._parse_count(match.group(1))
        elif match := re.search(bed_pattern, text):
            key = "beds_min" if "+" in match.group(0) else "beds_min"
            filters[key] = self._parse_count(match.group(1))

        if match := re.search(r"\bpreferably\s+(\d+)\b", text):
            filters["beds_preferred"] = int(match.group(1))

        if match := re.search(r"\b(?:at least|minimum|min|more than|over)\s+" + bath_pattern, text):
            filters["baths_min"] = self._parse_count(match.group(1))
        elif match := re.search(r"\bexactly\s+" + bath_pattern, text):
            filters["baths"] = self._parse_count(match.group(1))
        elif match := re.search(r"\btwo\s+full\s+baths?\b", text):
            filters["baths_min"] = 2
        elif match := re.search(bath_pattern, text):
            filters["baths_min"] = self._parse_count(match.group(1))

        return filters

    def _parse_sqft(self, text):
        filters = {}
        unit = r"(?:square feet|square foot|sq\.?\s*ft\.?|sqft|sf)"

        range_patterns = [
            rf"\bbetween\s+({self.SQFT_PATTERN})\s+and\s+({self.SQFT_PATTERN})\s+{unit}\b",
            rf"\bfrom\s+({self.SQFT_PATTERN})\s+to\s+({self.SQFT_PATTERN})\s+{unit}\b",
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text)
            if match:
                filters["sqft_min"] = self._parse_int(match.group(1))
                filters["sqft_max"] = self._parse_int(match.group(2))
                return filters

        min_pattern = rf"\b(?:at least|minimum|min|over|above|more than)\s+({self.SQFT_PATTERN})\s+{unit}\b"
        if match := re.search(min_pattern, text):
            filters["sqft_min"] = self._parse_int(match.group(1))

        max_pattern = rf"\b(?:under|below|less than|up to|no more than)\s+({self.SQFT_PATTERN})\s+{unit}\b"
        if match := re.search(max_pattern, text):
            filters["sqft_max"] = self._parse_int(match.group(1))

        plus_pattern = rf"\b({self.SQFT_PATTERN})\+?\s+{unit}\b"
        if not filters and (match := re.search(plus_pattern, text)):
            key = "sqft_min" if "+" in match.group(0) else "sqft"
            filters[key] = self._parse_int(match.group(1))

        return filters

    def _parse_structured_feature_flags(self, text):
        filters = {}

        if self._has_private_pool_filter(text):
            filters["private_pool"] = True
        if self._contains_phrase(text, "fireplace"):
            filters["fireplace"] = True
        if re.search(r"\b(?:ocean|mountain|city lights?|canyon|water|lake|golf course)?\s*views?\b", text):
            filters["has_view"] = True

        return filters

    def _parse_location(self, text):
        filters = {}
        county_spans = []
        for phrase, county in self.COUNTY_ALIASES.items():
            for match in re.finditer(self._phrase_pattern(phrase), text):
                filters["county"] = county
                county_spans.append(match.span())

        for city in self.cities:
            for match in re.finditer(self._phrase_pattern(city.lower()), text):
                if self._overlaps_any(match.span(), county_spans):
                    continue
                filters["city"] = city
                return filters

        return filters

    def _parse_open_house(self, text):
        if "open house" not in text and "open houses" not in text and "open this weekend" not in text:
            return {}

        filters = {}
        for phrase in ["this weekend", "today", "tomorrow", "sunday", "saturday"]:
            if self._contains_phrase(text, phrase):
                filters["open_house_date"] = phrase.title() if phrase in {"sunday", "saturday"} else phrase
                break

        if "after lunch" in text:
            filters["open_house_time"] = "after lunch"

        return filters

    def _parse_sort(self, text):
        if "cheapest" in text or "lowest price" in text:
            return {"sort": "price_asc"}
        if "most expensive" in text or "highest price" in text:
            return {"sort": "price_desc"}
        return {}

    def _parse_summary_focus(self, text):
        rules = [
            ("short buyer summary", "buyer summary"),
            ("main selling points", "selling points"),
            ("selling points", "selling points"),
            ("summarize the amenities", "amenities"),
            ("pros and possible concerns", "pros"),
            ("pros and possible concerns", "concerns"),
            ("search result card", "search result card"),
            ("family buyer", "family buyer fit"),
            ("lifestyle features", "lifestyle features"),
            ("comparing", "comparison"),
            ("neutral summary", "neutral summary"),
            ("without sounding too salesy", "neutral"),
            ("strongest lifestyle features", "concise"),
            ("compliance", "compliance-safe wording"),
        ]
        filters = {}
        for phrase, value in rules:
            if self._contains_phrase(text, phrase):
                field = "style_preference" if value in {"concise", "neutral"} else "summary_focus"
                self._add(filters, field, value)
        if "summary_focus" not in filters and self._contains_phrase(text, "summarize"):
            self._add(filters, "summary_focus", "general")
        return filters

    def _parse_phrases(self, text):
        matches = []
        spans = []
        protected_spans = self._protected_location_spans(text)
        for phrase, field, value in self.phrase_rules:
            for match in re.finditer(self._phrase_pattern(phrase), text):
                if self._skip_phrase_match(text, match, field, value, protected_spans):
                    continue
                target_field = self._negated_field(text, match.start(), field)
                if self._overlaps(match.span(), spans, target_field):
                    continue
                matches.append((match.start(), target_field, value))
                spans.append((match.span(), target_field))

        filters = {}
        for _, field, value in sorted(matches):
            self._add(filters, field, value)
        return filters

    def _build_phrase_rules(self):
        rules = list(self.PHRASE_RULES)
        rules.extend(self._load_taxonomy_rules())
        rules.sort(key=lambda item: len(item[0]), reverse=True)
        return rules

    def _load_taxonomy_rules(self):
        if not self.taxonomy_path.exists():
            return []

        field_by_category = {
            "property_type": "property_type",
            "room": "room",
            "amenity": "amenities",
            "interior_feature": "interior_features",
            "exterior_feature": "exterior_features",
            "location": "location_features",
            "condition": "condition",
            "transaction_or_listing": "transaction_features",
        }
        blocked = {
            "home",
            "homes",
            "property",
            "properties",
            "listing",
            "listings",
            "kitchen",
            "bedroom",
            "bathroom",
            "modern",
            "private",
            "view",
            "views",
        }

        with self.taxonomy_path.open() as f:
            taxonomy = json.load(f)

        rules = []
        for item in taxonomy.get("terms", []):
            term = str(item.get("term", "")).strip().lower()
            field = field_by_category.get(item.get("category"))
            if not field or term in blocked or len(term) < 4:
                continue
            rules.append((term, field, term))
            for alias in item.get("aliases", []):
                alias = str(alias).strip().lower()
                if alias and alias not in blocked and len(alias) >= 4:
                    rules.append((alias, field, term))
        return rules

    def _infer_intent(self, query, filters):
        text = self._normalize_query(query)
        if "summary_focus" in filters:
            return "summary_request"
        if "open house" in text or "open houses" in text:
            return "open_house_search"
        if "investment_features" in filters:
            return "investment_search"
        if "condition" in filters or "condition_exclude" in filters:
            return "condition_search"
        if "amenities" in filters or "amenities_exclude" in filters:
            return "amenity_search"
        if "interior_features" in filters:
            return "interior_feature_search"
        if "exterior_features" in filters or "exterior_features_exclude" in filters:
            return "exterior_feature_search"
        if "location_features" in filters or "city" in filters or "county" in filters:
            return "location_search"
        if {"beds_min", "baths_min", "beds", "baths"} & filters.keys():
            return "bed_bath_filter"
        if {"price_min", "price_max"} & filters.keys():
            return "price_filter"
        return "property_search"

    def _negated_field(self, text, start, field):
        if field.endswith("_exclude"):
            return field

        window = text[max(0, start - 32):start]
        negations = list(
            re.finditer(
                r"\b(?:no|without|not|do not want|don't want|dont want|not interested in)\b",
                window,
            )
        )
        if negations:
            tail = window[negations[-1].end():]
            if re.search(r"\btoo\s+far\s+from\s+the\s+$", tail):
                return field
            if re.search(r"\b(?:show|only|but|instead|rather)\b", tail):
                return field
            return f"{field}_exclude"
        return field

    def _skip_phrase_match(self, text, match, field, value, protected_spans):
        before = text[max(0, match.start() - 24):match.start()]
        after = text[match.end():match.end() + 16]
        value_key = self._value_key(value)

        if field == "location_features" and self._overlaps_any(match.span(), protected_spans):
            return True
        if field == "property_type" and value == "house" and before.endswith("open "):
            return True
        if field == "property_type" and value_key == "house":
            return not re.search(r"\bhouses?\s+in\b|\bshow me houses?\b", text)
        if field == "property_type" and value_key in {"guest house", "main house"}:
            return True
        if field == "exterior_features" and value_key in {
            "driveway",
            "garage",
            "parking",
            "rv parking",
            "solar",
            "solar panels",
            "attached garage",
        }:
            return True
        if field == "exterior_features" and value_key == "yard":
            return "maintenance" in after
        if field == "interior_features" and value_key == "fireplace":
            return True
        if field == "condition" and value_key in {
            "remodeled kitchen",
            "updated kitchen",
            "updated bathroom",
            "updated bathrooms",
        }:
            return True
        if field == "condition" and value_key == "remodeled":
            return bool(re.match(r"\s+kitchen\b", after))
        if field == "room" and value_key == "updated kitchen":
            return True
        if field == "room" and value_key == "separate bedrooms":
            return self._contains_phrase(text, "parents can stay downstairs")
        if field == "location_features" and value_key == "private":
            return bool(re.match(r"\s+(?:backyard|pool|yard|patio|driveway)\b", after))
        if field == "amenities" and value_key == "pool":
            return bool(re.search(r"\badd\s+a\s+$", before))
        if field == "investment_features" and value_key == "upside":
            return "cosmetic " in before
        if field == "transaction_features" and value_key in {"rental", "rental income"}:
            return True
        if field == "use_case" and value_key == "entertaining":
            return "outdoor " in before
        if field == "use_case" and value_key == "family":
            return "buyer" in match.group(0) or bool(re.match(r"\s+buyer\b", after))
        if field == "use_case" and value_key == "kids":
            return self._contains_phrase(text, "parents can stay downstairs")
        return False

    def _protected_location_spans(self, text):
        phrases = [city.lower() for city in self.cities]
        phrases.extend(self.COUNTY_ALIASES)

        spans = []
        for phrase in phrases:
            spans.extend(match.span() for match in re.finditer(self._phrase_pattern(phrase), text))
        return spans

    def _value_key(self, value):
        if isinstance(value, list):
            return "|".join(str(item).lower() for item in value)
        return str(value).lower()

    def _parse_money(self, text):
        match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|million|millions)?", text)
        value = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            value *= 1_000
        elif suffix in {"m", "million", "millions"}:
            value *= 1_000_000
        return int(value)

    def _parse_count(self, value):
        value = value.lower()
        if value in self.NUMBER_WORDS:
            return self.NUMBER_WORDS[value]
        count = float(value)
        return int(count) if count.is_integer() else count

    def _parse_int(self, value):
        return int(str(value).replace(",", ""))

    def _has_private_pool_filter(self, text):
        if self._contains_phrase(text, "private pool"):
            return True
        if re.search(r"\b(?:with|has|have|having)\s+(?:a\s+)?pool\b", text):
            return not re.search(r"\bcommunity\s+(?:with\s+)?pool\b|\bcommunity pool\b", text)
        if self._contains_phrase(text, "pool and spa"):
            return not self._contains_phrase(text, "community pool")
        return False

    def _normalize_query(self, query):
        text = "" if query is None else str(query)
        text = text.replace("’", "'").replace("“", '"').replace("”", '"')
        text = text.replace("&", " and ")
        text = re.sub(r"[/,]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    def _add(self, filters, key, value):
        if key in self.SCALAR_FILTERS:
            filters[key] = value
            return

        if isinstance(value, list):
            filters.setdefault(key, []).extend(value)
        else:
            filters.setdefault(key, []).append(value)

    def _merge(self, filters, updates):
        for key, value in updates.items():
            if isinstance(value, list):
                filters.setdefault(key, []).extend(value)
            else:
                filters[key] = value

    def _deduplicate_filters(self, filters):
        clean = {}
        for key, value in filters.items():
            if not isinstance(value, list):
                clean[key] = value
                continue

            seen = set()
            values = []
            for item in value:
                marker = str(item).lower()
                if marker in seen:
                    continue
                seen.add(marker)
                values.append(item)
            if values:
                clean[key] = values
        return clean

    def _contains_phrase(self, text, phrase):
        return re.search(self._phrase_pattern(phrase), text) is not None

    def _phrase_pattern(self, phrase):
        escaped = re.escape(phrase.lower()).replace(r"\ ", r"\s+")
        return rf"(?<!\w){escaped}(?!\w)"

    def _overlaps(self, span, spans, field):
        return any(
            existing_field == field and span[0] < existing[1] and existing[0] < span[1]
            for existing, existing_field in spans
        )

    def _overlaps_any(self, span, spans):
        return any(span[0] < existing[1] and existing[0] < span[1] for existing in spans)

    def _like_param(self, value):
        value = str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{value}%"
