"""Federal Fair Housing advertising rules used by the compliance checker."""

from dataclasses import dataclass


RULE_VERSION = "federal-1.1"


@dataclass(frozen=True)
class ComplianceRule:
    """One review rule for housing advertising language."""

    rule_id: str
    protected_class: str
    risk_type: str
    severity: str
    pattern: str
    message: str


FEDERAL_RULES = (
    ComplianceRule(
        "familial.exclusion.no_children",
        "familial_status",
        "explicit_exclusion",
        "error",
        r"\bno\s+(?:child(?:ren)?|kids?|teenagers?)\b(?![- ]only\s+policy)"
        r"|\b(?:child(?:ren)?|kids?|teenagers?)\s+(?:are\s+)?not\s+(?:permitted|allowed|accepted)\b",
        "This wording excludes families with children.",
    ),
    ComplianceRule(
        "familial.exclusion.adults_only",
        "familial_status",
        "explicit_exclusion",
        "error",
        r"\badults?\s*[- ]?only\b"
        r"|\b(?:adult|adults)\s+(?:residents?|tenants?)\s+(?:are\s+)?preferred\b"
        r"|\b(?:residents?|tenants?)\s+must\s+be\s+(?:at\s+least\s+)?(?:18|eighteen)"
        r"(?:\s+years?\s+old)?\b",
        "This wording restricts the listing to adults.",
    ),
    ComplianceRule(
        "familial.exclusion.single_people_only",
        "familial_status",
        "explicit_exclusion",
        "error",
        r"\bsingle\s+people\s+only\b",
        "This wording restricts occupancy by household type.",
    ),
    ComplianceRule(
        "familial.exclusion.no_families",
        "familial_status",
        "explicit_exclusion",
        "error",
        r"\bno\s+famil(?:y|ies)\b|\bnot\s+available\s+to\s+famil(?:y|ies)(?:\s+with\s+children)?\b",
        "This wording excludes families.",
    ),
    ComplianceRule(
        "familial.preference.singles",
        "familial_status",
        "occupant_preference",
        "warning",
        r"\b(?:perfect|ideal|great)\s+for\s+(?:a\s+)?"
        r"(?:single(?:s)?(?![- ](?:story|level))\b|"
        r"single(?![- ](?:story|level))\s+(?:professional|resident|occupant))"
        r"|\bbest\s+suited\s+to\s+(?:a\s+)?(?:one\s+person|"
        r"single(?![- ](?:story|level))\s+(?:professional|resident|occupant))\b",
        "Avoid describing a preferred type of resident.",
    ),
    ComplianceRule(
        "familial.preference.young_couple",
        "familial_status",
        "occupant_preference",
        "warning",
        r"\b(?:perfect|ideal|great)\s+for\s+(?:a\s+)?young\s+couples?\b"
        r"|\bbest\s+suited\s+to\s+(?:a\s+)?young\s+couples?\b"
        r"|\bgeared\s+toward\s+young\s+newlyweds?\b",
        "Avoid describing a preferred type of resident.",
    ),
    ComplianceRule(
        "disability.exclusion.wheelchairs",
        "disability",
        "explicit_exclusion",
        "error",
        r"\bno\s+wheelchairs?\b"
        r"|\b(?:cannot|can't|unable\s+to)\s+(?:accommodate|accept)\s+"
        r"wheelchair\s+(?:users?|residents?|tenants?)\b"
        r"|\bwheelchair\s+(?:users?|residents?|tenants?)\s+should\s+not\s+apply\b",
        "This wording excludes people with disabilities.",
    ),
    ComplianceRule(
        "disability.exclusion.able_bodied",
        "disability",
        "explicit_exclusion",
        "error",
        r"\b(?:applicants?|residents?|tenants?)\s+must\s+be\s+"
        r"(?:able[- ]?bodied|physically\s+fit)\b"
        r"|\bable[- ]?bodied\s+(?:only|tenants?|residents?)\b",
        "This wording restricts housing based on disability.",
    ),
    ComplianceRule(
        "disability.exclusion.not_suitable",
        "disability",
        "explicit_exclusion",
        "error",
        r"\bnot\s+(?:suitable|available|appropriate)\s+(?:for|to)\s+(?:the\s+)?"
        r"(?:disabled|people\s+with\s+disabilities|disabled\s+(?:people|residents?|renters?|tenants?|occupants?))\b",
        "This wording excludes people with disabilities.",
    ),
    ComplianceRule(
        "disability.exclusion.no_disabled_residents",
        "disability",
        "explicit_exclusion",
        "error",
        r"\bno\s+(?:disabled|disability)\s+(?:residents?|tenants?|occupants?)\b"
        r"|\bno\s+(?:child(?:ren)?|kids?|teenagers?)\s+or\s+disabled\s+"
        r"(?:residents?|tenants?|occupants?)\b",
        "This wording excludes people with disabilities.",
    ),
    ComplianceRule(
        "religion.preference.religion_only",
        "religion",
        "explicit_preference",
        "error",
        r"\b(?:christian|catholic|jewish|muslim|hindu|buddhist)\s+"
        r"(?:(?:tenants?|residents?|buyers?|occupants?|applicants?)\s+)?(?:are\s+)?(?:only|preferred)\b"
        r"|\b(?:christian|catholic|jewish|muslim|hindu|buddhist)\s+"
        r"(?:applicants?|tenants?|residents?|buyers?|occupants?)\s+(?:are\s+)?welcome\s+only\b"
        r"|\b(?:preference\s+(?:will\s+be\s+|is\s+)?given|gives?\s+preference)\s+to\s+"
        r"(?:christian|catholic|jewish|muslim|hindu|buddhist)\s+"
        r"(?:tenants?|residents?|buyers?|occupants?|applicants?)\b",
        "This wording expresses a religious preference.",
    ),
    ComplianceRule(
        "religion.neighborhood.religious_community",
        "religion",
        "neighborhood_demographic_claim",
        "warning",
        r"\b(?:christian|catholic|jewish|muslim|hindu|buddhist)\s+(?:community|neighborhood)\b"
        r"|\b(?:community|neighborhood)\s+popular\s+with\s+"
        r"(?:christian|catholic|jewish|muslim|hindu|buddhist)\s+residents?\b",
        "Avoid describing neighborhood residents by religion.",
    ),
    ComplianceRule(
        "national_origin.exclusion.english_only",
        "national_origin",
        "explicit_exclusion",
        "error",
        r"\benglish\s+speakers?\s+only\b"
        r"|\benglish[- ]speaking\s+(?:tenants?|households?|residents?|renters?|applicants?)\s+only\b"
        r"|\brestricted\s+to\s+english[- ]speaking\s+"
        r"(?:tenants?|households?|residents?|renters?|applicants?)\b",
        "This wording may restrict housing based on national origin.",
    ),
    ComplianceRule(
        "national_origin.exclusion.nationals_only",
        "national_origin",
        "explicit_exclusion",
        "error",
        r"\b(?:americans?|foreigners?|immigrants?|u\.?s\.?\s+citizens?)\s+only\b",
        "This wording restricts housing based on national origin.",
    ),
    ComplianceRule(
        "national_origin.neighborhood.ethnic",
        "national_origin",
        "neighborhood_demographic_claim",
        "warning",
        r"\b(?:ethnic|immigrant)\s+(?:community|neighborhood|area)\b"
        r"|\b(?:community|neighborhood|area)\s+known(?:\s+locally)?\s+as\s+an?\s+"
        r"(?:ethnic|immigrant)\s+(?:community|neighborhood|area)\b"
        r"|\b(?:community|neighborhood|area)\s+known\s+for\s+(?:its\s+)?"
        r"(?:ethnic|immigrant)\s+population\b",
        "Avoid describing neighborhood residents by national origin.",
    ),
    ComplianceRule(
        "race_color.exclusion.racial_preference",
        "race",
        "explicit_preference",
        "error",
        r"\b(?:white|black|asian|hispanic|latino|latina)\s+"
        r"(?:(?:tenants?|residents?|buyers?|occupants?|applicants?)\s+)?(?:are\s+)?(?:only|preferred)\b"
        r"|\b(?:preference\s+(?:will\s+be\s+|is\s+)?given|gives?\s+preference)\s+to\s+"
        r"(?:white|black|asian|hispanic|latino|latina)\s+"
        r"(?:tenants?|residents?|buyers?|occupants?|applicants?)\b",
        "This wording expresses a racial preference.",
    ),
    ComplianceRule(
        "color.exclusion.color_preference",
        "color",
        "explicit_preference",
        "error",
        r"\b(?:light|dark)[- ]skinned\s+"
        r"(?:(?:tenants?|residents?|buyers?|occupants?|applicants?)\s+)?(?:are\s+)?(?:only|preferred)\b",
        "This wording expresses a color-based preference.",
    ),
    ComplianceRule(
        "race_color.neighborhood.demographic_claim",
        "race",
        "neighborhood_demographic_claim",
        "warning",
        r"\b(?:white|black|asian|hispanic|latino|latina)\s+(?:community|neighborhood|area)\b"
        r"|\b(?:community|neighborhood|area)\s+with\s+(?:a\s+)?(?:large\s+)?"
        r"(?:white|black|asian|hispanic|latino|latina)\s+population\b",
        "Avoid describing neighborhood residents by race or ethnicity.",
    ),
    ComplianceRule(
        "race_color.neighborhood.diverse",
        "race",
        "neighborhood_demographic_claim",
        "warning",
        r"\bdiverse\s+(?:community|neighborhood|area)\b"
        r"|\bdiverse\s*,?\s+(?:welcoming\s+)?community\b"
        r"|\bdiverse\s+and\s+welcoming\s+place\s+to\s+live\b",
        "Avoid describing neighborhood residents by demographic composition.",
    ),
    ComplianceRule(
        "sex.exclusion.sex_only",
        "sex",
        "explicit_exclusion",
        "error",
        r"\b(?:women|men|female|male)(?:[- ]only\b|\s+"
        r"(?:(?:tenants?|residents?|buyers?|occupants?|renters?|applicants?)\s+)?"
        r"(?:are\s+)?(?:only|preferred)\b)",
        "This wording expresses a sex-based preference.",
    ),
    ComplianceRule(
        "sex.preference.occupant",
        "sex",
        "occupant_preference",
        "warning",
        r"\b(?:perfect|ideal|great)\s+for\s+(?:women|men|females|males)\b"
        r"|\bespecially\s+convenient\s+for\s+(?:women|men)\s+living\s+alone\b",
        "Avoid describing a preferred type of resident.",
    ),
    ComplianceRule(
        "familial.exception.senior_housing",
        "familial_status",
        "potential_exception",
        "info",
        r"\b(?:55\+|62\+|senior)\s+(?:community|housing|living)\b",
        "Confirm that any age-restricted housing designation is supported by the listing policy.",
    ),
)
