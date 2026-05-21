"""
Agent 2 — LLM-Only HTML Extractor (Claude)
Input:  saved HTML snapshot + schema from sites.yaml
Model:  Claude API
Output: outputs/llm_only_extractor/{site_id}.json
Logs:   logs/llm_only_extractor/{site_id}_log.json
"""

import os, json, time, re, argparse
from pathlib import Path

import yaml
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from anthropic import Anthropic

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
MODEL = os.getenv("CLAUDE_MODEL_AGENT2", "claude-haiku-4-5")

MAX_HTML_CHARS = 40_000
CONFIG_DIR = Path("config")
OUTPUT_DIR = Path("outputs/llm_only_extractor")
LOG_DIR = Path("logs/llm_only_extractor")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Default Claude pricing per 1M tokens.
# Adjust in .env if needed.
PRICE_IN = float(os.getenv("CLAUDE_AGENT2_PRICE_INPUT_PER_MTOK", "1.0")) / 1_000_000
PRICE_OUT = float(os.getenv("CLAUDE_AGENT2_PRICE_OUTPUT_PER_MTOK", "5.0")) / 1_000_000


# ── HTML cleaning ─────────────────────────────────────────────────────────────
def clean_html(raw_html: str, max_chars: int = MAX_HTML_CHARS) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "img", "link", "meta", "head"]):
        tag.decompose()

    text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n"))
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[TRUNCATED]"

    return text


# ── Prompt examples ───────────────────────────────────────────────────────────
ECOMMERCE_EXAMPLE = json.dumps([
    {
        "record_id": "1",
        "name": "Product Name",
        "price": "$12.99",
        "rating": "4",
        "availability": "In stock",
        "product_url": "https://example.com/product/1",
        "source_url": "https://example.com/",
        "source_xpath": None
    }
], indent=2)

CONFERENCE_EXAMPLE = json.dumps([
    {
        "record_id": "1",
        "conference_name": "Full Conference Name",
        "acronym": "CONF",
        "submission_deadline": "30 May 2026",
        "notification_date": "10 July 2026",
        "conference_dates": "29-30 October 2026",
        "location": "City, Country",
        "topics": ["Topic 1", "Topic 2"],
        "submission_url": "https://submit.example.com",
        "source_url": "https://conf.example.com/",
        "source_xpath": None
    }
], indent=2)


def build_prompt(site: dict, schema: dict, html_text: str) -> str:
    domain = site["domain"]
    site_url = site["url"]
    limit = site.get("output_limit", 10)
    fields = list(schema["fields"].keys())

    example = ECOMMERCE_EXAMPLE if domain == "ecommerce" else CONFERENCE_EXAMPLE

    if domain == "ecommerce":
        task = f"""
Extract the first {limit} product records from the page content below.

Source URL: {site_url}

Required fields:
{fields}

Rules:
- record_id: sequential string starting at "1".
- price: keep currency symbol, return as string.
- rating: numeric string "1"–"5", or null if not shown.
- availability: "In stock", "Out of stock", or null if not shown.
- product_url: full URL if available, otherwise null.
- source_url: always "{site_url}".
- source_xpath: always null.
- Return maximum {limit} records.
- Do not invent products not present in the provided page content.

Example:
{example}
"""
    else:
        task = f"""
Extract the conference information from the page content below.

Source URL: {site_url}

Required fields:
{fields}

Rules:
- record_id: always "1".
- conference_name: full conference name.
- acronym: conference acronym.
- submission_deadline: exact date string as shown.
- notification_date: exact date string as shown.
- conference_dates: full date range as shown.
- location: location as shown.
- topics: array of strings, one per topic.
- submission_url: submission platform URL if available.
- source_url: always "{site_url}".
- source_xpath: always null.
- Use null for fields not present in the page.
- Return exactly 1 record.
- Do not invent missing values.

Example:
{example}
"""

    return f"""
You are a precise structured data extraction engine.

Return ONLY a valid JSON array.
No markdown.
No explanation.
No backticks.
Start your response with [ and end with ].

{task}

---
PAGE CONTENT:
{html_text}
""".strip()


# ── Claude API call ───────────────────────────────────────────────────────────
def call_claude(prompt: str) -> tuple[list, int, int, float]:
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        raw = match.group(0)

    records = json.loads(raw)

    if not isinstance(records, list):
        records = [records]

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost_usd = round(tokens_in * PRICE_IN + tokens_out * PRICE_OUT, 6)

    return records, tokens_in, tokens_out, cost_usd


# ── Per-site runner ───────────────────────────────────────────────────────────
def run_site(site: dict) -> dict:
    site_id = site["id"]
    snap_path = Path(site["snapshot_path"])
    schema_path = CONFIG_DIR / site["schema"]

    out_path = OUTPUT_DIR / f"{site_id}.json"
    log_path = LOG_DIR / f"{site_id}_log.json"

    print(f"\n[{site_id}] Cleaning HTML...")

    raw_html = snap_path.read_text(encoding="utf-8", errors="ignore")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    html_text = clean_html(raw_html)
    prompt = build_prompt(site, schema, html_text)

    print(f"[{site_id}] Sending {len(html_text):,} chars to {MODEL}...")

    start = time.time()
    status = "success"
    error = None
    records = []
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0

    try:
        records, tokens_in, tokens_out, cost_usd = call_claude(prompt)
        records = records[:site.get("output_limit", 10)]
    except json.JSONDecodeError as e:
        status = "json_parse_error"
        error = str(e)
        print(f"  ✗ JSON parse error: {e}")
    except Exception as e:
        status = "error"
        error = str(e)
        print(f"  ✗ Error: {e}")

    elapsed = round(time.time() - start, 2)

    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    log = {
        "agent": "llm_only_extractor",
        "site_id": site_id,
        "model": MODEL,
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds": elapsed,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "estimated_cost": cost_usd,
        "html_chars_sent": len(html_text),
        "num_records": len(records),
        "status": status,
        "error": error
    }

    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"[{site_id}] {status} | {len(records)} records | "
        f"{tokens_in}+{tokens_out} tokens | ${cost_usd:.5f} | {elapsed}s"
    )

    return log


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Run only this site_id")
    parser.add_argument("--domain", help="Run only domain: ecommerce/conference")
    args = parser.parse_args()

    raw = yaml.safe_load(Path("config/sites.yaml").read_text(encoding="utf-8"))
    sites = raw["sites"]

    if args.site:
        sites = [s for s in sites if s["id"] == args.site]

    if args.domain:
        sites = [s for s in sites if s["domain"] == args.domain]

    if not sites:
        print("No matching sites.")
        return

    print(f"Agent 2 — LLM-only / Claude — {len(sites)} site(s) — model: {MODEL}")

    total_cost = 0.0

    for site in sites:
        log = run_site(site)
        total_cost += log.get("estimated_cost", 0.0)

    print(f"\n{'=' * 50}")
    print(f"Done. Total estimated cost: ${total_cost:.5f}")
    print(f"Outputs → {OUTPUT_DIR}/")
    print(f"Logs    → {LOG_DIR}/")


if __name__ == "__main__":
    main()