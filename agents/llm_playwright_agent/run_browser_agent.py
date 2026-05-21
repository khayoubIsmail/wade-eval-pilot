"""
Agent 3 — TRUE MCP-based LLM + Playwright Browser Agent

Architecture:
Claude API -> Python MCP Client -> Playwright MCP Server -> Browser Tools

Usage:
  python agents/llm_playwright_agent/run_browser_agent.py
  python agents/llm_playwright_agent/run_browser_agent.py --site ecommerce_books
  python agents/llm_playwright_agent/run_browser_agent.py --site ecommerce_demoblaze
  python agents/llm_playwright_agent/run_browser_agent.py --site conference_wise2026
  python agents/llm_playwright_agent/run_browser_agent.py --domain ecommerce
"""

import os
import re
import json
import time
import asyncio
import argparse
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from anthropic import Anthropic

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

PRICE_INPUT_PER_MTOK = float(os.getenv("CLAUDE_PRICE_INPUT_PER_MTOK", "3.0"))
PRICE_OUTPUT_PER_MTOK = float(os.getenv("CLAUDE_PRICE_OUTPUT_PER_MTOK", "15.0"))

CONFIG_DIR = Path("config")
OUTPUT_DIR = Path("outputs/llm_playwright_agent")
LOG_DIR = Path("logs/llm_playwright_agent")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


ECOMMERCE_EXAMPLE = json.dumps(
    [
        {
            "record_id": "1",
            "name": "Product Name",
            "price": "$12.99",
            "rating": "4",
            "availability": "In stock",
            "product_url": "https://example.com/product/1",
            "source_url": "https://example.com/",
            "source_xpath": "/html/body/main/div[1]/article[1]/h3/a"
        }
    ],
    indent=2
)

CONFERENCE_EXAMPLE = json.dumps(
    [
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
            "source_xpath": "/html/body/main/section[2]"
        }
    ],
    indent=2
)


XPATH_FUNCTION_INSTRUCTION = """
When using browser_evaluate, include this JavaScript helper and use it for source_xpath:

function getXPath(el) {
  if (!el) return null;
  if (el.id) return '//*[@id="' + el.id + '"]';

  const parts = [];
  while (el && el.nodeType === Node.ELEMENT_NODE) {
    let index = 1;
    let sibling = el.previousElementSibling;

    while (sibling) {
      if (sibling.nodeName === el.nodeName) index++;
      sibling = sibling.previousElementSibling;
    }

    parts.unshift(el.nodeName.toLowerCase() + "[" + index + "]");
    el = el.parentElement;
  }

  return "/" + parts.join("/");
}

For e-commerce records, source_xpath must point to the product title/link element.
For conference records, source_xpath must point to the main section or element containing the deadline/date evidence.
Do not return null for source_xpath if the evidence exists in the DOM.
"""


def build_task_prompt(site: dict, schema: dict) -> str:
    site_id = site["id"]
    domain = site["domain"]
    url = site["url"]
    limit = site.get("output_limit", 10)
    fields = list(schema["fields"].keys())

    if domain == "ecommerce":
        task = f"""
You are an MCP-based browser extraction agent.

Use the Playwright MCP browser tools to open and inspect the live webpage.

Site ID: {site_id}
URL: {url}
Domain: ecommerce
Required fields: {fields}

Task:
Extract the first {limit} product records.

Rules:
- You must navigate to the URL using browser tools.
- Use browser_snapshot and browser_evaluate when useful.
- If the page has pagination and fewer than {limit} products are visible, interact with the page.
- For Demoblaze, if only 9 products are visible, click the Next button and extract the 10th product.
- record_id must be sequential strings: "1", "2", ...
- price must keep the currency symbol.
- rating must be "1" to "5", or null if not shown.
- availability must be "In stock", "Out of stock", or null if not shown.
- product_url must be the full product URL if available.
- source_url must be exactly "{url}".
- source_xpath must be the XPath of the product title/link element when possible.
- Do not return null for source_xpath if the product exists in the DOM.
- If an item is extracted after pagination, source_xpath may be relative to the current paginated DOM state.

XPath instruction:
{XPATH_FUNCTION_INSTRUCTION}

Return ONLY a valid JSON array.
No markdown, no explanation, no backticks.
Start with [ and end with ].

Expected JSON example:
{ECOMMERCE_EXAMPLE}
"""
    else:
        wise_extra_rule = ""
        if site_id == "conference_wise2026":
            wise_extra_rule = """
Special rule for WISE 2026:
- Stay on the original CFP page.
- Do not navigate to the homepage or any other URL.
- You may click same-page accordion/tab/anchor sections only.
- Use browser_snapshot and browser_evaluate to extract visible text, links, dates, topics, and submission URL.
- Prefer ONE browser_evaluate call after navigation/snapshot.
- After at most 3 browser/tool actions, return the final JSON.
- Do not over-browse.
- Do not repeatedly call browser_snapshot.
- Do not use browser_navigate except for the original URL.
"""

        task = f"""
You are an MCP-based browser extraction agent.

Use the Playwright MCP browser tools to open and inspect the live webpage.

Site ID: {site_id}
URL: {url}
Domain: conference
Required fields: {fields}

Task:
Extract one structured conference record.

Rules:
- You must navigate to the URL using browser tools.
- Use browser_snapshot and browser_evaluate when useful.
- Do not navigate away from the original URL unless the current page has no relevant information.
- Prefer one browser_evaluate call that extracts document.body.innerText, links, dates, topics, and submission URL.
- After receiving enough evidence, return the final JSON immediately.
- record_id must be "1".
- conference_name must be the full conference name.
- acronym must be the conference acronym.
- submission_deadline must be the exact date string shown.
- notification_date must be the exact date string shown.
- conference_dates must be the full date range shown.
- location must be the location shown on the page.
- topics must be an array of topic strings.
- submission_url must be the submission platform URL if available.
- source_url must be exactly "{url}".
- source_xpath must point to the main DOM section containing the key extracted evidence, preferably dates/deadlines.
- Do not return null for source_xpath if the evidence exists in the DOM.
- Use null only for missing data fields. Do not invent values.

{wise_extra_rule}

XPath instruction:
{XPATH_FUNCTION_INSTRUCTION}

Return ONLY a valid JSON array.
No markdown, no explanation, no backticks.
Start with [ and end with ].

Expected JSON example:
{CONFERENCE_EXAMPLE}
"""

    return task.strip()


def mcp_tools_to_anthropic(tools_result: Any) -> list[dict]:
    tools = []

    for tool in tools_result.tools:
        input_schema = tool.inputSchema if tool.inputSchema else {
            "type": "object",
            "properties": {}
        }

        tools.append(
            {
                "name": tool.name,
                "description": tool.description or f"MCP tool: {tool.name}",
                "input_schema": input_schema
            }
        )

    return tools


def tool_result_to_text(result: Any) -> str:
    parts = []

    if hasattr(result, "content"):
        for item in result.content:
            item_type = getattr(item, "type", None)

            if item_type == "text":
                parts.append(getattr(item, "text", ""))

            elif item_type == "image":
                parts.append("[Image returned by MCP tool. Use snapshot/text if needed.]")

            else:
                parts.append(str(item))
    else:
        parts.append(str(result))

    return "\n".join(parts).strip()


def extract_json_array(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        text = match.group(0)

    data = json.loads(text)

    if isinstance(data, dict):
        return [data]

    if not isinstance(data, list):
        raise ValueError("Claude output is not a JSON array.")

    return data


def compute_cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens / 1_000_000) * PRICE_INPUT_PER_MTOK
        + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_MTOK,
        6
    )


async def run_mcp_agent_for_site(site: dict) -> dict:
    site_id = site["id"]
    schema_path = CONFIG_DIR / site["schema"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    output_path = OUTPUT_DIR / f"{site_id}.json"
    log_path = LOG_DIR / f"{site_id}_log.json"

    start = time.time()

    status = "success"
    error = None
    records = []
    browser_actions = []
    total_input_tokens = 0
    total_output_tokens = 0

    server_params = StdioServerParameters(
        command="npx",
        args=[
            "@playwright/mcp@latest",
            "--browser", "chrome",
            "--caps", "vision",
            "--ignore-https-errors",
            "--viewport-size", "1440x1200",
            "--output-dir", "agents/llm_playwright_agent/mcp_outputs",
            "--output-mode", "file"
        ]
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tools = mcp_tools_to_anthropic(tools_result)

                print(f"[{site_id}] MCP tools loaded: {len(tools)}")

                messages = [
                    {
                        "role": "user",
                        "content": build_task_prompt(site, schema)
                    }
                ]

                max_turns = 15
                final_text = None

                for turn in range(max_turns):

                    if site_id == "conference_wise2026" and turn >= 4:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "You have used enough browser actions. "
                                    "Do not call more tools. "
                                    "Based only on the evidence already collected, "
                                    "return the final valid JSON array now. "
                                    "No markdown, no explanation."
                                )
                            }
                        )

                    response = anthropic_client.messages.create(
                        model=MODEL,
                        max_tokens=4096,
                        temperature=0,
                        tools=tools,
                        messages=messages
                    )

                    total_input_tokens += response.usage.input_tokens
                    total_output_tokens += response.usage.output_tokens

                    assistant_content = response.content

                    messages.append(
                        {
                            "role": "assistant",
                            "content": assistant_content
                        }
                    )

                    tool_uses = [
                        block for block in assistant_content
                        if getattr(block, "type", None) == "tool_use"
                    ]

                    if not tool_uses:
                        final_text = "".join(
                            getattr(block, "text", "")
                            for block in assistant_content
                            if getattr(block, "type", None) == "text"
                        ).strip()
                        break

                    if site_id == "conference_wise2026" and turn >= 4:
                        final_text = "".join(
                            getattr(block, "text", "")
                            for block in assistant_content
                            if getattr(block, "type", None) == "text"
                        ).strip()
                        if final_text:
                            break

                    tool_results_for_message = []

                    for tool_use in tool_uses:
                        tool_name = tool_use.name
                        tool_args = tool_use.input or {}

                        if site_id == "conference_wise2026":
                            if tool_name == "browser_navigate" and browser_actions:
                                result_text = (
                                    "Blocked: For WISE 2026, do not navigate away from the original CFP page. "
                                    "Use the evidence already collected and return final JSON."
                                )
                                tool_results_for_message.append(
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_use.id,
                                        "content": result_text
                                    }
                                )
                                continue

                        print(f"[{site_id}] Tool call: {tool_name} {tool_args}")

                        browser_actions.append(
                            {
                                "turn": turn + 1,
                                "tool": tool_name,
                                "args": tool_args
                            }
                        )

                        try:
                            result = await session.call_tool(tool_name, tool_args)
                            result_text = tool_result_to_text(result)
                        except Exception as tool_error:
                            result_text = f"Tool error: {tool_error}"

                        tool_results_for_message.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": result_text[:12000]
                            }
                        )

                    messages.append(
                        {
                            "role": "user",
                            "content": tool_results_for_message
                        }
                    )

                if final_text is None or not final_text.strip():
                    raise RuntimeError("Max tool turns reached without final JSON output.")

                records = extract_json_array(final_text)
                records = records[:site.get("output_limit", 10)]

    except Exception as e:
        status = "error"
        error = str(e)
        print(f"[{site_id}] ERROR: {error}")

    elapsed = round(time.time() - start, 2)
    estimated_cost = compute_cost(total_input_tokens, total_output_tokens)

    output_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    log = {
        "agent": "mcp_llm_playwright_agent",
        "site_id": site_id,
        "model": MODEL,
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds": elapsed,
        "tokens_input": total_input_tokens,
        "tokens_output": total_output_tokens,
        "estimated_cost": estimated_cost,
        "num_records": len(records),
        "status": status,
        "error": error,
        "browser_actions": browser_actions
    }

    log_path.write_text(
        json.dumps(log, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(
        f"[{site_id}] {status} | {len(records)} records | "
        f"{total_input_tokens}+{total_output_tokens} tokens | "
        f"${estimated_cost:.5f} | {elapsed}s"
    )

    return log


async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Run only this site_id")
    parser.add_argument("--domain", help="Run only this domain: ecommerce/conference")
    args = parser.parse_args()

    config = yaml.safe_load(Path("config/sites.yaml").read_text(encoding="utf-8"))
    sites = config["sites"]

    if args.site:
        sites = [s for s in sites if s["id"] == args.site]

    if args.domain:
        sites = [s for s in sites if s["domain"] == args.domain]

    if not sites:
        print("No matching sites.")
        return

    print("Agent 3 — TRUE MCP-based Claude + Playwright agent")
    print(f"Sites: {len(sites)} | Model: {MODEL}")

    total_cost = 0.0

    for site in sites:
        log = await run_mcp_agent_for_site(site)
        total_cost += log.get("estimated_cost", 0.0)

    print("\n" + "=" * 60)
    print(f"Done. Total estimated cost: ${total_cost:.5f}")
    print(f"Outputs → {OUTPUT_DIR}")
    print(f"Logs    → {LOG_DIR}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()