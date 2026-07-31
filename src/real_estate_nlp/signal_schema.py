import re


SIGNAL_BUCKETS = (
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


BUCKET_OVERRIDES = {
    ("amenities", "fireplace"): ("interior_features", "fireplace"),
    ("amenities", "solar"): ("exterior_features", "solar"),
    ("exterior_features", "bbq area"): ("amenities", "bbq area"),
    ("interior_features", "new paint"): ("condition", "freshly painted"),
    ("interior_features", "penthouse"): ("property_type", "penthouse"),
    ("interior_features", "solar"): ("exterior_features", "solar"),
    ("rooms", "breakfast bar"): ("interior_features", "breakfast bar"),
    ("transaction_features", "rental income"): ("investment_features", "rental income"),
    ("transaction_features", "short term rental"): ("investment_features", "short term rental"),
    ("transaction_features", "tenant occupied"): ("investment_features", "tenant occupied"),
}


VALUE_ALIASES = {
    "amenities": {
        "community pool": "pool",
        "pool and spa": "pool",
        "swimming pool": "pool",
        "tennis courts": "tennis court",
        "hot tub": "spa",
        "jacuzzi": "spa",
        "gym": "fitness center",
        "private dock": "boat dock",
    },
    "condition": {
        "brand new": "new construction",
        "fresh paint": "freshly painted",
        "freshly painted": "freshly painted",
        "new paint": "freshly painted",
        "needs renovation": "fixer upper",
        "renovated": "remodeled",
        "recently remodeled": "remodeled",
        "recently renovated": "remodeled",
        "renovated kitchen": "remodeled",
        "tlc": "fixer upper",
        "thoughtfully updated": "updated",
        "updated bathroom": "updated",
        "updated flooring": "updated",
        "updated kitchen": "updated",
        "upgraded": "updated",
        "upgraded flooring": "updated",
    },
    "interior_features": {
        "central air conditioning": "air conditioning",
        "hardwood flooring": "hardwood floors",
        "open concept": "open floor plan",
        "open concept kitchen": "open kitchen",
        "washer and dryer": "washer dryer",
        "walk in closet": "walk-in closet",
    },
    "exterior_features": {
        "fence": "fenced",
        "fenced backyard": "fenced",
    },
    "location_features": {
        "close to freeway": "freeway access",
        "close to schools": "near schools",
        "freeway": "freeway access",
        "mountain views": "mountain view",
        "near freeway": "freeway access",
        "quiet neighborhood": "quiet location",
        "shopping": "near shopping",
        "shopping center": "near shopping",
        "shopping centers": "near shopping",
        "shops": "near shopping",
        "restaurants": "near dining",
        "schools": "near schools",
        "school district": "near schools",
        "dining": "near dining",
        "park": "near parks",
        "parks": "near parks",
        "gated": "gated community",
        "views": "view",
    },
    "property_type": {
        "adu": "accessory dwelling unit",
        "condominium": "condo",
        "estate home": "estate",
        "townhouse": "townhome",
    },
    "rooms": {
        "indoor laundry": "laundry room",
        "indoor laundry room": "laundry room",
        "master bedroom": "primary suite",
        "primary bedroom": "primary suite",
    },
    "parking": {
        "driveway parking": "driveway",
        "garage parking": "garage",
        "rv access": "rv parking",
    },
}


EXPANDED_VALUES = {
    ("amenities", "pool and spa"): (("amenities", "pool"), ("amenities", "spa")),
    ("location_features", "near shopping and dining"): (
        ("location_features", "near shopping"),
        ("location_features", "near dining"),
    ),
    ("location_features", "shopping restaurants"): (
        ("location_features", "near shopping"),
        ("location_features", "near dining"),
    ),
}


EXCLUDED_VALUES = {
    ("amenities", "building amenities"),
    ("amenities", "community amenities"),
    ("condition", "cozy"),
    ("condition", "modern"),
    ("condition", "new"),
    ("condition", "upgrades"),
    ("interior_features", "flooring"),
    ("interior_features", "floor plan"),
    ("location_features", "convenient access"),
    ("location_features", "walking distance"),
    ("rooms", "bathroom"),
    ("rooms", "bedroom"),
    ("rooms", "dining area"),
    ("rooms", "dining room"),
    ("rooms", "family room"),
    ("rooms", "kitchen"),
    ("rooms", "living room"),
    ("transaction_features", "financing"),
    ("transaction_features", "hoa"),
    ("transaction_features", "income potential"),
    ("transaction_features", "income property"),
    ("transaction_features", "investment property"),
    ("transaction_features", "price reduction"),
    ("investment_features", "investment"),
    ("investment_features", "rental"),
    ("condition", "renovation"),
}


def normalize_value(value):
    text = str(value).lower()
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w\s.+]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def empty_text_signals():
    return {bucket: [] for bucket in SIGNAL_BUCKETS}


def normalize_text_signals(signals):
    normalized = empty_text_signals()
    for bucket, values in signals.items():
        if bucket not in normalized:
            continue
        for value in values:
            for target_bucket, target_value in _normalized_pairs(bucket, value):
                if target_value not in normalized[target_bucket]:
                    normalized[target_bucket].append(target_value)
    if "laundry hookups" in normalized["interior_features"]:
        normalized["interior_features"] = [
            value for value in normalized["interior_features"] if value != "washer dryer"
        ]
    if any(
        value in normalized["location_features"]
        for value in ("city lights view", "mountain view", "ocean view", "water view")
    ):
        normalized["location_features"] = [
            value for value in normalized["location_features"] if value != "view"
        ]
    return {bucket: sorted(values, key=str) for bucket, values in normalized.items()}


def _normalized_pairs(bucket, value):
    if not isinstance(value, str):
        return [(bucket, value)]

    normalized_value = normalize_value(value)
    expanded = EXPANDED_VALUES.get((bucket, normalized_value))
    if expanded:
        pairs = expanded
    else:
        pairs = ((bucket, normalized_value),)

    output = []
    for target_bucket, target_value in pairs:
        target_value = VALUE_ALIASES.get(target_bucket, {}).get(target_value, target_value)
        target_bucket, target_value = BUCKET_OVERRIDES.get(
            (target_bucket, target_value),
            (target_bucket, target_value),
        )
        if (target_bucket, target_value) not in EXCLUDED_VALUES:
            output.append((target_bucket, target_value))
    return output
