import json

from src.real_estate_nlp.query_parser import QueryParser
from src.real_estate_nlp.schema_validator import SchemaValidator
from scripts.generate_city_list import build_city_payload
from scripts.evaluate_query_parser import evaluate


def parser():
    return QueryParser()


def assert_filter(query, expected):
    filters = parser().parse(query, flat=True)
    for key, value in expected.items():
        assert filters[key] == value


def test_parse_city_and_price_cap():
    assert_filter(
        "homes in Irvine under 1 million",
        {"city": "Irvine", "price_max": 1_000_000},
    )


def test_parse_comma_formatted_price_cap():
    assert_filter(
        "homes in Irvine under $900,000",
        {"city": "Irvine", "price_max": 900_000},
    )


def test_parse_comma_formatted_price_range():
    assert_filter(
        "homes between $750,000 and $1,250,000",
        {"price_min": 750_000, "price_max": 1_250_000},
    )


def test_parse_city_from_generated_city_list():
    assert_filter(
        "homes in San Jose under 1.2 million",
        {"city": "San Jose", "price_max": 1_200_000},
    )


def test_city_blocklist_avoids_common_adjective_false_positive():
    filters = parser().parse("nice homes under 900k", flat=True)

    assert "city" not in filters
    assert filters["price_max"] == 900_000


def test_county_phrase_does_not_create_city_filter():
    filters = parser().parse("homes in Orange County with a pool", flat=True)

    assert filters["county"] == "Orange"
    assert "city" not in filters


def test_valid_city_asset_loaded():
    with open("data/processed/valid_cities.json") as f:
        payload = json.load(f)

    assert len(payload["cities"]) >= 500
    assert "San Jose" in payload["cities"]
    assert "Other" not in payload["cities"]


def test_city_list_builder_blocks_ambiguous_values():
    payload = build_city_payload(
        [("San Jose", 100), ("Nice", 10), ("Other", 5)],
        {"Nice", "Other"},
    )

    assert payload == {"cities": ["San Jose"], "blocked": ["Nice", "Other"]}


def test_parse_property_type_and_city():
    assert_filter(
        "show me houses in Pasadena",
        {"city": "Pasadena", "property_type": ["house"]},
    )


def test_parse_bedroom_minimum():
    assert_filter(
        "find listings in Santa Monica with at least 3 bedrooms",
        {"city": "Santa Monica", "beds_min": 3},
    )


def test_parse_price_below_k_suffix():
    assert_filter(
        "single family homes in Long Beach below 900k",
        {"city": "Long Beach", "property_type": ["single family"], "price_max": 900_000},
    )


def test_parse_bedroom_and_garage():
    assert_filter(
        "I need a 4 bedroom home in Anaheim with a garage",
        {"city": "Anaheim", "beds_min": 4, "amenities": ["garage"]},
    )


def test_parse_sqft_minimum():
    assert_filter(
        "homes in Irvine with at least 2000 sqft",
        {"city": "Irvine", "sqft_min": 2000},
    )


def test_parse_sqft_range():
    assert_filter(
        "homes between 1500 and 2200 square feet",
        {"sqft_min": 1500, "sqft_max": 2200},
    )


def test_parse_around_price_as_cap():
    assert_filter(
        "looking for a move-in ready place in Riverside around 700k",
        {"city": "Riverside", "price_max": 700_000, "condition": ["move-in ready"]},
    )


def test_parse_location_feature():
    assert_filter(
        "show me family homes near good shopping in Torrance under 1.2 million",
        {"city": "Torrance", "price_max": 1_200_000, "location_features": ["near shopping"]},
    )


def test_parse_room_and_view():
    assert_filter(
        "anything in San Diego with ocean views and enough space for a home office",
        {
            "city": "San Diego",
            "has_view": True,
            "location_features": ["ocean view"],
            "room": ["home office"],
        },
    )


def test_parse_county_and_negated_condition():
    assert_filter(
        "find me something in Orange County that has a pool, 3 beds, and is not a fixer",
        {
            "county": "Orange",
            "beds_min": 3,
            "private_pool": True,
            "amenities": ["pool"],
            "condition_exclude": ["fixer upper"],
        },
    )


def test_parse_near_beach_and_turnkey():
    assert_filter(
        "we want a turnkey home near the beach but still under 1.5m",
        {"price_max": 1_500_000, "location_features": ["near beach"], "condition": ["turnkey"]},
    )


def test_parse_price_floor():
    assert_filter("properties above 1.5 million", {"price_min": 1_500_000})


def test_parse_price_range_between():
    assert_filter(
        "show listings between 700k and 950k",
        {"price_min": 700_000, "price_max": 950_000},
    )


def test_parse_price_range_from_to():
    assert_filter(
        "houses in Pasadena from 1 million to 1.4 million",
        {
            "city": "Pasadena",
            "property_type": ["house"],
            "price_min": 1_000_000,
            "price_max": 1_400_000,
        },
    )


def test_parse_sort_cheapest():
    assert_filter(
        "I want the cheapest homes with at least 4 bedrooms in Corona",
        {"city": "Corona", "beds_min": 4, "sort": "price_asc"},
    )


def test_parse_beds_and_baths():
    assert_filter(
        "homes with 4 beds and 3 baths",
        {"beds_min": 4, "baths_min": 3},
    )


def test_parse_preferred_bed_count():
    assert_filter(
        "minimum 3 beds, preferably 4, with more than 2 bathrooms",
        {"beds_min": 3, "beds_preferred": 4, "baths_min": 2},
    )


def test_parse_written_bath_count():
    assert_filter(
        "not interested unless it has a real primary bedroom and two full baths",
        {"room": ["primary bedroom"], "baths_min": 2},
    )


def test_parse_multigenerational_family_context():
    assert_filter(
        "find homes where parents can stay downstairs and kids have separate bedrooms",
        {"room": ["downstairs bedroom"], "use_case": ["multi-generational"]},
    )


def test_parse_cul_de_sac():
    assert_filter(
        "homes in a cul de sac in Irvine",
        {"city": "Irvine", "location_features": ["cul de sac"]},
    )


def test_parse_school_and_park_location():
    assert_filter(
        "show homes close to schools and parks",
        {"location_features": ["near schools", "near parks"]},
    )


def test_parse_busy_street_exclusion():
    assert_filter(
        "homes that feel private, not on a busy street",
        {"location_features": ["private"], "location_features_exclude": ["busy street"]},
    )


def test_parse_pool_and_spa():
    assert_filter("homes with pool and spa", {"private_pool": True, "amenities": ["pool", "spa"]})


def test_parse_condo_amenities():
    assert_filter(
        "show condos with a gym and clubhouse",
        {"property_type": ["condo"], "amenities": ["gym", "clubhouse"]},
    )


def test_parse_rv_parking():
    assert_filter(
        "find homes with RV parking in Riverside",
        {"city": "Riverside", "amenities": ["rv parking"]},
    )


def test_parse_fireplace_and_central_air():
    assert_filter(
        "houses with a fireplace and central air",
        {"fireplace": True, "amenities": ["fireplace", "central air"]},
    )


def test_parse_private_pool_exclusion():
    assert_filter(
        "find listings with a private pool, not just community pool",
        {
            "private_pool": True,
            "amenities": ["private pool"],
            "amenities_exclude": ["community pool"],
        },
    )


def test_parse_community_pool_stays_soft():
    result = parser().parse("show condos in Irvine with community pool")

    assert "private_pool" not in result["hard_filters"]
    assert result["soft_signals"]["amenities"] == ["community pool"]


def test_parse_ev_charger():
    assert_filter(
        "homes with space for an EV charger or already installed charging",
        {"amenities": ["ev charger", "garage"]},
    )


def test_parse_interior_features():
    assert_filter(
        "find listings with high ceilings and natural light",
        {"interior_features": ["high ceilings", "natural light"]},
    )


def test_parse_open_floor_plan_from_loose_language():
    assert_filter(
        "I want a bright home that does not feel chopped up inside",
        {"interior_features": ["natural light", "open floor plan"]},
    )


def test_parse_kitchen_living_flow():
    assert_filter(
        "find homes where the kitchen, dining, and living areas flow together",
        {"interior_features": ["kitchen dining living flow", "open floor plan"]},
    )


def test_parse_exterior_features():
    assert_filter(
        "show homes with a landscaped yard and covered patio",
        {"exterior_features": ["landscaped yard", "covered patio"]},
    )


def test_parse_pet_use_case():
    assert_filter(
        "find houses with a private backyard for dogs",
        {"exterior_features": ["private backyard"], "use_case": ["pets"]},
    )


def test_parse_outdoor_use_cases():
    assert_filter(
        "I need outdoor space that works for kids and weekend BBQs",
        {
            "exterior_features": ["backyard", "outdoor entertaining"],
            "use_case": ["kids", "barbecue"],
        },
    )


def test_parse_tiny_patio_exclusion():
    assert_filter(
        "show me homes that have privacy outside, not just a tiny patio",
        {
            "exterior_features": ["private outdoor space"],
            "exterior_features_exclude": ["tiny patio"],
        },
    )


def test_parse_condition_exclusions():
    assert_filter(
        "I do not want a project, only clean and ready homes",
        {"condition_exclude": ["project", "fixer upper"]},
    )


def test_parse_modern_not_brand_new():
    assert_filter(
        "show listings that feel modern without being brand new",
        {"condition": ["modern"], "condition_exclude": ["new construction"]},
    )


def test_parse_townhome_and_attached_garage():
    assert_filter(
        "find townhomes with attached garage",
        {"property_type": ["townhouse"], "amenities": ["attached garage"]},
    )


def test_parse_detached_home_with_condo_exclusion():
    assert_filter(
        "not interested in condos, show detached homes",
        {"property_type": ["detached home"], "property_type_exclude": ["condo"]},
    )


def test_parse_open_house_date():
    assert_filter(
        "show Sunday open houses in Irvine",
        {"city": "Irvine", "open_house_date": "Sunday"},
    )


def test_parse_open_house_time():
    assert_filter(
        "show me open houses I can visit after lunch on Sunday",
        {"open_house_date": "Sunday", "open_house_time": "after lunch"},
    )


def test_parse_investment_features():
    assert_filter(
        "homes with guest house or separate entrance",
        {"investment_features": ["guest house", "separate entrance"]},
    )


def test_parse_short_term_rental():
    assert_filter(
        "find homes that could work for short term rental near the beach",
        {"investment_features": ["short term rental"], "location_features": ["near beach"]},
    )


def test_parse_summary_focus():
    assert_filter(
        "give me a neutral summary and avoid any wording that could raise compliance issues",
        {"summary_focus": ["neutral summary", "compliance-safe wording"]},
    )


def test_city_name_does_not_create_beach_signal():
    result = parser().parse("homes in Newport Beach", flat=True)

    assert result == {"city": "Newport Beach"}


def test_parking_amenities_do_not_duplicate_as_exterior_features():
    result = parser().parse("listings with a garage", flat=True)

    assert result == {"amenities": ["garage"]}


def test_private_backyard_does_not_create_private_location_signal():
    result = parser().parse("find houses with a private backyard for dogs", flat=True)

    assert result == {"exterior_features": ["private backyard"], "use_case": ["pets"]}


def test_specific_summary_focus_does_not_add_general_focus():
    result = parser().parse("summarize the amenities in this listing", flat=True)

    assert result == {"summary_focus": ["amenities"]}


def test_parse_query_returns_intent_envelope():
    result = parser().parse_query("open houses this weekend")
    assert result == {
        "intent": "open_house_search",
        "filters": {"open_house_date": "this weekend"},
        "hard_filters": {},
        "soft_signals": {"open_house_date": "this weekend"},
    }


def test_parse_returns_search_result():
    result = parser().parse("3 bed homes in Irvine under 900k with pool")

    assert result["hard_filters"] == {
        "city": "Irvine",
        "price_max": 900_000,
        "beds_min": 3,
        "private_pool": True,
    }
    assert result["soft_signals"] == {"amenities": ["pool"]}


def test_to_sql_uses_parameters_for_structured_filters():
    sql, params = parser().to_sql(
        {
            "city": "Irvine",
            "price_max": 900_000,
            "beds_min": 3,
            "private_pool": True,
            "amenities": ["pool"],
        }
    )

    assert "L_City = %s" in sql
    assert "L_SystemPrice <= %s" in sql
    assert "L_Keyword2 >= %s" in sql
    assert "PoolPrivateYN = %s" in sql
    assert "L_Remarks LIKE %s" not in sql
    assert params == ["Irvine", 900_000, 3, True]


def test_to_sql_can_include_soft_signals_when_requested():
    sql, params = parser().to_sql(
        {
            "city": "Irvine",
            "price_max": 900_000,
            "beds_min": 3,
            "private_pool": True,
            "amenities": ["pool"],
        },
        include_soft_signals=True,
    )

    assert "L_Remarks LIKE %s" in sql
    assert params == ["Irvine", 900_000, 3, True, "%pool%"]


def test_to_sql_uses_structured_sqft_and_flags():
    sql, params = parser().to_sql(
        {
            "sqft_min": 1800,
            "sqft_max": 2600,
            "private_pool": True,
            "fireplace": True,
            "has_view": True,
        }
    )

    assert "LM_Int2_3 >= %s" in sql
    assert "LM_Int2_3 <= %s" in sql
    assert "PoolPrivateYN = %s" in sql
    assert "FireplaceYN = %s" in sql
    assert "ViewYN = %s" in sql
    assert params == [1800, 2600, True, True, True]


def test_to_sql_accepts_parse_query_result():
    parsed = parser().parse_query("3 bed homes in Irvine under 900k")
    sql, params = parser().to_sql(parsed)

    assert "L_City = %s" in sql
    assert params[:3] == ["Irvine", 900_000, 3]


def test_to_sql_does_not_concat_user_text():
    query = "homes in Irvine'; DROP TABLE rets_property; -- under 900k"
    filters = parser().parse(query, flat=True)
    sql, params = parser().to_sql(filters)

    assert "DROP TABLE" not in sql
    assert "Irvine" in params
    assert 900_000 in params


def test_like_params_escape_wildcards():
    sql, params = parser().to_sql({"amenities": ["pool_%"]}, include_soft_signals=True)

    assert "ESCAPE" in sql
    assert params == [r"%pool\_\%%"]


def test_parse_splits_hard_filters_and_soft_signals():
    result = parser().parse("3 bed homes in Irvine under 900k with pool")

    assert result["hard_filters"] == {
        "price_max": 900_000,
        "beds_min": 3,
        "city": "Irvine",
        "private_pool": True,
    }
    assert result["soft_signals"] == {"amenities": ["pool"]}


def test_to_sql_accepts_parse_result_without_soft_where_clauses():
    parsed = parser().parse("3 bed homes in Irvine under 900k with pool")
    sql, params = parser().to_sql(parsed)

    assert "L_Remarks LIKE %s" not in sql
    assert params == ["Irvine", 900_000, 3, True]


def test_validator_accepts_valid_parser_output():
    filters = parser().parse("3 bed homes in Irvine under 900k with pool")
    valid, errors = SchemaValidator().validate_query(filters)

    assert valid
    assert errors == []


def test_validator_accepts_generated_city_list_city():
    valid, errors = SchemaValidator().validate_query({"city": "San Jose"})

    assert valid
    assert errors == []


def test_validator_accepts_parse_query_envelope():
    parsed = parser().parse_query("open houses this weekend in Pasadena")
    valid, errors = SchemaValidator().validate_query(parsed)

    assert valid
    assert errors == []


def test_validator_rejects_unknown_city():
    valid, errors = SchemaValidator(cities=["Irvine"]).validate_query({"city": "Atlantis"})

    assert not valid
    assert "City 'Atlantis' not found in known city list" in errors


def test_validator_rejects_too_low_price():
    valid, errors = SchemaValidator().validate_query({"price_max": 49_999})

    assert not valid
    assert "price_max=49999 is outside the supported range" in errors


def test_validator_rejects_too_high_price():
    valid, errors = SchemaValidator().validate_query({"price_min": 150_000_000})

    assert not valid
    assert "price_min=150000000 is outside the supported range" in errors


def test_validator_rejects_impossible_bed_count():
    valid, errors = SchemaValidator().validate_query({"beds_min": 99})

    assert not valid
    assert "beds_min=99 is outside the supported range" in errors


def test_validator_rejects_invalid_sqft():
    valid, errors = SchemaValidator().validate_query({"sqft_min": 60})

    assert not valid
    assert "sqft_min=60 is outside the supported range" in errors


def test_validator_rejects_non_boolean_structured_flag():
    valid, errors = SchemaValidator().validate_query({"private_pool": "yes"})

    assert not valid
    assert "private_pool must be boolean" in errors


def test_validator_rejects_inverted_price_range():
    valid, errors = SchemaValidator().validate_query({"price_min": 900_000, "price_max": 700_000})

    assert not valid
    assert "price_min cannot be greater than price_max" in errors


def test_validator_rejects_inverted_sqft_range():
    valid, errors = SchemaValidator().validate_query({"sqft_min": 3000, "sqft_max": 1500})

    assert not valid
    assert "sqft_min cannot be greater than sqft_max" in errors


def test_validator_rejects_unknown_filter_key():
    valid, errors = SchemaValidator().validate_query({"city": "Irvine", "unsafe_sql": "DROP TABLE"})

    assert not valid
    assert "Unsupported filter: unsafe_sql" in errors


def test_validator_rejects_non_list_feature_field():
    valid, errors = SchemaValidator().validate_query({"amenities": "pool"})

    assert not valid
    assert "amenities must be a list" in errors


def test_validator_catches_bad_sql_injection_filter_shape():
    filters = {"city": "Irvine", "amenities": ["pool"], "raw_where": "1=1; DROP TABLE rets_property"}
    valid, errors = SchemaValidator().validate_query(filters)

    assert not valid
    assert "Unsupported filter: raw_where" in errors


def test_evaluation_reports_exact_match_accuracy():
    queries = [
        {
            "id": "q1",
            "query": "homes in Irvine under 900k",
            "entities": {"city": "Irvine", "max_price": 900_000},
        }
    ]

    report = evaluate(queries, parser())

    assert report["matched_expected_fields"] == 2
    assert report["total_expected_fields"] == 2
    assert report["full_filter_exact_match_rate"] == 1
    assert report["hard_filter_exact_match_rate"] == 1


def test_evaluation_separates_coverage_from_extra_fields():
    queries = [
        {
            "id": "q1",
            "query": "homes in Irvine under 900k with garage",
            "entities": {"city": "Irvine", "max_price": 900_000},
        }
    ]

    report = evaluate(queries, parser())

    assert report["matched_expected_fields"] == 2
    assert report["total_expected_fields"] == 2
    assert report["full_filter_exact_match_rate"] == 0
    assert report["hard_filter_exact_match_rate"] == 1
    assert report["soft_signal_exact_match_rate"] == 0
    assert report["extra_fields"] == {"amenities": 1}
    assert report["hard_extra_fields"] == {}
    assert report["soft_extra_fields"] == {"amenities": 1}
