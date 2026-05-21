"""
Record alignment for WADE-Eval.

Matches predicted records to ground-truth records before field-level scoring.
"""

from eval.normalize import normalize_field


def _safe_get(record, key):
    if not isinstance(record, dict):
        return None
    return record.get(key)


def align_ecommerce_records(gold_records, pred_records):
    """
    Align e-commerce records using product_url first, then name.
    Returns list of (gold_record, predicted_record_or_none).
    """

    pred_by_url = {}
    pred_by_name = {}

    for pred in pred_records:
        url = normalize_field("product_url", _safe_get(pred, "product_url"))
        name = normalize_field("name", _safe_get(pred, "name"))

        if url:
            pred_by_url[url] = pred

        if name:
            pred_by_name[name] = pred

    aligned = []
    used_pred_ids = set()

    for gold in gold_records:
        gold_url = normalize_field("product_url", _safe_get(gold, "product_url"))
        gold_name = normalize_field("name", _safe_get(gold, "name"))

        match = None

        if gold_url and gold_url in pred_by_url:
            match = pred_by_url[gold_url]

        elif gold_name and gold_name in pred_by_name:
            match = pred_by_name[gold_name]

        if match is not None:
            used_pred_ids.add(id(match))

        aligned.append((gold, match))

    unmatched_predictions = [
        pred for pred in pred_records if id(pred) not in used_pred_ids
    ]

    return aligned, unmatched_predictions


def align_conference_records(gold_records, pred_records):
    """
    Conference pages have exactly one expected record.
    """
    gold = gold_records[0] if gold_records else None
    pred = pred_records[0] if pred_records else None

    aligned = []
    if gold is not None:
        aligned.append((gold, pred))

    unmatched_predictions = pred_records[1:] if len(pred_records) > 1 else []

    return aligned, unmatched_predictions


def align_records(domain, gold_records, pred_records):
    if domain == "ecommerce":
        return align_ecommerce_records(gold_records, pred_records)

    if domain == "conference":
        return align_conference_records(gold_records, pred_records)

    raise ValueError(f"Unknown domain: {domain}")
