from scripts.entity_extractor import EntityExtractor


def values_for(entities, label):
    return [entity["value"] for entity in entities if entity["label"] == label]


def first_entity(entities, label):
    return next(entity for entity in entities if entity["label"] == label)


def test_extract_bedrooms():
    extractor = EntityExtractor()
    entities = extractor.extract_bedrooms("bright 3 bedroom home")
    assert values_for(entities, "bedrooms") == [3]


def test_bedroom_count_ignores_ordinals_and_large_false_counts():
    extractor = EntityExtractor()
    entities = extractor.extract_bedrooms("the second bedroom sits near 85 bedroom avenue")
    assert values_for(entities, "bedrooms") == []


def test_extract_bathrooms_with_decimal():
    extractor = EntityExtractor()
    entities = extractor.extract_bathrooms("includes 2.5 bathroom")
    assert values_for(entities, "bathrooms") == [2.5]


def test_extract_bathrooms_with_written_fraction():
    extractor = EntityExtractor()
    entities = extractor.extract_bathrooms("powder room with one and a half bath")
    assert values_for(entities, "bathrooms") == [1.5]


def test_bathroom_count_ignores_ordinals_and_large_false_counts():
    extractor = EntityExtractor()
    entities = extractor.extract_bathrooms("the second bathroom is near 280 bathroom lane")
    assert values_for(entities, "bathrooms") == []


def test_bedroom_bathroom_counts_ignore_acre_context():
    extractor = EntityExtractor()
    text = "almost 1 bedroom 3 bathroom of an acre"
    assert values_for(extractor.extract_bedrooms(text), "bedrooms") == []
    assert values_for(extractor.extract_bathrooms(text), "bathrooms") == []


def test_extract_listing_price():
    extractor = EntityExtractor()
    entities = extractor.extract_price("listed at 875000")
    assert values_for(entities, "price") == [875000]


def test_extract_standalone_price():
    extractor = EntityExtractor()
    entities = extractor.extract_price("new price 1250000")
    assert values_for(entities, "price") == [1250000]


def test_extract_sqft():
    extractor = EntityExtractor()
    entities = extractor.extract_sqft("open layout with 1840 square feet")
    assert values_for(entities, "sqft") == [1840]


def test_sqft_does_not_capture_lot_size():
    extractor = EntityExtractor()
    entities = extractor.extract_sqft("7500 square feet lot")
    assert values_for(entities, "sqft") == []


def test_sqft_does_not_capture_described_lot_size():
    extractor = EntityExtractor()
    entities = extractor.extract_sqft("8721 square feet private flat lot")
    assert values_for(entities, "sqft") == []


def test_extract_acre_lot_size():
    extractor = EntityExtractor()
    entities = extractor.extract_lot_size("private 0.25 acre lot")
    assert values_for(entities, "lot_size") == [0.25]


def test_extract_leading_decimal_acre_lot_size():
    extractor = EntityExtractor()
    entity = first_entity(extractor.extract_lot_size("private .35 acre lot"), "lot_size")
    assert entity["value"] == 0.35
    assert entity["text"] == ".35 acre lot"


def test_extract_square_foot_lot_size():
    extractor = EntityExtractor()
    entities = extractor.extract_lot_size("large 7500 square feet lot")
    assert values_for(entities, "lot_size") == [7500]


def test_extract_described_square_foot_lot_size():
    extractor = EntityExtractor()
    entity = first_entity(extractor.extract_lot_size("8721 square feet private flat lot"), "lot_size")
    assert entity["value"] == 8721
    assert entity["text"] == "8721 square feet private flat lot"


def test_extract_lot_dimensions():
    extractor = EntityExtractor()
    entities = extractor.extract_lot_size("rare 50 by 100 foot lot")
    assert values_for(entities, "lot_size") == [{"width_ft": 50.0, "depth_ft": 100.0}]


def test_extract_year_built():
    extractor = EntityExtractor()
    entities = extractor.extract_year_built("year built 2005")
    assert values_for(entities, "year_built") == [2005]


def test_extract_story_count():
    extractor = EntityExtractor()
    entities = extractor.extract_stories("classic 2 story home")
    assert values_for(entities, "stories") == [2]


def test_extract_split_level():
    extractor = EntityExtractor()
    entities = extractor.extract_stories("well kept split level layout")
    assert values_for(entities, "stories") == ["split level"]


def test_extract_garage_count():
    extractor = EntityExtractor()
    entities = extractor.extract_parking("oversized 2 car garage")
    assert values_for(entities, "parking") == [2, "garage"]


def test_extract_attached_garage_feature():
    extractor = EntityExtractor()
    entities = extractor.extract_parking("attached garage with storage")
    assert values_for(entities, "parking") == ["attached garage"]


def test_parking_feature_skips_laundry_context():
    extractor = EntityExtractor()
    entities = extractor.extract_parking("includes in garage laundry")
    assert values_for(entities, "parking") == []


def test_extract_monthly_hoa_fee():
    extractor = EntityExtractor()
    entities = extractor.extract_hoa("homeowners association fee 450 per month")
    assert values_for(entities, "hoa_fee") == [450]


def test_extract_no_hoa():
    extractor = EntityExtractor()
    entities = extractor.extract_hoa("no homeowners association")
    assert values_for(entities, "hoa_fee") == [0]


def test_taxonomy_extracts_amenity():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("community pool and spa")
    assert "community pool" in values_for(entities, "amenity")


def test_taxonomy_extracts_interior_feature():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("stainless steel appliances")
    assert "stainless steel appliances" in values_for(entities, "interior_feature")


def test_taxonomy_extracts_property_type():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("updated condo near downtown")
    assert "condo" in values_for(entities, "property_type")


def test_taxonomy_extracts_condition():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("recently remodeled kitchen")
    assert "recently remodeled" in values_for(entities, "condition")


def test_taxonomy_skips_generic_modern_marketing_phrase():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("modern comfort close to shopping")
    assert values_for(entities, "condition") == []


def test_taxonomy_skips_plural_bedroom_bathroom_room_terms():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("3 bedrooms and 2 bathrooms")
    assert values_for(entities, "room") == []


def test_taxonomy_skips_plural_room_terms_without_counts():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("bedrooms are upstairs and bathrooms are updated")
    assert values_for(entities, "room") == []


def test_taxonomy_skips_room_kitchen_inside_feature_phrase():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("modern kitchen lighting")
    assert values_for(entities, "room") == []


def test_taxonomy_skips_plural_living_areas_alias():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("separate living areas with good flow")
    assert values_for(entities, "room") == []


def test_taxonomy_skips_beach_inside_property_or_city_phrase():
    extractor = EntityExtractor()
    assert values_for(extractor.extract_taxonomy_terms("classic beach house"), "location") == []
    assert values_for(extractor.extract_taxonomy_terms("long beach location"), "location") == []


def test_taxonomy_skips_solar_lease_context():
    extractor = EntityExtractor()
    entities = extractor.extract_taxonomy_terms("option to purchase or lease the solar")
    assert values_for(entities, "transaction_or_listing") == []


def test_extract_all_keeps_longer_taxonomy_match():
    extractor = EntityExtractor()
    entities = extractor.extract_all("community pool")
    assert values_for(entities, "amenity") == ["community pool"]


def test_extract_all_maps_eval_style_phrases():
    extractor = EntityExtractor()
    text = "open concept living with a breakfast bar and indoor laundry room"
    entities = extractor.extract_all(text)
    assert values_for(entities, "interior_feature") == ["open concept", "breakfast bar"]
    assert values_for(entities, "room") == ["indoor laundry room"]


def test_extract_all_keeps_structured_sqft_over_room_term():
    extractor = EntityExtractor()
    entities = extractor.extract_all("1840 square feet")
    assert values_for(entities, "sqft") == [1840]


def test_extract_all_keeps_lot_size_separate_from_sqft():
    extractor = EntityExtractor()
    entities = extractor.extract_all("1840 square feet home on 7500 square feet lot")
    assert values_for(entities, "sqft") == [1840]
    assert values_for(entities, "lot_size") == [7500]


def test_extract_all_does_not_turn_year_into_price():
    extractor = EntityExtractor()
    entities = extractor.extract_all("year built 2005")
    assert values_for(entities, "year_built") == [2005]
    assert values_for(entities, "price") == []


def test_extract_all_combines_regex_and_taxonomy():
    extractor = EntityExtractor()
    text = "updated 3 bedroom 2 bathroom condo with pool"
    entities = extractor.extract_all(text)
    assert values_for(entities, "bedrooms") == [3]
    assert values_for(entities, "bathrooms") == [2]
    assert values_for(entities, "property_type") == ["condo"]
    assert values_for(entities, "amenity") == ["pool"]
    assert values_for(entities, "condition") == ["updated"]


def test_entity_output_schema():
    extractor = EntityExtractor()
    entity = first_entity(extractor.extract_all("3 bedroom"), "bedrooms")
    assert set(entity) == {"label", "value", "text", "start", "end", "method", "source"}


def test_entity_span_offsets():
    extractor = EntityExtractor()
    entity = first_entity(extractor.extract_all("large 3 bedroom home"), "bedrooms")
    assert entity["text"] == "3 bedroom"
    assert entity["start"] == 6
    assert entity["end"] == 15


def test_regex_entity_method_and_source():
    extractor = EntityExtractor()
    entity = first_entity(extractor.extract_all("3 bedroom"), "bedrooms")
    assert entity["method"] == "regex"
    assert entity["source"] == "bedroom_count"


def test_taxonomy_entity_method_and_source():
    extractor = EntityExtractor()
    entity = first_entity(extractor.extract_all("pool"), "amenity")
    assert entity["method"] == "taxonomy"
    assert entity["source"].startswith("amenity_")


def test_empty_text_returns_no_entities():
    extractor = EntityExtractor()
    assert extractor.extract_all("") == []


def test_none_text_returns_no_entities():
    extractor = EntityExtractor()
    assert extractor.extract_all(None) == []


def test_default_ner_interface_returns_empty_list():
    extractor = EntityExtractor()
    assert extractor.extract_ner_entities("Irvine condo") == []


def test_callable_ner_interface():
    def fake_ner(text):
        return [
            {
                "label": "location",
                "value": "Irvine",
                "text": "Irvine",
                "start": 0,
                "end": 6,
            }
        ]

    extractor = EntityExtractor(ner_model=fake_ner)
    entity = first_entity(extractor.extract_all("Irvine condo"), "location")
    assert entity["value"] == "Irvine"
    assert entity["method"] == "ner"
    assert entity["source"] == "function"


def test_object_ner_interface():
    class FakeNER:
        def extract(self, text):
            return [
                {
                    "label": "location",
                    "value": "Pasadena",
                    "text": "Pasadena",
                    "start": 0,
                    "end": 8,
                }
            ]

    extractor = EntityExtractor(ner_model=FakeNER())
    entity = first_entity(extractor.extract_all("Pasadena bungalow"), "location")
    assert entity["value"] == "Pasadena"
    assert entity["method"] == "ner"
    assert entity["source"] == "FakeNER"
