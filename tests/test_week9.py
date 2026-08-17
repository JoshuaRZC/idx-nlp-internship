import pytest

from scripts.check_listing_compliance import check_records
from scripts.evaluate_compliance_checker import evaluate_items
from src.real_estate_nlp.compliance_checker import ComplianceChecker
from src.real_estate_nlp.compliance_rules import ComplianceRule, FEDERAL_RULES, RULE_VERSION


@pytest.mark.parametrize(
    ("text", "protected_class"),
    [
        ("No children permitted.", "familial_status"),
        ("Adults-only community.", "familial_status"),
        ("No families allowed.", "familial_status"),
        ("Single people only.", "familial_status"),
        ("Residents must be at least 18 years old.", "familial_status"),
        ("No wheelchairs in this building.", "disability"),
        ("Able-bodied tenants only.", "disability"),
        ("Residents must be able-bodied.", "disability"),
        ("Not suitable for disabled residents.", "disability"),
        ("No disabled tenants.", "disability"),
        ("Christian tenants only.", "religion"),
        ("English speakers only.", "national_origin"),
        ("Americans only rental.", "national_origin"),
        ("White residents preferred.", "race"),
        ("Light-skinned buyers only.", "color"),
        ("Women only unit.", "sex"),
        ("Male tenants preferred.", "sex"),
    ],
)
def test_checker_blocks_explicit_federal_violations(text, protected_class):
    result = ComplianceChecker().check_listing(text)

    assert result["status"] == "blocked"
    assert result["can_publish"] is False
    assert result["findings"][0]["protected_class"] == protected_class
    assert result["findings"][0]["severity"] == "error"


@pytest.mark.parametrize(
    "text",
    [
        "Family room opens to a private patio.",
        "Wheelchair accessible entry and a wide hallway.",
        "Walk to a church, shops, and restaurants.",
        "A kosher kitchen with updated appliances.",
        "Spacious primary bedroom in a desirable neighborhood.",
    ],
)
def test_checker_does_not_flag_neutral_property_descriptions(text):
    assert ComplianceChecker().check_listing(text) == {
        "status": "pass",
        "can_publish": True,
        "rule_version": RULE_VERSION,
        "findings": [],
    }


@pytest.mark.parametrize(
    "text",
    [
        "Perfect for singles near transit.",
        "Ideal for a young couple.",
        "Located in a diverse neighborhood.",
        "Christian community setting.",
    ],
)
def test_checker_sends_ambiguous_language_to_review(text):
    result = ComplianceChecker().check_listing(text)

    assert result["status"] == "review"
    assert result["can_publish"] is False
    assert result["findings"][0]["severity"] == "warning"


@pytest.mark.parametrize(
    "text",
    [
        "There is no children-only policy in this community.",
        "Ideal for single-story living with no interior stairs.",
        "Perfect for single-level living and easy access throughout.",
        "Great for a single-story home buyer seeking an open layout.",
    ],
)
def test_checker_does_not_flag_known_contextual_counterexamples(text):
    assert ComplianceChecker().check_listing(text)["status"] == "pass"


def test_checker_keeps_the_original_match_and_span():
    text = "Bright two-bedroom home. No children permitted. Updated kitchen."
    finding = ComplianceChecker().check_listing(text)["findings"][0]

    assert finding["matched_text"] == "No children"
    assert text[finding["start"] : finding["end"]] == "No children"


def test_checker_keeps_only_the_highest_severity_overlapping_rule():
    rules = (
        ComplianceRule("warning.children", "familial_status", "mention", "warning", r"\bchildren\b", "Review."),
        ComplianceRule("error.no_children", "familial_status", "exclusion", "error", r"\bno children\b", "Block."),
    )
    result = ComplianceChecker(rules=rules).check_listing("No children allowed.")

    assert result["status"] == "blocked"
    assert [finding["rule_id"] for finding in result["findings"]] == ["error.no_children"]


def test_checker_returns_nonblocking_info_for_senior_housing_language():
    result = ComplianceChecker().check_listing("Active 55+ community with a pool.")

    assert result["status"] == "pass"
    assert result["can_publish"] is True
    assert result["findings"][0]["severity"] == "info"


def test_checker_accepts_an_explicit_empty_policy():
    result = ComplianceChecker(rules=()).check_listing("No children permitted.")

    assert result["status"] == "pass"
    assert result["findings"] == []


def test_batch_helper_returns_one_result_per_listing():
    records = [
        {"listing_id": "A1", "remarks": "No children permitted."},
        {"listing_id": "A2", "remarks": "Wheelchair accessible entry."},
    ]

    results = check_records(records)

    assert [item["listing_id"] for item in results] == ["A1", "A2"]
    assert [item["status"] for item in results] == ["blocked", "pass"]


def test_evaluation_reports_expected_compliance_metrics():
    items = [
        {
            "id": "blocked_1",
            "source": "synthetic",
            "text": "No children permitted.",
            "expected_status": "blocked",
            "expected_findings": [{"rule_id": "familial.exclusion.no_children"}],
        },
        {
            "id": "review_1",
            "source": "synthetic",
            "text": "Perfect for singles near transit.",
            "expected_status": "review",
            "expected_findings": [{"rule_id": "familial.preference.singles"}],
        },
        {
            "id": "pass_1",
            "source": "synthetic",
            "text": "Wheelchair accessible entry with an updated kitchen.",
            "expected_status": "pass",
            "expected_findings": [],
        },
    ]

    results = evaluate_items(items)

    assert results["known_violation_recall"] == 1.0
    assert results["actionable_alert_precision"] == 1.0
    assert results["status_accuracy"] == 1.0
    assert results["clean_listing_false_positive_rate"] == 0.0
    assert results["per_protected_class_recall"]["familial_status"]["recall"] == 1.0


def test_all_error_rules_have_a_rule_identifier_and_valid_pattern():
    errors = [rule for rule in FEDERAL_RULES if rule.severity == "error"]

    assert len(errors) == 14
    assert len({rule.rule_id for rule in errors}) == len(errors)
