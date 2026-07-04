import pandas as pd
import pytest

from scripts.text_cleaning import TextCleaner


def test_unicode_non_breaking_space():
    cleaner = TextCleaner()
    assert cleaner.normalize_unicode("Luxury\u00a0home") == "Luxury home"


def test_unicode_smart_quotes():
    cleaner = TextCleaner()
    assert cleaner.normalize_unicode("\u201cMove-in ready\u201d") == '"Move-in ready"'


def test_unicode_long_dash():
    cleaner = TextCleaner()
    assert cleaner.normalize_unicode("pool \u2014 spa") == "pool - spa"


def test_remove_paragraph_tags():
    cleaner = TextCleaner()
    assert cleaner.remove_html("<p>Updated kitchen</p>") == " Updated kitchen "


def test_remove_br_tags():
    cleaner = TextCleaner()
    assert cleaner.remove_html("Great room<br>Pool") == "Great room Pool"


def test_decode_html_ampersand():
    cleaner = TextCleaner()
    assert cleaner.remove_html("Pool &amp; spa") == "Pool & spa"


def test_decode_html_space():
    cleaner = TextCleaner()
    assert cleaner.remove_html("A&nbsp;large lot") == "A large lot"


def test_price_k_suffix():
    cleaner = TextCleaner()
    assert cleaner.normalize_prices("priced at 450k") == "priced at 450000"


def test_price_m_suffix_with_dollar():
    cleaner = TextCleaner()
    assert cleaner.normalize_prices("listed for $1.2m") == "listed for 1200000"


def test_price_m_suffix_without_dollar():
    cleaner = TextCleaner()
    assert cleaner.normalize_prices("value near 2.5M") == "value near 2500000"


def test_price_with_commas():
    cleaner = TextCleaner()
    assert cleaner.normalize_prices("asking $1,250,000") == "asking 1250000"


def test_price_range_language_is_not_forced():
    cleaner = TextCleaner()
    assert cleaner.normalize_prices("low $900s") == "low $900s"


def test_measurement_sqft():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("2,000 sqft home") == "2000 square feet home"


def test_measurement_sq_ft():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("750 sq ft condo") == "750 square feet condo"


def test_measurement_sf_with_periods():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("7,500 s.f. lot") == "7500 square feet lot"


def test_measurement_acre_abbreviation():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("0.25 ac parcel") == "0.25 acre parcel"


def test_measurement_fractional_acre():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("1/2 acre lot") == "0.5 acre lot"


def test_measurement_lot_dimensions():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("50x100 lot") == "50 by 100 foot lot"


def test_measurement_feet():
    cleaner = TextCleaner()
    assert cleaner.normalize_measurements("8 ft ceilings") == "8 foot ceilings"


def test_bedroom_br():
    cleaner = TextCleaner()
    assert cleaner.normalize_bed_bath_counts("3br home") == "3 bedroom home"


def test_bedroom_bd():
    cleaner = TextCleaner()
    assert cleaner.normalize_bed_bath_counts("4 bd plan") == "4 bedroom plan"


def test_bathroom_ba():
    cleaner = TextCleaner()
    assert cleaner.normalize_bed_bath_counts("2.5ba condo") == "2.5 bathroom condo"


def test_bed_bath_slash_format():
    cleaner = TextCleaner()
    assert cleaner.normalize_bed_bath_counts("3/2 ranch") == "3 bedroom 2 bathroom ranch"


def test_full_bathroom():
    cleaner = TextCleaner()
    assert cleaner.normalize_bed_bath_counts("2 full baths") == "2 full bathroom"


def test_half_bathroom():
    cleaner = TextCleaner()
    assert cleaner.normalize_bed_bath_counts("1 half bath") == "1 half bathroom"


def test_parking_car_garage():
    cleaner = TextCleaner()
    assert cleaner.normalize_parking("2-car garage") == "2 car garage"


def test_parking_attached_garage():
    cleaner = TextCleaner()
    assert cleaner.normalize_parking("2 car attached gar") == "2 car attached garage"


def test_parking_assigned_space():
    cleaner = TextCleaner()
    assert cleaner.normalize_parking("1 assigned pkg") == "1 assigned parking"


def test_parking_for_two():
    cleaner = TextCleaner()
    assert cleaner.normalize_parking("pkg for 2") == "2 parking"


def test_hoa_none():
    cleaner = TextCleaner()
    assert cleaner.normalize_hoa("no HOA") == "no homeowners association"


def test_hoa_monthly_fee_after_hoa():
    cleaner = TextCleaner()
    assert cleaner.normalize_hoa("HOA $450/mo") == "homeowners association fee 450 per month"


def test_hoa_monthly_fee_before_hoa():
    cleaner = TextCleaner()
    assert cleaner.normalize_hoa("450/month HOA") == "homeowners association fee 450 per month"


def test_hoa_fee_included():
    cleaner = TextCleaner()
    assert cleaner.normalize_hoa("HOA fees included") == "homeowners association fee included"


def test_hoa_includes_water():
    cleaner = TextCleaner()
    assert cleaner.normalize_hoa("HOA incl water") == "homeowners association includes water"


def test_year_built_phrase():
    cleaner = TextCleaner()
    assert cleaner.normalize_year_built("built in 1998") == "year built 1998"


def test_year_built_abbreviation():
    cleaner = TextCleaner()
    assert cleaner.normalize_year_built("yr blt 2005") == "year built 2005"


def test_year_built_construction_after_year():
    cleaner = TextCleaner()
    assert cleaner.normalize_year_built("2018 construction") == "year built 2018"


def test_year_built_constructed():
    cleaner = TextCleaner()
    assert cleaner.normalize_year_built("constructed 2020") == "year built 2020"


def test_single_story():
    cleaner = TextCleaner()
    assert cleaner.normalize_stories("single-story home") == "1 story home"


def test_two_story():
    cleaner = TextCleaner()
    assert cleaner.normalize_stories("two story plan") == "2 story plan"


def test_three_level():
    cleaner = TextCleaner()
    assert cleaner.normalize_stories("3-level townhouse") == "3 story townhouse"


def test_tri_level():
    cleaner = TextCleaner()
    assert cleaner.normalize_stories("tri-level layout") == "3 story layout"


def test_split_level():
    cleaner = TextCleaner()
    assert cleaner.normalize_stories("split-level home") == "split level home"


def test_expand_master_bedroom():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("mstr br") == "master bedroom"


def test_expand_primary_bedroom():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("prim bdrm") == "primary bedroom"


def test_expand_living_room():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("liv rm") == "living room"


def test_expand_dining_room():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("din rm") == "dining room"


def test_expand_family_room():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("fam rm") == "family room"


def test_expand_recreation_room():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("rec rm") == "recreation room"


def test_expand_kitchen_and_appliances():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("kit w/ ss appls") == "kitchen with stainless steel appliances"


def test_expand_dishwasher_refrigerator():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("dw and refrig") == "dishwasher and refrigerator"


def test_expand_washer_dryer():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("w/d hookups") == "washer dryer hookups"


def test_expand_backyard_balcony():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("bkyd and balc") == "backyard and balcony"


def test_expand_property_and_school():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("sfh near elem sch") == "single family home near elementary school"


def test_expand_neighborhood():
    cleaner = TextCleaner()
    assert cleaner.expand_abbreviations("nbhd park") == "neighborhood park"


def test_do_not_expand_drive_address():
    cleaner = TextCleaner()
    assert cleaner.clean_text("23785 Black Canyon Dr") == "23785 black canyon dr"


def test_do_not_expand_street_address():
    cleaner = TextCleaner()
    assert cleaner.clean_text("Oak St address") == "oak st address"


def test_punctuation_repeated_exclamation():
    cleaner = TextCleaner()
    assert cleaner.normalize_punctuation("Great!!!  pool/spa") == "Great. pool spa"


def test_punctuation_semicolon_colon():
    cleaner = TextCleaner()
    assert cleaner.normalize_punctuation("kitchen; dining: patio") == "kitchen, dining, patio"


def test_punctuation_dash_spacing():
    cleaner = TextCleaner()
    assert cleaner.normalize_punctuation("move - in ready") == "move in ready"


def test_whitespace_cleanup():
    cleaner = TextCleaner()
    assert cleaner.normalize_whitespace("  too    many   spaces  ") == "too many spaces"


def test_clean_text_full_listing_example():
    cleaner = TextCleaner()
    text = "<p>Beautiful 3BR/2BA home w/ 2,000 sqft &amp; SS appls!</p>"
    expected = "beautiful 3 bedroom 2 bathroom home with 2000 square feet stainless steel appliances"
    assert cleaner.clean_text(text) == expected


def test_clean_text_year_story_hoa_example():
    cleaner = TextCleaner()
    text = "Yr blt 2005, single-story, HOA $450/mo."
    expected = "year built 2005, 1 story, homeowners association fee 450 per month."
    assert cleaner.clean_text(text) == expected


def test_clean_text_property_feature_example():
    cleaner = TextCleaner()
    text = "$1.25M SFH w/ att gar, bkyd, and elem sch nearby."
    expected = "1250000 single family home with attached garage, backyard, and elementary school nearby."
    assert cleaner.clean_text(text) == expected


def test_clean_text_none():
    cleaner = TextCleaner()
    assert cleaner.clean_text(None) == ""


def test_clean_dataframe_adds_cleaned_column():
    cleaner = TextCleaner()
    df = pd.DataFrame(
        {
            "listing_id": [1, 2],
            "remarks": ["3br home w/ pool", "HOA $300/mo and 2-car garage"],
        }
    )

    cleaned = cleaner.clean_dataframe(df)

    assert "remarks_cleaned" in cleaned.columns
    assert cleaned.loc[0, "remarks_cleaned"] == "3 bedroom home with pool"
    assert cleaned.loc[1, "remarks_cleaned"] == "homeowners association fee 300 per month and 2 car garage"
    assert "remarks_cleaned" not in df.columns


def test_profile_column_returns_expected_metrics():
    cleaner = TextCleaner()
    df = pd.DataFrame(
        {
            "remarks": [
                "<p>3br home w/ pool listed at $750k</p>",
                "2ba condo with HOA $400/mo",
                None,
            ]
        }
    )

    profile = cleaner.profile_column(df, "remarks")

    assert profile["null_rate"] == pytest.approx(1 / 3)
    assert profile["price_mentions"] == 2
    assert profile["has_html"] == 1
    assert profile["avg_length"] > 0
    assert profile["common_terms"]
    assert profile["common_abbreviations"]


def test_abbreviation_dictionary_has_required_size():
    cleaner = TextCleaner()
    assert len(cleaner.abbrev_map) >= 30


def test_cleaner_has_required_normalization_methods():
    cleaner = TextCleaner()
    normalize_methods = [
        name for name in dir(cleaner)
        if name.startswith("normalize_")
    ]
    assert len(normalize_methods) >= 6


def test_clean_text_preserves_bedroom_number():
    cleaner = TextCleaner()
    assert "4 bedroom" in cleaner.clean_text("4br/3ba, 2,400 sqft, built in 2019, $950k")


def test_clean_text_preserves_bathroom_number():
    cleaner = TextCleaner()
    assert "3 bathroom" in cleaner.clean_text("4br/3ba, 2,400 sqft, built in 2019, $950k")


def test_clean_text_preserves_square_feet():
    cleaner = TextCleaner()
    assert "2400 square feet" in cleaner.clean_text("4br/3ba, 2,400 sqft, built in 2019, $950k")


def test_clean_text_preserves_year_built():
    cleaner = TextCleaner()
    assert "year built 2019" in cleaner.clean_text("4br/3ba, 2,400 sqft, built in 2019, $950k")


def test_clean_text_preserves_price():
    cleaner = TextCleaner()
    assert "950000" in cleaner.clean_text("4br/3ba, 2,400 sqft, built in 2019, $950k")
