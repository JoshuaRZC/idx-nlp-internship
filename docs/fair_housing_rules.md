# Fair Housing Review Rules

## Purpose

`ComplianceChecker` is a pre-publication screening tool for English listing remarks. It flags advertising language that may express a preference, limitation, or exclusion related to a protected class. It supports editorial review; it is not a legal opinion or a substitute for review by qualified counsel.

The default `federal-1.1` policy follows the Federal Fair Housing Act baseline: race, color, national origin, religion, sex, familial status, and disability. State or local requirements are intentionally out of scope for this version.

## Review Outcomes

| Status | Meaning | Submission action |
| --- | --- | --- |
| `pass` | No actionable rule matched. | The listing can proceed. |
| `review` | The text may imply a resident preference or demographic characterization. | An authorized reviewer must revise or approve the wording. |
| `blocked` | The text explicitly limits, excludes, or prefers a protected group. | The listing cannot be published until it is corrected. |

`info` findings do not change a `pass` status. They identify phrases such as `55+ community` that need confirmation from upstream listing policy rather than an automatic legal conclusion.

## Rule Boundaries

The checker targets complete risk expressions, such as `no children`, `English speakers only`, or `perfect for singles`. It does not flag isolated protected-class words by themselves.

Examples of neutral property descriptions that should remain publishable:

- `wheelchair accessible entry`
- `walk to a church`
- `family room with fireplace`
- `kosher kitchen`

Describe the property, its features, and its location. Do not describe the type of person who should live there or the demographic makeup of a neighborhood.

## Submission Integration

```python
result = ComplianceChecker().check_listing(draft_remarks)

if result["status"] == "blocked":
    return {"saved": False, "compliance": result}
if result["status"] == "review":
    return {"saved": False, "requires_reviewer_confirmation": True, "compliance": result}

save_listing(draft_remarks)
```

Store the rule version, matched rule IDs, reviewer action, and review time with the submission record. Do not treat a `pass` result as a legal certification.

## Maintaining The Policy

Add a rule only when it has a clear protected-class connection, an explicit editorial action, and positive and negative test cases. Keep rules in `compliance_rules.py`, assign a stable `rule_id`, and update the local evaluation set before changing the policy version.

Primary references: [HUD Fair Housing Act overview](https://www.hud.gov/helping-americans/fair-housing-act-overview) and [HUD Fair Housing Advertising regulations](https://hud.gov/sites/dfiles/FHEO/documents/BBE%20Part%20109%20Fair%20Housing%20Advertising.pdf).
