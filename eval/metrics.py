"""
Metric computation for WADE-Eval.

Metrics:
- TSR: Task Success Rate
- Field F1
- RC: Record Completeness
- SV: Schema Validity
- Provenance
- Latency
- CPCR: Cost Per Correct Record
"""

import json
from pathlib import Path

from eval.normalize import values_equal


ECOMMERCE_FIELDS = [
    "name",
    "price",
    "rating",
    "availability",
    "product_url"
]

CONFERENCE_FIELDS = [
    "conference_name",
    "acronym",
    "submission_deadline",
    "notification_date",
    "conference_dates",
    "location",
    "topics",
    "submission_url"
]


def required_fields_for_domain(domain):
    if domain == "ecommerce":
        return [
            "record_id",
            "name",
            "price",
            "rating",
            "availability",
            "product_url",
            "source_url",
            "source_xpath"
        ]

    if domain == "conference":
        return [
            "record_id",
            "conference_name",
            "acronym",
            "submission_deadline",
            "notification_date",
            "conference_dates",
            "location",
            "topics",
            "submission_url",
            "source_url",
            "source_xpath"
        ]

    raise ValueError(f"Unknown domain: {domain}")


def scored_fields_for_domain(domain):
    if domain == "ecommerce":
        return ECOMMERCE_FIELDS

    if domain == "conference":
        return CONFERENCE_FIELDS

    raise ValueError(f"Unknown domain: {domain}")


def load_json_file(path):
    path = Path(path)

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            return None

        return data

    except Exception:
        return None


def load_log_file(path):
    path = Path(path)

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def schema_validity(pred_records, domain):
    if not pred_records:
        return 0.0

    required = required_fields_for_domain(domain)
    valid_count = 0

    for record in pred_records:
        if not isinstance(record, dict):
            continue

        has_all = all(field in record for field in required)

        if domain == "conference":
            topics_ok = isinstance(record.get("topics"), list)
        else:
            topics_ok = True

        if has_all and topics_ok:
            valid_count += 1

    return round(valid_count / len(pred_records), 4)


def task_success(pred_records, log):
    if log.get("status") not in [None, "success"]:
        return 0.0

    if pred_records is None:
        return 0.0

    if len(pred_records) == 0:
        return 0.0

    return 1.0


def record_completeness(gold_records, pred_records):
    if not gold_records:
        return 0.0

    if pred_records is None:
        pred_records = []

    return round(min(len(pred_records), len(gold_records)) / len(gold_records), 4)


def field_scores(domain, aligned_pairs):
    fields = scored_fields_for_domain(domain)

    true_positive = 0
    false_positive = 0
    false_negative = 0

    correct_records = 0

    for gold, pred in aligned_pairs:
        if pred is None:
            false_negative += len(fields)
            continue

        record_correct_fields = 0

        for field in fields:
            gold_value = gold.get(field)
            pred_value = pred.get(field)

            if values_equal(field, gold_value, pred_value):
                true_positive += 1
                record_correct_fields += 1
            else:
                false_positive += 1
                false_negative += 1

        if record_correct_fields == len(fields):
            correct_records += 1

    precision_den = true_positive + false_positive
    recall_den = true_positive + false_negative

    precision = true_positive / precision_den if precision_den else 0.0
    recall = true_positive / recall_den if recall_den else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "field_precision": round(precision, 4),
        "field_recall": round(recall, 4),
        "field_f1": round(f1, 4),
        "correct_fields": true_positive,
        "correct_records": correct_records
    }


def provenance_score(pred_records):
    if not pred_records:
        return 0.0

    count = 0

    for record in pred_records:
        source_xpath = record.get("source_xpath")
        if source_xpath is not None and str(source_xpath).strip() != "":
            count += 1

    return round(count / len(pred_records), 4)


def cost_per_correct_record(cost, correct_records):
    if correct_records <= 0:
        return None

    return round(cost / correct_records, 6)


def compute_site_metrics(domain, gold_records, pred_records, aligned_pairs, log):
    if pred_records is None:
        pred_records = []

    tsr = task_success(pred_records, log)
    sv = schema_validity(pred_records, domain)
    rc = record_completeness(gold_records, pred_records)
    field_result = field_scores(domain, aligned_pairs)
    prov = provenance_score(pred_records)

    latency = log.get("latency_seconds", None)
    cost = log.get("estimated_cost", 0.0) or 0.0
    tokens_in = log.get("tokens_input", 0) or 0
    tokens_out = log.get("tokens_output", 0) or 0
    status = log.get("status", "unknown")
    error = log.get("error", None)

    cpcr = cost_per_correct_record(
        cost=cost,
        correct_records=field_result["correct_records"]
    )

    return {
        "TSR": tsr,
        "Field_Precision": field_result["field_precision"],
        "Field_Recall": field_result["field_recall"],
        "Field_F1": field_result["field_f1"],
        "RC": rc,
        "SV": sv,
        "Provenance": prov,
        "Latency": latency,
        "Cost": round(cost, 6),
        "CPCR": cpcr,
        "Tokens_Input": tokens_in,
        "Tokens_Output": tokens_out,
        "Correct_Fields": field_result["correct_fields"],
        "Correct_Records": field_result["correct_records"],
        "Predicted_Records": len(pred_records),
        "Gold_Records": len(gold_records),
        "Status": status,
        "Error": error
    }
