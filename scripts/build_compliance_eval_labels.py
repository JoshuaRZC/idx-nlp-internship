import argparse
import json
from pathlib import Path

import pandas as pd


SENSITIVE_CANDIDATE_TERMS = (
    r"\b(?:children?|kids?|adults?|famil(?:y|ies)|singles?|couples?|women|men|male|female|"
    r"christian|catholic|jewish|muslim|hindu|buddhist|english\s+speakers?|americans?|"
    r"foreigners?|immigrants?|white|black|asian|hispanic|latino|latina|light[- ]skinned|"
    r"dark[- ]skinned|diverse|ethnic|senior|disabled|wheelchairs?)\b|(?:55|62)\+"
)


ERROR_EXAMPLES = {
    "familial.exclusion.no_children": [
        "No children permitted in this building.",
        "Quiet unit: no kids.",
        "NO CHILD allowed.",
        "No children, please.",
        "No child residents.",
        "No kids allowed.",
        "No children in the community.",
        "No children accepted.",
    ],
    "familial.exclusion.adults_only": [
        "Adults only residence.",
        "Adult-only community.",
        "This home is for adults only.",
        "ADULTS ONLY building.",
        "Adults-only living.",
        "Adult only occupancy.",
        "Quiet adults only unit.",
        "Adults only, please.",
    ],
    "familial.exclusion.no_families": [
        "No families allowed.",
        "This rental accepts no family.",
        "NO FAMILIES in this unit.",
        "No family households.",
        "No families, please.",
        "No family occupancy.",
        "No family residents.",
        "No families permitted.",
    ],
    "disability.exclusion.wheelchairs": [
        "No wheelchairs in the building.",
        "This unit allows no wheelchair access.",
        "NO WHEELCHAIR users.",
        "No wheelchair residents.",
        "No wheelchairs allowed.",
        "No wheelchair use.",
        "No wheelchairs, please.",
        "No wheelchair tenants.",
    ],
    "disability.exclusion.able_bodied": [
        "Able-bodied tenants only.",
        "Must be able bodied residents.",
        "Able bodied only occupancy.",
        "Able-bodied only home.",
        "Must be able-bodied tenants.",
        "Able bodied residents only.",
        "Able-bodied tenants preferred.",
        "Able bodied tenants only.",
    ],
    "disability.exclusion.not_suitable": [
        "Not suitable for the disabled.",
        "This home is not available for disabled residents.",
        "Not suitable for disabled tenants.",
        "Not available for the disabled.",
        "Not suitable for the disabled occupant.",
        "Not available for disabled people.",
        "Not suitable for disabled residents.",
        "Not available for the disabled tenant.",
    ],
    "disability.exclusion.no_disabled_residents": [
        "No disabled residents.",
        "No disabled tenants allowed.",
        "NO DISABLED occupants.",
        "No disability residents.",
        "No disabled tenant occupancy.",
        "No disabled residents, please.",
        "No disability tenants.",
        "No disabled occupants allowed.",
    ],
    "religion.preference.religion_only": [
        "Christian only home.",
        "Catholic residents preferred.",
        "Jewish only rental.",
        "Muslim preferred community.",
        "Hindu only household.",
        "Buddhist residents preferred.",
        "Christian tenants only.",
        "Jewish buyers preferred.",
    ],
    "national_origin.exclusion.english_only": [
        "English speakers only.",
        "This unit is for English speaker only.",
        "ENGLISH SPEAKERS ONLY building.",
        "English speaker only tenancy.",
        "English speakers only, please.",
        "English speakers only occupancy.",
        "English speaker only residents.",
        "English speakers only rental.",
    ],
    "national_origin.exclusion.nationals_only": [
        "Americans only rental.",
        "Foreigners only unit.",
        "Immigrants only home.",
        "American only tenants.",
        "Foreigners only occupancy.",
        "Immigrants only residents.",
        "Americans only, please.",
        "Foreigners only community.",
    ],
    "race_color.exclusion.racial_preference": [
        "White only home.",
        "Black residents preferred.",
        "Asian only unit.",
        "Hispanic buyers preferred.",
        "Latino only rental.",
        "Latina tenants preferred.",
        "White tenants only.",
        "Asian residents preferred.",
    ],
    "color.exclusion.color_preference": [
        "Light-skinned only home.",
        "Dark skinned residents preferred.",
        "Light skinned only unit.",
        "Dark-skinned tenants preferred.",
        "Light-skinned residents only.",
        "Dark skinned only rental.",
        "Light skinned buyers preferred.",
        "Dark-skinned only occupancy.",
    ],
    "sex.exclusion.sex_only": [
        "Women only unit.",
        "Men preferred rental.",
        "Female only occupancy.",
        "Male tenants preferred.",
        "Women preferred home.",
        "Men only residence.",
        "Female residents only.",
        "Male only rental.",
    ],
}

WARNING_EXAMPLES = {
    "familial.preference.singles": [
        "Perfect for singles near downtown.",
        "Ideal for a single professional.",
        "Great for singles who commute.",
        "Perfect for a single resident.",
        "Ideal for singles seeking convenience.",
        "Great for a single occupant.",
        "Perfect for singles with a short commute.",
    ],
    "familial.preference.young_couple": [
        "Perfect for a young couple.",
        "Ideal for young couples.",
        "Great for a young couple starting out.",
        "Perfect for young couples who entertain.",
        "Ideal for a young couple near downtown.",
        "Great for young couples.",
        "Perfect for a young couple seeking convenience.",
    ],
    "religion.neighborhood.religious_community": [
        "Located in a Christian community.",
        "Peaceful Jewish neighborhood.",
        "Muslim community setting.",
        "Catholic neighborhood nearby.",
        "Hindu community location.",
        "Buddhist neighborhood setting.",
        "Christian neighborhood atmosphere.",
    ],
    "national_origin.neighborhood.ethnic": [
        "Located in an ethnic community.",
        "Immigrant neighborhood location.",
        "Ethnic area near downtown.",
        "Immigrant community setting.",
        "Ethnic neighborhood with shops.",
        "Immigrant area close to transit.",
        "Ethnic community nearby.",
    ],
    "race_color.neighborhood.demographic_claim": [
        "Located in a white neighborhood.",
        "Black community location.",
        "Asian neighborhood nearby.",
        "Hispanic community setting.",
        "Latino area close to shops.",
        "Latina neighborhood location.",
        "White community near downtown.",
    ],
    "race_color.neighborhood.diverse": [
        "Located in a diverse neighborhood.",
        "Diverse community near transit.",
        "A diverse area with parks.",
        "Diverse neighborhood setting.",
        "Diverse community with restaurants.",
        "Diverse area near downtown.",
        "Diverse neighborhood close to schools.",
    ],
    "sex.preference.occupant": [
        "Perfect for women who commute.",
        "Ideal for men seeking convenience.",
        "Great for women near downtown.",
        "Perfect for men who travel.",
        "Ideal for women with a short commute.",
        "Great for men seeking a quiet home.",
        "Perfect for women who work nearby.",
    ],
}


ADDITIONAL_EVALUATION_CASES = (
    {
        "text": "Children are not permitted in this residence.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_children"],
    },
    {
        "text": "This home is not available to families with children.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_families"],
    },
    {
        "text": "Residents must be at least 18 years old.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.adults_only"],
    },
    {
        "text": "Adult residents are preferred for this unit.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.adults_only"],
    },
    {
        "text": "Applicants must be physically fit to occupy this home.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.able_bodied"],
    },
    {
        "text": "This property cannot accommodate wheelchair users.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.wheelchairs"],
    },
    {
        "text": "Not appropriate for people with disabilities.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.not_suitable"],
    },
    {
        "text": "Christian applicants are welcome only.",
        "expected_status": "blocked",
        "rule_ids": ["religion.preference.religion_only"],
    },
    {
        "text": "Rental is restricted to English-speaking tenants.",
        "expected_status": "blocked",
        "rule_ids": ["national_origin.exclusion.english_only"],
    },
    {
        "text": "U.S. citizens only.",
        "expected_status": "blocked",
        "rule_ids": ["national_origin.exclusion.nationals_only"],
    },
    {
        "text": "Preference will be given to white applicants.",
        "expected_status": "blocked",
        "rule_ids": ["race_color.exclusion.racial_preference"],
    },
    {
        "text": "Light-skinned applicants are preferred.",
        "expected_status": "blocked",
        "rule_ids": ["color.exclusion.color_preference"],
    },
    {
        "text": "Female applicants only.",
        "expected_status": "blocked",
        "rule_ids": ["sex.exclusion.sex_only"],
    },
    {
        "text": "No teenagers, please.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_children"],
    },
    {
        "text": "Single people only.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.single_people_only"],
    },
    {
        "text": "Best suited to one person.",
        "expected_status": "review",
        "rule_ids": ["familial.preference.singles"],
    },
    {
        "text": "Geared toward young newlyweds.",
        "expected_status": "review",
        "rule_ids": ["familial.preference.young_couple"],
    },
    {
        "text": "A community popular with Christian residents.",
        "expected_status": "review",
        "rule_ids": ["religion.neighborhood.religious_community"],
    },
    {
        "text": "A neighborhood known for its immigrant population.",
        "expected_status": "review",
        "rule_ids": ["national_origin.neighborhood.ethnic"],
    },
    {
        "text": "A neighborhood with a large Asian population.",
        "expected_status": "review",
        "rule_ids": ["race_color.neighborhood.demographic_claim"],
    },
    {
        "text": "Especially convenient for women living alone.",
        "expected_status": "review",
        "rule_ids": ["sex.preference.occupant"],
    },
    {
        "text": "A diverse and welcoming place to live.",
        "expected_status": "review",
        "rule_ids": ["race_color.neighborhood.diverse"],
    },
    {
        "text": "An active 55-and-over housing community.",
        "expected_status": "pass",
        "rule_ids": ["familial.exception.senior_housing"],
    },
    {
        "text": "Verified senior housing community with a pool.",
        "expected_status": "pass",
        "rule_ids": ["familial.exception.senior_housing"],
    },
    {
        "text": "Recently updated two-bedroom unit near transit. Please note that children are not permitted in the building. New flooring and parking included.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_children"],
    },
    {
        "text": "Bright upstairs condo with a renovated kitchen and balcony. Because of the stairs, wheelchair users should not apply.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.wheelchairs"],
    },
    {
        "text": "Quiet home with a large yard and garden. Residents must be physically fit to occupy the property.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.able_bodied"],
    },
    {
        "text": "This renovated cottage has a private patio and updated appliances. The landlord gives preference to Christian tenants.",
        "expected_status": "blocked",
        "rule_ids": ["religion.preference.religion_only"],
    },
    {
        "text": "Freshly painted one-bedroom home close to restaurants. English-speaking households only, please.",
        "expected_status": "blocked",
        "rule_ids": ["national_origin.exclusion.english_only"],
    },
    {
        "text": "Updated kitchen, fenced yard, and attached garage. Preference is given to white buyers.",
        "expected_status": "blocked",
        "rule_ids": ["race_color.exclusion.racial_preference"],
    },
    {
        "text": "Open-plan condo close to rail and shopping. The quiet building is ideal for a single professional.",
        "expected_status": "review",
        "rule_ids": ["familial.preference.singles"],
    },
    {
        "text": "New flooring, private patio, and covered parking. The layout is best suited to a young couple.",
        "expected_status": "review",
        "rule_ids": ["familial.preference.young_couple"],
    },
    {
        "text": "Well-maintained home near shopping and transit, in a neighborhood known locally as an immigrant neighborhood.",
        "expected_status": "review",
        "rule_ids": ["national_origin.neighborhood.ethnic"],
    },
    {
        "text": "Move-in-ready home with solar panels and a covered patio, located in a diverse, welcoming community.",
        "expected_status": "review",
        "rule_ids": ["race_color.neighborhood.diverse"],
    },
    {
        "text": "Updated home with a family room, quartz counters, and a fenced backyard. Walk to parks, shops, and transit.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Single-level home with a wheelchair ramp, wide entry, and accessible bathroom. Near a church and local shops.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Bright condo near a synagogue and restaurants, with a primary suite, in-unit laundry, and covered parking.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Classic home with a primary bedroom, updated kitchen, and mature landscaping. The floor plan supports single-story living.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Active 55+ community with clubhouse access, pool, and landscaped walking paths.",
        "expected_status": "pass",
        "rule_ids": ["familial.exception.senior_housing"],
    },
    {
        "text": "Two-bedroom home with an updated bath and garage. The unit is not suitable for disabled renters.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.not_suitable"],
    },
    {
        "text": "Freshly updated apartment near downtown. Women-only renters, please.",
        "expected_status": "blocked",
        "rule_ids": ["sex.exclusion.sex_only"],
    },
    {
        "text": "Private yard and remodeled kitchen. No families are permitted in this rental.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_families"],
    },
    {
        "text": "Spacious townhome with a balcony and garage, located in a Catholic neighborhood near downtown.",
        "expected_status": "review",
        "rule_ids": ["religion.neighborhood.religious_community"],
    },
    {
        "text": "Quiet street with mature trees, a private patio, and a family room that opens to the kitchen.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "No children permitted. Christian tenants only.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_children", "religion.preference.religion_only"],
    },
    {
        "text": "Wheelchair accessible entrance and wide hallway, but no wheelchair users.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.wheelchairs"],
    },
    {
        "text": "No families allowed. Ideal for singles.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_families", "familial.preference.singles"],
    },
    {
        "text": "Christian community setting. English speakers only.",
        "expected_status": "blocked",
        "rule_ids": ["religion.neighborhood.religious_community", "national_origin.exclusion.english_only"],
    },
    {
        "text": "Diverse community with parks, ideal for a young couple.",
        "expected_status": "review",
        "rule_ids": ["race_color.neighborhood.diverse", "familial.preference.young_couple"],
    },
    {
        "text": "White neighborhood near transit, perfect for a single resident.",
        "expected_status": "review",
        "rule_ids": ["race_color.neighborhood.demographic_claim", "familial.preference.singles"],
    },
    {
        "text": "Active senior community. No children allowed.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exception.senior_housing", "familial.exclusion.no_children"],
    },
    {
        "text": "Family room with fireplace and a private patio. No families permitted.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_families"],
    },
    {
        "text": "Walk to a church and local shops. Christian tenants preferred.",
        "expected_status": "blocked",
        "rule_ids": ["religion.preference.religion_only"],
    },
    {
        "text": "Wheelchair ramp at the front entry. Residents must be able-bodied.",
        "expected_status": "blocked",
        "rule_ids": ["disability.exclusion.able_bodied"],
    },
    {
        "text": "55+ community with pool access. English speakers only.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exception.senior_housing", "national_origin.exclusion.english_only"],
    },
    {
        "text": "Great for women who commute and ideal for singles seeking convenience.",
        "expected_status": "review",
        "rule_ids": ["sex.preference.occupant", "familial.preference.singles"],
    },
    {
        "text": "A diverse community, perfect for singles and women working nearby.",
        "expected_status": "review",
        "rule_ids": ["race_color.neighborhood.diverse", "familial.preference.singles", "sex.preference.occupant"],
    },
    {
        "text": "No children or disabled tenants.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.no_children", "disability.exclusion.no_disabled_residents"],
    },
    {
        "text": "Adult-only home. Men preferred.",
        "expected_status": "blocked",
        "rule_ids": ["familial.exclusion.adults_only", "sex.exclusion.sex_only"],
    },
    {
        "text": "Family room, white cabinetry, and a private patio. Women-only renters.",
        "expected_status": "blocked",
        "rule_ids": ["sex.exclusion.sex_only"],
    },
    {
        "text": "Family room opens to the patio and backyard.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Flexible, family-friendly floor plan with a large kitchen island.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "A welcoming home for families with children, featuring a fenced yard.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "No-smoking and no-pet policy. Updated flooring throughout.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "There is no children-only policy in this community.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Wheelchair ramp and accessible entry at the front of the home.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Accessible bathroom and wide hallway in this single-level home.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Conveniently located near a church, park, and grocery store.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Walk to the synagogue, restaurants, and public transportation.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Kitchen includes a kosher prep area and updated appliances.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "White cabinetry and black stainless appliances in the kitchen.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Asian-inspired landscaping frames the front entry.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "A diverse selection of floor plans is available in the development.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Close to ethnic restaurants, markets, and transit.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Senior center and library are nearby.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Ideal for single-story living with no interior stairs.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Perfect for single-level living and easy access throughout.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Great for a single-story home buyer seeking an open layout.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Adults will appreciate the mature landscaping and private garden.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Women’s clinic and pharmacy are a short walk away.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Christian Street is two blocks away, with shops and cafes nearby.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "The commute is about 55 minutes in typical traffic.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "This listing does not restrict families from applying.",
        "expected_status": "pass",
        "rule_ids": [],
    },
    {
        "text": "Private courtyard, mature trees, and a quiet street near shopping.",
        "expected_status": "pass",
        "rule_ids": [],
    },
)


def parse_args():
    parser = argparse.ArgumentParser(description="Create a Fair Housing evaluation-label scaffold.")
    parser.add_argument("--source", default="data/processed/listing_semantic_sample_10k.csv")
    parser.add_argument("--output", default="data/processed/compliance_eval_labels.json")
    parser.add_argument("--real-neutral-count", type=int, default=60)
    parser.add_argument("--mark-mls-reviewed", action="store_true")
    return parser.parse_args()


def synthetic_items(examples, status, limits):
    items = []
    for index, (rule_id, texts) in enumerate(examples.items()):
        for text in texts[:limits[index]]:
            items.append(
                {
                    "id": f"compliance_{len(items) + 1:04d}",
                    "source": "synthetic",
                    "text": text,
                    "expected_status": status,
                    "expected_findings": [{"rule_id": rule_id}],
                    "annotation_status": "complete",
                }
            )
    return items


def neutral_candidates(source, count, reviewed=False):
    frame = pd.read_csv(source)
    remarks = frame["remarks"].fillna("").astype(str).str.strip()
    candidates = frame.loc[remarks.str.len().between(80, 700), ["listing_id", "remarks"]].copy()
    candidates = candidates[~candidates["remarks"].str.contains(SENSITIVE_CANDIDATE_TERMS, case=False, regex=True)]
    candidates = candidates.sample(n=min(count, len(candidates)), random_state=42)
    return [
        {
            "source": "mls_neutral" if reviewed else "mls_neutral_candidate",
            "listing_id": str(row.listing_id),
            "text": row.remarks,
            "expected_status": "pass",
            "expected_findings": [],
            "annotation_status": "complete" if reviewed else "review_required",
        }
        for row in candidates.itertuples(index=False)
    ]


def additional_evaluation_items():
    return [
        {
            "source": "synthetic",
            "text": case["text"],
            "expected_status": case["expected_status"],
            "expected_findings": [{"rule_id": rule_id} for rule_id in case["rule_ids"]],
            "annotation_status": "complete",
        }
        for case in ADDITIONAL_EVALUATION_CASES
    ]


def build_items(source, real_neutral_count, reviewed=False):
    items = synthetic_items(ERROR_EXAMPLES, "blocked", [6] * 7 + [5] * 6)
    items += synthetic_items(WARNING_EXAMPLES, "review", [7, 7, 7, 7, 7, 7, 6])
    items += additional_evaluation_items()
    for item in neutral_candidates(source, real_neutral_count, reviewed):
        items.append(item)
    for index, item in enumerate(items, start=1):
        item["id"] = f"compliance_{index:04d}"
    return items


def main():
    args = parse_args()
    items = build_items(args.source, args.real_neutral_count, args.mark_mls_reviewed)
    payload = {
        "items": items,
        "annotation_rules": {
            "blocked": "An explicit preference, limitation, or exclusion tied to a protected class.",
            "review": "A phrase that needs human compliance review before publication.",
            "pass": "A neutral property description with no compliance finding.",
            "mls_review": "Review each MLS candidate before changing annotation_status to complete.",
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} label items to {output}")


if __name__ == "__main__":
    main()
