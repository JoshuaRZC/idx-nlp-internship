import math
import re
from decimal import Decimal

from src.real_estate_nlp.entity_extractor import EntityExtractor
from src.real_estate_nlp.signal_schema import SIGNAL_BUCKETS, normalize_text_signals
from src.real_estate_nlp.text_cleaner import TextCleaner


class SignalExtractor:
    REMARK_FIELDS = ("remarks_cleaned", "remarks", "L_Remarks")

    FIELD_ALIASES = {
        "listing_id": ("listing_id", "L_ListingID"),
        "price": ("price", "L_SystemPrice"),
        "beds": ("beds", "L_Keyword2"),
        "baths": ("baths", "LM_Dec_3"),
        "sqft": ("sqft", "LM_Int2_3"),
    }

    NUMERIC_ENTITY_LABELS = {
        "price": "price",
        "bedrooms": "beds",
        "bathrooms": "baths",
        "sqft": "sqft",
        "lot_size": "lot_size",
        "year_built": "year_built",
        "hoa_fee": "hoa_fee",
        "stories": "stories",
    }

    ENTITY_BUCKETS = {
        "amenity": "amenities",
        "condition": "condition",
        "interior_feature": "interior_features",
        "exterior_feature": "exterior_features",
        "location": "location_features",
        "room": "rooms",
        "property_type": "property_type",
        "parking": "parking",
    }

    SIGNAL_BUCKETS = SIGNAL_BUCKETS

    FINANCING_PATTERNS = {
        "seller financing": [
            r"\bseller\s+financ(?:e|ing)\b",
            r"\bowner\s+(?:will\s+)?carry\b",
            r"\bowner\s+financ(?:e|ing)\b",
        ],
        "assumable loan": [r"\bassumable\s+(?:loan|mortgage|financing)\b"],
        "cash only": [r"\bcash\s+only\b", r"\ball\s+cash\b"],
        "fha loan": [r"\bfha\b"],
        "va loan": [r"\bva\b"],
        "conventional loan": [r"\bconventional\s+(?:loan|financing)\b"],
        "lease option": [r"\blease\s+option\b", r"\boption\s+to\s+purchase\b"],
    }

    EXTRA_SIGNAL_PATTERNS = {
        "amenities": {
            "private pool": [r"\bprivate\s+pool\b"],
            "community pool": [r"\bcommunity\s+pool\b"],
            "pool": [r"\b(?:private\s+|community\s+|sparkling\s+)?pool\b"],
            "spa": [r"\bspa\b", r"\bhot\s+tub\b", r"\bjacuzzi\b"],
            "ev charger": [r"\bev\s+charg(?:er|ing)\b"],
            "bbq area": [r"\b(?:bbq|barbecue)\s+(?:area|pavilion)\b"],
            "boat dock": [r"\b(?:private\s+)?(?:boat\s+)?dock\b"],
            "clubhouse": [r"\bclubhouse\b"],
            "tennis court": [r"\btennis\s+courts?\b"],
        },
        "condition": {
            "turnkey": [r"\bturn\s*key\b", r"\bturnkey\b"],
            "move-in ready": [r"\bmove\s+in\s+ready\b", r"\bmove-in\s+ready\b"],
            "updated": [r"\bupdated\b", r"\brecently\s+updated\b"],
            "remodeled": [r"\bremodel(?:ed|s)?\b", r"\brenovat(?:ed|ion)\b"],
            "new construction": [r"\bnew\s+construction\b", r"\bbrand\s+new\s+construction\b"],
            "fixer upper": [
                r"\b(?:cosmetic\s+)?fixer(?:\s+upper)?\b",
                r"\bin\s+need\s+of\s+renovation\b",
                r"\bneeds\s+(?:tlc|work|repairs?)\b",
            ],
        },
        "location_features": {
            "cul de sac": [r"\bcul[\s-]?de[\s-]?sac\b"],
            "ocean view": [r"\bocean\s+views?\b"],
            "mountain view": [r"\bmountain\s+views?\b"],
            "city lights view": [r"\bcity\s+lights?\s+views?\b"],
            "waterfront": [r"\bwaterfront\b", r"\briverfront\b", r"\blackefront\b"],
            "near beach": [r"\b(?:near|near\s+to|close\s+to)\s+(?:the\s+)?beach\b"],
            "near schools": [r"\b(?:near|near\s+to|close\s+to)\s+(?:[^.]{0,40}\s+)?schools?\b"],
            "near shopping": [r"\b(?:near|near\s+to|close\s+to|adjacent\s+to)\s+(?:[^.]{0,40}\s+)?(?:shopping|shops?|mall)\b"],
            "near dining": [r"\b(?:near|near\s+to|close\s+to|adjacent\s+to)\s+(?:[^.]{0,40}\s+)?(?:dining|restaurants?)\b"],
            "near parks": [r"\b(?:near|near\s+to|close\s+to|adjacent\s+to)\s+(?:[^.]{0,40}\s+)?parks?\b"],
            "near lake": [r"\b(?:near|near\s+to|close\s+to)\s+(?:the\s+)?lake\b"],
            "freeway access": [r"\b(?:easy\s+)?(?:freeway|highway)\s+access\b", r"\b(?:close\s+to|access\s+to)\s+(?:the\s+)?(?:freeway|highway)\b"],
            "quiet location": [r"\bquiet\s+(?:street|neighborhood|location)\b"],
        },
        "investment_features": {
            "adu potential": [r"\b(?:adu\s+potential|potential\s+(?:for\s+an?\s+)?adu|possible\s+adu\s+conversion)\b"],
            "rental income": [r"\b(?:rental\s+income|income[-\s]producing)\b"],
            "tenant occupied": [r"\btenant\s+occupied\b"],
            "value add": [r"\bvalue[-\s]add\b", r"\badd(?:ed)?\s+value\b", r"\b(?:significant|strong|tremendous)\s+upside\b"],
            "short term rental": [r"\bshort\s+term\s+rental\b"],
        },
        "transaction_features": {
            "as is": [r"\bas\s+is\b"],
            "no hoa": [r"\bno\s+(?:hoa|homeowners\s+association)\b"],
            "low hoa": [r"\blow\s+(?:hoa|homeowners\s+association)\b"],
            "55 community": [r"\b55\+?\s+(?:community|age\s+restricted)\b"],
        },
        "exterior_features": {
            "patio": [r"\b(?:private\s+|covered\s+|rear\s+|front\s+|back\s+)?patio\b"],
            "deck": [r"\b(?:private\s+|covered\s+|roof\s+)?deck\b"],
        },
        "interior_features": {
            "laundry hookups": [r"\bwasher\s*(?:and|/|\s)\s*dryer\s+hookups?\b"],
        },
    }

    TRANSACTION_TO_INVESTMENT = {
        "investment",
        "rental",
        "tenant occupied",
    }

    CANONICAL_VALUES = {
        "amenities": {
            "swimming pool": "pool",
            "hot tub": "spa",
            "jacuzzi": "spa",
            "solar panels": "solar",
            "solar system": "solar",
            "solar energy": "solar",
        },
        "condition": {
            "renovation": "renovated",
            "needs renovation": "fixer upper",
            "tlc": "fixer upper",
            "newly constructed": "new construction",
            "brand new": "new construction",
        },
        "location_features": {
            "shopping": "near shopping",
            "dining": "near dining",
            "shopping restaurants": "near shopping and dining",
            "close to shopping": "near shopping",
            "near shopping": "near shopping",
            "close to schools": "near schools",
            "top-rated schools": "near schools",
            "close to freeway": "freeway access",
            "freeway access": "freeway access",
            "water view": "water view",
            "views": "view",
        },
        "parking": {
            "garage parking": "garage",
            "driveway parking": "driveway",
            "rv parking": "rv parking",
        },
        "transaction_features": {
            "55 community": "55 community",
            "as-is": "as is",
        },
    }

    def __init__(self, taxonomy_path="data/processed/taxonomy.json", entity_extractor=None, text_cleaner=None):
        self.cleaner = text_cleaner or TextCleaner()
        self.entity_extractor = entity_extractor or EntityExtractor(taxonomy_path=taxonomy_path)

    def extract_signals(self, listing_record):
        record = dict(listing_record)
        remarks_raw = self._first_present(record, self.REMARK_FIELDS)
        remarks_cleaned = (
            str(remarks_raw).strip()
            if "remarks_cleaned" in record and self._has_value(record.get("remarks_cleaned"))
            else self.cleaner.clean_text(remarks_raw)
        )

        entities = self.entity_extractor.extract_all(remarks_cleaned)
        signals = {bucket: {} for bucket in self.SIGNAL_BUCKETS}

        self._add_entity_signals(signals, entities, remarks_cleaned)
        self._add_location_list_signals(signals, remarks_cleaned)
        self._add_phrase_signals(signals, remarks_cleaned)
        text_signals = self._finalize_signals(signals)

        return {
            "listing_id": self._json_value(self._first_present(record, self.FIELD_ALIASES["listing_id"])),
            "text_signals": text_signals,
            "numeric_signals": self._numeric_signals(record, entities),
            "keywords": self._keywords(text_signals),
        }

    def extract_many(self, listing_records):
        return [self.extract_signals(record) for record in listing_records]

    def _add_entity_signals(self, signals, entities, text):
        for entity in entities:
            label = entity.get("label")
            value = entity.get("value")
            if label in self.ENTITY_BUCKETS:
                if label == "location" and self._location_needs_context(value):
                    continue
                if self._is_potential_feature(entity, label, text):
                    continue
                self._add_signal(signals, self.ENTITY_BUCKETS[label], value)
            elif label == "transaction_or_listing":
                if self._is_financing_value(self._normalize_text(value)) and self._is_negated(
                    text, entity.get("start", 0)
                ):
                    continue
                self._add_transaction_signal(signals, value)

    def _add_transaction_signal(self, signals, value):
        normalized = self._normalize_text(value)
        bucket = "transaction_features"
        if normalized in self.TRANSACTION_TO_INVESTMENT:
            bucket = "investment_features"
        if self._is_financing_value(normalized):
            bucket = "financing_terms"
        self._add_signal(signals, bucket, normalized)

    def _add_phrase_signals(self, signals, text):
        for value, patterns in self.FINANCING_PATTERNS.items():
            for pattern in patterns:
                for _ in re.finditer(pattern, text, flags=re.I):
                    if self._is_negated(text, _.start()):
                        continue
                    self._add_signal(signals, "financing_terms", value)

        for bucket, term_patterns in self.EXTRA_SIGNAL_PATTERNS.items():
            for value, patterns in term_patterns.items():
                for pattern in patterns:
                    for _ in re.finditer(pattern, text, flags=re.I):
                        self._add_signal(signals, bucket, value)

    def _add_location_list_signals(self, signals, text):
        for match in re.finditer(
            r"\b(?:near|near\s+to|close\s+to|adjacent\s+to|minutes?\s+from|within\s+minutes?\s+of)\b",
            text,
            flags=re.I,
        ):
            clause = re.split(r"[.;]", text[match.end():match.end() + 120], maxsplit=1)[0].lower()
            if re.search(r"\b(?:shopping|shops?|mall)\b", clause):
                self._add_signal(signals, "location_features", "near shopping")
            if re.search(r"\b(?:dining|restaurants?)\b", clause):
                self._add_signal(signals, "location_features", "near dining")
            if re.search(r"\bschools?\b", clause):
                self._add_signal(signals, "location_features", "near schools")
            if re.search(r"\bparks?\b", clause):
                self._add_signal(signals, "location_features", "near parks")

    def _add_signal(self, signals, bucket, value):
        if bucket not in signals or not self._has_value(value):
            return

        value = self._canonical_value(bucket, value)
        key = self._signal_key(value)
        if not key:
            return
        signals[bucket][key] = self._json_value(value)

    def _numeric_signals(self, record, entities):
        values = {
            "price": self._number_from_record(record, self.FIELD_ALIASES["price"]),
            "beds": self._number_from_record(record, self.FIELD_ALIASES["beds"]),
            "baths": self._number_from_record(record, self.FIELD_ALIASES["baths"]),
            "sqft": self._number_from_record(record, self.FIELD_ALIASES["sqft"]),
            "lot_size": None,
            "year_built": None,
            "hoa_fee": None,
            "stories": None,
        }

        for entity in entities:
            label = entity.get("label")
            target = self.NUMERIC_ENTITY_LABELS.get(label)
            if target and values.get(target) is None:
                values[target] = self._json_value(entity.get("value"))
        return values

    def _finalize_signals(self, signals):
        return normalize_text_signals(
            {bucket: list(items.values()) for bucket, items in signals.items()}
        )

    def _keywords(self, text_signals):
        keywords = set()
        for bucket in self.SIGNAL_BUCKETS:
            for value in text_signals[bucket]:
                if isinstance(value, str):
                    keywords.add(value)
        return sorted(keywords)

    def _is_potential_feature(self, entity, label, text):
        if label not in {"amenity", "property_type", "room"}:
            return False
        start = entity.get("start", 0)
        context = text[max(0, start - 70):start].lower()
        tail = text[entity.get("end", start):entity.get("end", start) + 20].lower()
        if label == "amenity" and re.search(r"\b(?:nearby|near|close\s+to)\b[^.!?]{0,60}$", context):
            return True
        if label == "property_type" and re.match(r"\s+potential\b", tail):
            return True
        return bool(
            re.search(
                r"\b(?:can|could|may)\s+(?:\w+\s+){0,3}be\b[^.!?]{0,50}$"
                r"|\b(?:allows?|possible|potential)\s+(?:for\s+)?(?:an?\s+)?$"
                r"|\bideal\s+for\b[^.!?]{0,50}$",
                context,
            )
        )

    def _is_negated(self, text, start):
        context = text[max(0, start - 18):start].lower()
        return bool(re.search(r"\b(?:no|not|without)\b[^.!?]{0,18}$", context))

    def _location_needs_context(self, value):
        return self._normalize_text(value) in {
            "dining",
            "parks",
            "restaurants",
            "schools",
            "shopping",
            "shops",
        }

    def _first_present(self, record, names):
        for name in names:
            value = record.get(name)
            if self._has_value(value):
                return value
        return None

    def _number_from_record(self, record, names):
        return self._to_number(self._first_present(record, names))

    def _is_financing_value(self, value):
        return any(
            term in value
            for term in (
                "financing",
                "loan",
                "cash only",
                "all cash",
                "owner carry",
                "assumable",
                "lease option",
                "option to purchase",
            )
        )

    def _signal_key(self, value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(self._json_value(value))
        return self._normalize_text(value)

    def _canonical_value(self, bucket, value):
        if not isinstance(value, str):
            return value
        normalized = self._normalize_text(value)
        return self.CANONICAL_VALUES.get(bucket, {}).get(normalized, normalized)

    def _normalize_text(self, value):
        text = str(value).lower()
        text = re.sub(r"[-_/]+", " ", text)
        text = re.sub(r"[^\w\s.+]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _to_number(self, value):
        if not self._has_value(value):
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else value
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number

    def _json_value(self, value):
        if not self._has_value(value):
            return None
        if hasattr(value, "item"):
            return self._json_value(value.item())
        if isinstance(value, Decimal):
            number = float(value)
            return int(number) if number.is_integer() else number
        if isinstance(value, dict):
            return {key: self._json_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_value(item) for item in value]
        if isinstance(value, tuple):
            return [self._json_value(item) for item in value]
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    def _has_value(self, value):
        if value is None:
            return False
        if value.__class__.__name__ in {"NAType", "NaTType"}:
            return False
        if isinstance(value, float) and math.isnan(value):
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return True
