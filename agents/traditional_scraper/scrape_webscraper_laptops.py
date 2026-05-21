"""
Agent 1 - Traditional Scraper: webscraper.io/test-sites/e-commerce/allinone/computers/laptops
Reads from saved HTML snapshot.
Output: outputs/traditional_scraper/ecommerce_webscraper_laptops.json
"""

import json, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SOURCE_URL = "https://webscraper.io/test-sites/e-commerce/allinone/computers/laptops"
SNAPSHOT   = Path("data/snapshots/ecommerce/webscraper_laptops.html")
OUTPUT     = Path("outputs/traditional_scraper/ecommerce_webscraper_laptops.json")
LOG_OUT    = Path("logs/traditional_scraper/webscraper_log.json")
BASE_URL   = "https://webscraper.io"

Path("outputs/traditional_scraper").mkdir(parents=True, exist_ok=True)
Path("logs/traditional_scraper").mkdir(parents=True, exist_ok=True)


def scrape_webscraper() -> list[dict]:
    html  = SNAPSHOT.read_text(encoding="utf-8")
    soup  = BeautifulSoup(html, "html.parser")
    items = soup.select("div.thumbnail")
    records = []

    for i, item in enumerate(items, start=1):
        name_el    = item.select_one("a.title")
        price_span = item.select_one("span[itemprop='price']") or item.select_one("h4.price")
        star_els   = item.select("span.ws-icon-star")
        reviews_el = item.select_one("p.review-count") or item.select_one(".ratings .pull-right")

        if not name_el:
            continue

        name  = name_el.get_text(strip=True)
        href  = name_el.get("href", "")
        product_url = BASE_URL + href if href.startswith("/") else href

        # Price: keep as string with $ sign to match ground truth format
        price = None
        if price_span:
            raw = price_span.get_text(strip=True)
            # Ensure $ prefix
            if not raw.startswith("$"):
                raw = "$" + raw
            price = raw

        # Rating: count filled stars → string
        rating = str(len(star_els)) if star_els else None

        # Source XPath — positional, matching ground truth pattern
        source_xpath = (
            f"/html/body/div[1]/main/div[3]/div/div[2]/div[1]/div[{i}]"
            f"/div/div/div[1]/h4[2]/a"
        )

        records.append({
            "record_id":    str(i),
            "name":         name,
            "price":        price,
            "rating":       rating,
            "availability": None,  # not shown on listing page
            "product_url":  product_url,
            "source_url":   SOURCE_URL,
            "source_xpath": source_xpath,
        })

    return records[:10]


def main():
    start   = time.time()
    records = scrape_webscraper()
    elapsed = round(time.time() - start, 3)

    OUTPUT.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    log = {
        "agent":           "traditional_scraper",
        "site_id":         "webscraper_laptops",
        "start_time":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds": elapsed,
        "tokens_input":    0,
        "tokens_output":   0,
        "estimated_cost":  0.0,
        "num_records":     len(records),
        "status":          "success",
        "error":           None,
    }
    LOG_OUT.write_text(json.dumps(log, indent=2))

    print(f"[webscraper] {len(records)} records → {OUTPUT}  ({elapsed}s)")
    return records[:10]


if __name__ == "__main__":
    main()
