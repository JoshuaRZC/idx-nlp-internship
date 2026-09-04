from src.real_estate_nlp.signal_extractor import SignalExtractor
from src.real_estate_nlp.text_cleaner import TextCleaner


class FakeEntityExtractor:
    def __init__(self, entities):
        self.entities = entities
        self.last_text = None

    def extract_all(self, text):
        self.last_text = text
        return self.entities


def entity(label, value, text, method="regex", source="test", start=0):
    return {
        "label": label,
        "value": value,
        "text": text,
        "start": start,
        "end": start + len(text),
        "method": method,
        "source": source,
    }


def values(result, bucket):
    return result["text_signals"][bucket]


def test_signal_schema_keeps_compact_text_and_numeric_signals():
    extractor = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("amenity", "pool", "pool"),
                entity("condition", "updated", "updated"),
            ]
        )
    )

    result = extractor.extract_signals(
        {
            "listing_id": "A1",
            "city": "Irvine",
            "price": 1_250_000,
            "remarks": "Updated home with pool.",
        }
    )

    assert set(result) == {
        "listing_id",
        "text_signals",
        "numeric_signals",
        "keywords",
    }
    assert result["listing_id"] == "A1"
    assert values(result, "amenities") == ["pool"]
    assert values(result, "condition") == ["updated"]
    assert "pool" in result["keywords"]


def test_numeric_signals_prefer_record_fields():
    extractor = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("price", 1_000_000, "$1,000,000"),
                entity("bedrooms", 4, "4 bedroom"),
                entity("lot_size", 7200, "7200 square feet lot"),
            ]
        )
    )

    result = extractor.extract_signals(
        {
            "listing_id": "A2",
            "price": 950_000,
            "beds": 3,
            "baths": 2.5,
            "sqft": 1840,
            "remarks": "4 bedroom on a 7200 square feet lot.",
        }
    )

    assert result["numeric_signals"]["price"] == 950_000
    assert result["numeric_signals"]["beds"] == 3
    assert result["numeric_signals"]["baths"] == 2.5
    assert result["numeric_signals"]["sqft"] == 1840
    assert result["numeric_signals"]["lot_size"] == 7200


def test_duplicate_signal_keeps_one_compact_value():
    extractor = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("amenity", "pool", "pool", method="taxonomy"),
                entity("amenity", "pool", "sparkling pool", method="regex"),
            ]
        )
    )

    result = extractor.extract_signals({"listing_id": "A3", "remarks": "Sparkling pool and pool."})
    assert values(result, "amenities") == ["pool"]
    assert set(result) == {"listing_id", "text_signals", "numeric_signals", "keywords"}


def test_empty_remark_returns_empty_signal_buckets():
    result = SignalExtractor(entity_extractor=FakeEntityExtractor([])).extract_signals(
        {"listing_id": "A4", "remarks": ""}
    )

    assert all(items == [] for items in result["text_signals"].values())
    assert result["keywords"] == []


def test_raw_mls_column_names_are_supported():
    result = SignalExtractor(entity_extractor=FakeEntityExtractor([])).extract_signals(
        {
            "L_ListingID": "MLS1",
            "L_Address": "10 Main St",
            "L_City": "Pasadena",
            "L_SystemPrice": 900000,
            "L_Keyword2": 2,
            "LM_Dec_3": 1.5,
            "LM_Int2_3": 1200,
            "L_Remarks": "",
        }
    )

    assert result["listing_id"] == "MLS1"
    assert result["numeric_signals"]["price"] == 900000
    assert result["numeric_signals"]["beds"] == 2
    assert result["numeric_signals"]["baths"] == 1.5
    assert result["numeric_signals"]["sqft"] == 1200


def test_financing_phrase_rules_do_not_need_entity_match():
    result = SignalExtractor(entity_extractor=FakeEntityExtractor([])).extract_signals(
        {"listing_id": "A5", "remarks": "Seller financing available for qualified buyers."}
    )

    assert values(result, "financing_terms") == ["seller financing"]


def test_location_signals_use_search_ready_values():
    extractor = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("location", "shopping", "shopping"),
                entity("location", "dining", "dining"),
                entity("location", "close to schools", "close to schools"),
            ]
        )
    )

    result = extractor.extract_signals({"listing_id": "A6", "remarks": "Near shopping, dining, and schools."})

    assert values(result, "location_features") == [
        "near dining",
        "near schools",
        "near shopping",
    ]


def test_transaction_entities_are_routed_to_signal_buckets():
    extractor = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("transaction_or_listing", "tenant occupied", "tenant occupied"),
                entity("transaction_or_listing", "va loan", "VA approved"),
                entity("transaction_or_listing", "as is", "as is"),
            ]
        )
    )

    result = extractor.extract_signals({"listing_id": "A7", "remarks": "Tenant occupied, VA approved, as is."})

    assert values(result, "investment_features") == ["tenant occupied"]
    assert values(result, "financing_terms") == ["va loan"]
    assert values(result, "transaction_features") == ["as is"]


def test_text_signals_use_one_bucket_and_one_canonical_value():
    extractor = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("amenity", "fireplace", "fireplace"),
                entity("amenity", "community amenities", "amenities"),
                entity("interior_feature", "solar", "solar panels"),
                entity("room", "kitchen", "kitchen"),
                entity("room", "primary suite", "primary suite"),
                entity("transaction_or_listing", "investment", "investment opportunity"),
            ]
        )
    )

    result = extractor.extract_signals({"listing_id": "A8", "remarks": ""})

    assert values(result, "amenities") == []
    assert values(result, "interior_features") == ["fireplace"]
    assert values(result, "exterior_features") == ["solar"]
    assert values(result, "rooms") == ["primary suite"]
    assert values(result, "investment_features") == []


def test_financing_rules_ignore_negated_eligibility():
    result = SignalExtractor(entity_extractor=FakeEntityExtractor([])).extract_signals(
        {"listing_id": "A9", "remarks": "No FHA or VA financing. Cash only."}
    )

    assert values(result, "financing_terms") == ["cash only"]


def test_location_lists_do_not_treat_indoor_dining_as_a_nearby_location():
    result = SignalExtractor(entity_extractor=FakeEntityExtractor([])).extract_signals(
        {
            "listing_id": "A10",
            "remarks": "Near schools, shopping, and dining. The dining room opens to the kitchen.",
        }
    )

    assert values(result, "location_features") == [
        "near dining",
        "near schools",
        "near shopping",
    ]


def test_potential_uses_are_not_emitted_as_existing_features():
    remarks = "The lower level offers possible ADU conversion and could easily be used as a gym."
    cleaned_remarks = TextCleaner().clean_text(remarks)
    result = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity(
                    "property_type",
                    "accessory dwelling unit",
                    "accessory dwelling unit",
                    start=cleaned_remarks.index("accessory dwelling unit"),
                ),
                entity("amenity", "gym", "gym", start=cleaned_remarks.index("gym")),
            ]
        )
    ).extract_signals(
        {
            "listing_id": "A11",
            "remarks": remarks,
        }
    )

    assert values(result, "property_type") == []
    assert values(result, "amenities") == []


def test_pool_rules_ignore_absent_or_potential_pools():
    extractor = SignalExtractor(entity_extractor=FakeEntityExtractor([]))

    for remark in (
        "No pool on the property.",
        "A private yard without a pool.",
        "Potential pool site with room for a pool.",
        "The backyard could add a pool.",
    ):
        result = extractor.extract_signals({"listing_id": "POOL", "remarks": remark})
        assert values(result, "amenities") == []

    result = extractor.extract_signals({"listing_id": "POOL", "remarks": "Private pool and spa beside the patio."})
    assert "private pool" in values(result, "amenities")


def test_schema_keeps_laundry_hookups_distinct_from_appliances():
    result = SignalExtractor(
        entity_extractor=FakeEntityExtractor(
            [
                entity("amenity", "gym", "gym"),
                entity("interior_feature", "washer dryer", "washer/dryer"),
            ]
        )
    ).extract_signals(
        {"listing_id": "A12", "remarks": "Community gym and washer/dryer hookups."}
    )

    assert values(result, "amenities") == ["fitness center"]
    assert values(result, "interior_features") == ["laundry hookups"]


def test_extract_many_returns_one_signal_record_per_listing():
    extractor = SignalExtractor(entity_extractor=FakeEntityExtractor([]))
    results = extractor.extract_many(
        [
            {"listing_id": "A13", "remarks": ""},
            {"listing_id": "A14", "remarks": ""},
        ]
    )

    assert [item["listing_id"] for item in results] == ["A13", "A14"]
