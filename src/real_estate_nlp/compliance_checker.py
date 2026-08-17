"""Screen listing remarks for Fair Housing advertising risks."""

import re

from src.real_estate_nlp.compliance_rules import FEDERAL_RULES, RULE_VERSION


class ComplianceChecker:
    """Apply an explainable Federal Fair Housing rule set to listing text."""

    SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

    def __init__(self, rules=None, rule_version=RULE_VERSION):
        self.rules = tuple(FEDERAL_RULES if rules is None else rules)
        self.rule_version = rule_version

    def check_listing(self, text):
        """Return review findings and the resulting publication status."""
        source = str(text or "")
        findings = self._findings(source)
        status = self._status(findings)
        return {
            "status": status,
            "can_publish": status == "pass",
            "rule_version": self.rule_version,
            "findings": findings,
        }

    def _findings(self, text):
        findings = []
        for rule in self.rules:
            for match in re.finditer(rule.pattern, text, flags=re.IGNORECASE):
                findings.append(
                    {
                        "rule_id": rule.rule_id,
                        "protected_class": rule.protected_class,
                        "risk_type": rule.risk_type,
                        "severity": rule.severity,
                        "matched_text": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                        "message": rule.message,
                    }
                )
        return self._deduplicate(findings)

    def _deduplicate(self, findings):
        ranked = sorted(
            findings,
            key=lambda item: (
                self.SEVERITY_ORDER[item["severity"]],
                -(item["end"] - item["start"]),
                item["start"],
                item["rule_id"],
            ),
        )
        selected = []
        for finding in ranked:
            if any(self._overlaps(finding, kept) for kept in selected):
                continue
            selected.append(finding)
        return sorted(selected, key=lambda item: (item["start"], self.SEVERITY_ORDER[item["severity"]]))

    @staticmethod
    def _overlaps(left, right):
        return left["start"] < right["end"] and right["start"] < left["end"]

    @staticmethod
    def _status(findings):
        severities = {finding["severity"] for finding in findings}
        if "error" in severities:
            return "blocked"
        if "warning" in severities:
            return "review"
        return "pass"
