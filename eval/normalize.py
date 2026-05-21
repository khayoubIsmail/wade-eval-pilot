"""
Normalization utilities for WADE-Eval.

Used to compare ground-truth values and predicted values robustly.
"""

import re
from urllib.parse import urlparse, urlunparse


def normalize_text(value):
    if value is None:
        return None

    if isinstance(value, list):
        return [normalize_text(v) for v in value]

    value = str(value)
    value = value.strip()
    value = re.sub(r"\s+", " ", value)

    return value


def normalize_lower(value):
    value = normalize_text(value)
    if value is None:
        return None
    return value.lower()


def normalize_price(value):
    if value is None:
        return None

    value = str(value).strip()
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", "", value)

    # Keep currency symbol but normalize numeric part.
    return value


def normalize_rating(value):
    if value is None or value == "":
        return None

    value = str(value).strip().lower()

    rating_map = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5"
    }

    if value in rating_map:
        return rating_map[value]

    match = re.search(r"[0-5]", value)
    if match:
        return match.group(0)

    return value


def normalize_url(value):
    if value is None or value == "":
        return None

    value = str(value).strip()

    try:
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path[:-1]

        return urlunparse((scheme, netloc, path, "", parsed.query, ""))
    except Exception:
        return value


def normalize_date(value):
    """
    Lightweight date normalization.
    For this pilot, keep date strings mostly as-is but normalize spaces and dashes.
    """
    if value is None or value == "":
        return None

    value = normalize_text(value)
    value = value.replace("â€“", "-").replace("â€”", "-")
    value = re.sub(r"\s*-\s*", "-", value)

    return value


def normalize_list(values):
    if values is None:
        return []

    if not isinstance(values, list):
        values = [values]

    cleaned = []
    for item in values:
        item = normalize_text(item)
        if item:
            cleaned.append(item.lower())

    return cleaned


def normalize_field(field, value):
    if field in {"name", "conference_name", "acronym", "availability", "location"}:
        return normalize_lower(value)

    if field == "price":
        return normalize_price(value)

    if field == "rating":
        return normalize_rating(value)

    if field in {"product_url", "source_url", "submission_url"}:
        return normalize_url(value)

    if field in {"submission_deadline", "notification_date", "conference_dates"}:
        return normalize_date(value)

    if field == "topics":
        return normalize_list(value)

    if field == "source_xpath":
        return normalize_text(value)

    return normalize_text(value)


def values_equal(field, gold_value, pred_value):
    gold = normalize_field(field, gold_value)
    pred = normalize_field(field, pred_value)

    if gold is None and pred is None:
        return True

    if gold in [None, ""] and pred in [None, ""]:
        return True

    if field == "topics":
        gold_set = set(gold)
        pred_set = set(pred)
        if not gold_set and not pred_set:
            return True
        if not gold_set or not pred_set:
            return False

        overlap = len(gold_set & pred_set)
        return overlap / max(len(gold_set), 1) >= 0.5

    return gold == pred
