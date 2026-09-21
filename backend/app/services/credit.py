"""CRediT category seed list and helpers.

The 14 CRediT contributor roles per NISO Z39.104-2022.
"""
from __future__ import annotations

CREDIT_CATEGORIES: list[tuple[str, str]] = [
    ("conceptualization", "Conceptualization"),
    ("data_curation", "Data curation"),
    ("formal_analysis", "Formal analysis"),
    ("funding_acquisition", "Funding acquisition"),
    ("investigation", "Investigation"),
    ("methodology", "Methodology"),
    ("project_administration", "Project administration"),
    ("resources", "Resources"),
    ("software", "Software"),
    ("supervision", "Supervision"),
    ("validation", "Validation"),
    ("visualization", "Visualization"),
    ("writing_original_draft", "Writing - original draft"),
    ("writing_review_editing", "Writing - review & editing"),
]


CREDIT_BY_CODE: dict[str, str] = dict(CREDIT_CATEGORIES)


def is_valid_category(code: str) -> bool:
    return code in CREDIT_BY_CODE
