"""
Run WADE-Eval evaluation over all agents and all sites.

Outputs:
- results/per_site_results.csv
- results/domain_results.csv
- results/final_results.csv
- results/table_for_paper.tex
"""

import csv
import json
from pathlib import Path
from statistics import mean

import yaml

from eval.align_records import align_records
from eval.metrics import (
    load_json_file,
    load_log_file,
    compute_site_metrics
)


AGENTS = {
    "traditional_scraper": {
        "output_dir": Path("outputs/traditional_scraper"),
        "log_dir": Path("logs/traditional_scraper")
    },
    "llm_only_extractor": {
        "output_dir": Path("outputs/llm_only_extractor"),
        "log_dir": Path("logs/llm_only_extractor")
    },
    "llm_playwright_agent": {
        "output_dir": Path("outputs/llm_playwright_agent"),
        "log_dir": Path("logs/llm_playwright_agent")
    }
}


RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def read_sites():
    config = yaml.safe_load(Path("config/sites.yaml").read_text(encoding="utf-8"))
    return config["sites"]


def resolve_agent_output_path(agent_name, site):
    site_id = site["id"]
    output_dir = AGENTS[agent_name]["output_dir"]

    candidates = [
        output_dir / f"{site_id}.json"
    ]

    # Compatibility with earlier naming.
    if site_id == "ecommerce_webscraper_laptops":
        candidates.append(output_dir / "ecommerce_webscraper.json")

    for path in candidates:
        if path.exists():
            return path

    return candidates[0]


def resolve_agent_log_path(agent_name, site):
    site_id = site["id"]
    log_dir = AGENTS[agent_name]["log_dir"]

    candidates = [
        log_dir / f"{site_id}_log.json"
    ]

    # Compatibility with earlier naming.
    short_names = {
        "ecommerce_books": "books_log.json",
        "ecommerce_webscraper_laptops": "webscraper_log.json",
        "ecommerce_demoblaze": "demoblaze_log.json",
        "conference_icitri": "icitri_log.json",
        "conference_icoa": "icoa_log.json",
        "conference_wise2026": "wise2026_log.json"
    }

    if site_id in short_names:
        candidates.append(log_dir / short_names[site_id])

    for path in candidates:
        if path.exists():
            return path

    return candidates[0]


def evaluate_all_sites():
    rows = []
    sites = read_sites()

    for site in sites:
        site_id = site["id"]
        domain = site["domain"]

        gold_path = Path(site["ground_truth_path"])
        gold_records = load_json_file(gold_path)

        if gold_records is None:
            print(f"[WARN] Missing or invalid ground truth: {gold_path}")
            continue

        for agent_name in AGENTS:
            pred_path = resolve_agent_output_path(agent_name, site)
            log_path = resolve_agent_log_path(agent_name, site)

            pred_records = load_json_file(pred_path)
            log = load_log_file(log_path)

            if pred_records is None:
                pred_records = []
                log.setdefault("status", "missing_output")
                log.setdefault("error", f"Missing or invalid output: {pred_path}")

            aligned_pairs, unmatched_predictions = align_records(
                domain=domain,
                gold_records=gold_records,
                pred_records=pred_records
            )

            metrics = compute_site_metrics(
                domain=domain,
                gold_records=gold_records,
                pred_records=pred_records,
                aligned_pairs=aligned_pairs,
                log=log
            )

            row = {
                "Agent": agent_name,
                "Site_ID": site_id,
                "Domain": domain,
                "Gold_Path": str(gold_path),
                "Prediction_Path": str(pred_path),
                "Log_Path": str(log_path),
                "Unmatched_Predictions": len(unmatched_predictions),
                **metrics
            }

            rows.append(row)

            print(
                f"[{agent_name} | {site_id}] "
                f"F1={row['Field_F1']} RC={row['RC']} "
                f"SV={row['SV']} Prov={row['Provenance']} "
                f"Latency={row['Latency']} Cost={row['Cost']}"
            )

    return rows


def write_csv(path, rows):
    if not rows:
        return

    fieldnames = list(rows[0].keys())

    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    if not values:
        return None
    return round(mean(values), 4)


def safe_sum(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return round(sum(values), 6)


def aggregate_by(rows, keys):
    grouped = {}

    for row in rows:
        group_key = tuple(row[k] for k in keys)
        grouped.setdefault(group_key, []).append(row)

    out = []

    for group_key, items in grouped.items():
        result = {keys[i]: group_key[i] for i in range(len(keys))}

        result.update({
            "N_Sites": len(items),
            "TSR": safe_mean([r["TSR"] for r in items]),
            "Field_F1": safe_mean([r["Field_F1"] for r in items]),
            "RC": safe_mean([r["RC"] for r in items]),
            "SV": safe_mean([r["SV"] for r in items]),
            "Provenance": safe_mean([r["Provenance"] for r in items]),
            "Latency": safe_mean([r["Latency"] for r in items]),
            "Cost": safe_sum([r["Cost"] for r in items]),
            "CPCR": safe_mean([r["CPCR"] for r in items]),
            "Tokens_Input": safe_sum([r["Tokens_Input"] for r in items]),
            "Tokens_Output": safe_sum([r["Tokens_Output"] for r in items]),
            "Correct_Records": safe_sum([r["Correct_Records"] for r in items]),
            "Predicted_Records": safe_sum([r["Predicted_Records"] for r in items]),
            "Gold_Records": safe_sum([r["Gold_Records"] for r in items])
        })

        out.append(result)

    return out


def make_latex_table(final_rows):
    """
    Creates compact LaTeX table for the paper.
    """

    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Pilot WADE-Eval results across six live web pages.}")
    lines.append(r"\label{tab:wade_eval_pilot}")
    lines.append(r"\resizebox{\columnwidth}{!}{%")
    lines.append(r"\begin{tabular}{lrrrrrrr}")
    lines.append(r"\hline")
    lines.append(r"Agent & TSR & Field F1 & RC & SV & Prov. & Lat. $\downarrow$ & CPCR $\downarrow$ \\")
    lines.append(r"\hline")

    display_names = {
        "traditional_scraper": "Traditional scraper",
        "llm_only_extractor": "LLM-only",
        "llm_playwright_agent": "LLM+MCP browser"
    }

    for row in final_rows:
        agent = display_names.get(row["Agent"], row["Agent"])

        cpcr = row["CPCR"]
        cpcr_str = "--" if cpcr is None else f"{cpcr:.4f}"

        latency = row["Latency"]
        latency_str = "--" if latency is None else f"{latency:.2f}"

        lines.append(
            f"{agent} & "
            f"{row['TSR']:.2f} & "
            f"{row['Field_F1']:.2f} & "
            f"{row['RC']:.2f} & "
            f"{row['SV']:.2f} & "
            f"{row['Provenance']:.2f} & "
            f"{latency_str} & "
            f"{cpcr_str} \\\\"
        )

    lines.append(r"\hline")
    lines.append(r"\end{tabular}%")
    lines.append(r"}")
    lines.append(r"\end{table}")

    return "\n".join(lines)


def main():
    rows = evaluate_all_sites()

    per_site_path = RESULTS_DIR / "per_site_results.csv"
    domain_path = RESULTS_DIR / "domain_results.csv"
    final_path = RESULTS_DIR / "final_results.csv"
    latex_path = RESULTS_DIR / "table_for_paper.tex"

    write_csv(per_site_path, rows)

    domain_rows = aggregate_by(rows, ["Agent", "Domain"])
    write_csv(domain_path, domain_rows)

    final_rows = aggregate_by(rows, ["Agent"])
    write_csv(final_path, final_rows)

    latex = make_latex_table(final_rows)
    latex_path.write_text(latex, encoding="utf-8")

    print("\nDone.")
    print(f"Per-site results: {per_site_path}")
    print(f"Domain results:   {domain_path}")
    print(f"Final results:    {final_path}")
    print(f"LaTeX table:      {latex_path}")


if __name__ == "__main__":
    main()
