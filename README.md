# WADE-Eval Pilot Artifact

This repository contains the pilot evaluation artifact for **WADE-Eval**, a taxonomy and evaluation framework for web automation and data extraction using LLM-based agents.

The pilot compares three extraction paradigms across live web pages:

1. **Traditional scraper** — manually written CSS/XPath selectors.
2. **LLM-only extractor** — Claude reads saved HTML snapshots and returns JSON.
3. **LLM + Playwright MCP browser agent** — Claude uses Playwright MCP tools to interact with live web pages.

The goal is to show that simple task success is insufficient for evaluating web data extraction agents. WADE-Eval instead evaluates extraction quality, record completeness, schema validity, provenance, latency, and cost.

---

## Repository Structure

```text
wade-eval-pilot/
│
├── agents/
│   ├── traditional_scraper/
│   ├── llm_only_extractor/
│   └── llm_playwright_agent/
│
├── config/
│   ├── sites.yaml
│   ├── ecommerce_schema.json
│   └── conference_schema.json
│
├── data/
│   ├── ground_truth/
│   └── snapshots/
│
├── eval/
│   ├── __init__.py
│   ├── normalize.py
│   ├── align_records.py
│   ├── metrics.py
│   └── run_eval.py
│
├── logs/
│
├── outputs/
│
├── results/
│   ├── per_site_results.csv
│   ├── domain_results.csv
│   ├── final_results.csv
│   └── table_for_paper.tex
│
├── capture_pages.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Evaluated Websites

The pilot uses six live web pages from two domains.

### E-commerce

| Site ID | Website | Task |
|---|---|---|
| `ecommerce_books` | Books to Scrape | Extract book listings |
| `ecommerce_webscraper_laptops` | WebScraper laptop test site | Extract laptop listings |
| `ecommerce_demoblaze` | Demoblaze | Extract product listings with pagination |

### Conference CFP Pages

| Site ID | Website | Task |
|---|---|---|
| `conference_icitri` | ICITRI | Extract conference metadata |
| `conference_icoa` | ICOA | Extract conference metadata |
| `conference_wise2026` | WISE 2026 CFP | Extract conference metadata |

---

## Agents

### Agent 1: Traditional Scraper

The traditional scraper uses manually defined CSS/XPath selectors for each website.

Characteristics:

- Fast
- Free at runtime
- Strong when selectors are stable
- Requires site-specific engineering
- Weak when pages require pagination or dynamic interaction

Outputs:

```text
outputs/traditional_scraper/
logs/traditional_scraper/
```

---

### Agent 2: LLM-only HTML Extractor

The LLM-only extractor uses saved HTML snapshots as input.

Pipeline:

```text
HTML snapshot + schema + prompt → Claude → JSON output
```

This agent does not use browser tools and cannot interact with pages.

Outputs:

```text
outputs/llm_only_extractor/
logs/llm_only_extractor/
```

---

### Agent 3: LLM + Playwright MCP Browser Agent

The browser agent uses Claude with Playwright MCP tools.

Pipeline:

```text
Claude API → MCP client → Playwright MCP server → browser tools → JSON output
```

This agent can:

- Navigate live web pages
- Inspect DOM snapshots
- Click buttons
- Handle pagination
- Return extraction provenance through `source_xpath`

Outputs:

```text
outputs/llm_playwright_agent/
logs/llm_playwright_agent/
```

---

## Metrics

WADE-Eval computes the following metrics:

| Metric | Meaning |
|---|---|
| TSR | Task Success Rate |
| Field F1 | Field-level extraction quality |
| RC | Record Completeness |
| SV | Schema Validity |
| Provenance | Fraction of records with source XPath evidence |
| Latency | Runtime in seconds |
| CPCR | Cost per correct record |

These metrics are intended to show that task success alone is not enough for evaluating web extraction agents.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/wade-eval-pilot.git
cd wade-eval-pilot
```

### 2. Create Python environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate
```

```bash
# macOS/Linux
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

Copy:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and add your Anthropic API key:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

---

## Playwright MCP Setup

Go to the MCP agent folder:

```bash
cd agents/llm_playwright_agent
```

Install Node dependencies:

```bash
npm install
```

Install Chromium:

```bash
npx playwright install chromium
```

Return to project root:

```bash
cd ../..
```

The Python MCP client starts the Playwright MCP server automatically. You do not need to run the MCP server manually in another terminal for the provided script.

---

## Running the Pipeline

### 1. Capture live pages

```bash
python capture_pages.py
```

This creates HTML snapshots and screenshots.

Outputs:

```text
data/snapshots/
data/screenshots/
logs/capture_log.json
```

### 2. Run Agent 1: Traditional Scraper

Run the traditional scripts from the project root.

```bash
python agents/traditional_scraper/scrape_books.py
python agents/traditional_scraper/scrape_webscraper_laptops.py
python agents/traditional_scraper/scrape_demoblaze.py
python agents/traditional_scraper/scrape_icitri.py
python agents/traditional_scraper/scrape_icoa.py
python agents/traditional_scraper/scrape_wise2026.py
```

### 3. Run Agent 2: LLM-only Extractor

Run all sites:

```bash
python agents/llm_only_extractor/run_llm_only.py
```

Or run one site:

```bash
python agents/llm_only_extractor/run_llm_only.py --site ecommerce_books
```

### 4. Run Agent 3: MCP Browser Agent

Run one site:

```bash
python agents/llm_playwright_agent/run_browser_agent.py --site ecommerce_demoblaze
```

Run all sites:

```bash
python agents/llm_playwright_agent/run_browser_agent.py
```

---

## Running Evaluation

Run:

```bash
python -m eval.run_eval
```

This generates:

```text
results/per_site_results.csv
results/domain_results.csv
results/final_results.csv
results/table_for_paper.tex
```

---

## Main Result Summary

The pilot results show that task success alone is insufficient.

A typical final summary is:

| Agent | TSR | Field F1 | Provenance | Latency | Cost |
|---|---:|---:|---:|---:|---:|
| Traditional scraper | 1.00 | 0.79 | 1.00 | 0.22s | $0.00 |
| LLM-only | 1.00 | 0.45 | 0.00 | 5.2s | $0.05 |
| LLM + Playwright MCP | 1.00 | 0.84 | 1.00 | 250s | $4.99 |

Interpretation:

- All agents can achieve high task success.
- LLM-only extraction may produce partially correct fields but weak complete-record accuracy.
- Browser-agent extraction improves field quality and provenance.
- Browser-agent extraction is slower and more expensive.
- WADE-Eval exposes trade-offs hidden by task success alone.

---

## Reproducibility Notes

This artifact includes:

- Website configuration
- Extraction schemas
- Ground-truth JSON files
- Agent outputs
- Logs with latency, token usage, and estimated cost
- Evaluation scripts
- Result tables

Live websites may change over time. For reproducibility, saved HTML snapshots are included where appropriate.

---

## Limitations

This is a pilot-scale evaluation, not a large benchmark.

Known limitations:

- Only six live web pages are used.
- Some pages may change after capture.
- Agent 3 uses live browser interaction, which can introduce runtime variability.
- API costs depend on provider pricing at the time of execution.
- LLM outputs may vary slightly across runs and model versions.
- The browser agent can enter long interaction loops on complex pages, increasing latency and cost.
- CPCR may be undefined when an agent produces no fully correct records, even if some individual fields are correct.

---

## Citation

If you use this artifact, please cite the associated WADE-Eval paper.

```bibtex
@misc{wadeeval2026,
  title        = {WADE-Eval: A Taxonomy and Evaluation Framework for Web Automation and Data Extraction Agents},
  author       = {Khayoub, Ismail and Chadi, Mohamed-Amine and Mousannif, Hajar and Ait Mohamed, Firdaous},
  year         = {2026},
  note         = {Pilot evaluation artifact}
}
```

---

## License

This repository is released for academic and reproducibility purposes.

Add a `LICENSE` file before public release if needed.
