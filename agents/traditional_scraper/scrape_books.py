"""
Agent 1 - Traditional Scraper: books.toscrape.com
Reads from saved HTML snapshot for reproducibility.
Output: outputs/traditional_scraper/ecommerce_books.json
"""

import json, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SOURCE_URL   = "https://books.toscrape.com/"
SNAPSHOT     = Path("data/snapshots/ecommerce/books.html")
OUTPUT       = Path("outputs/traditional_scraper/ecommerce_books.json")
LOG_OUT      = Path("logs/traditional_scraper/books_log.json")
RATING_MAP   = {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}

Path("outputs/traditional_scraper").mkdir(parents=True, exist_ok=True)
Path("logs/traditional_scraper").mkdir(parents=True, exist_ok=True)


def scrape_books() -> list[dict]:
    html  = SNAPSHOT.read_text(encoding="utf-8")
    soup  = BeautifulSoup(html, "html.parser")
    items = soup.select("article.product_pod")
    records = []

    for i, item in enumerate(items, start=1):
        name_el   = item.select_one("h3 > a")
        price_el  = item.select_one("p.price_color")
        rating_el = item.select_one("p.star-rating")
        avail_el  = item.select_one("p.availability")

        if not name_el:
            continue

        name  = name_el.get("title", "").strip()
        price = price_el.get_text(strip=True) if price_el else None

        # Rating: class="star-rating Three" → "3"
        rating = None
        if rating_el:
            cls   = rating_el.get("class", [])
            word  = next((c for c in cls if c != "star-rating"), None)
            rating = RATING_MAP.get(word)

        avail = None
        if avail_el:
            avail = "In stock" if "In stock" in avail_el.get_text() else "Out of stock"

        # Build product URL from relative href
        href = name_el.get("href", "")
        href_clean = href.replace("../", "")
        product_url = f"https://books.toscrape.com/catalogue/{href_clean}"

        # XPath for provenance (position-based, matches ground truth pattern)
        source_xpath = (
            f"/html/body/div/div/div/div/section/div[2]/ol/li[{i}]/article/h3/a"
        )

        records.append({
            "record_id":   str(i),
            "name":        name,
            "price":       price,
            "rating":      rating,
            "availability": avail,
            "product_url": product_url,
            "source_url":  SOURCE_URL,
            "source_xpath": source_xpath,
        })

    return records[:10]


def main():
    start = time.time()
    records = scrape_books()
    elapsed = round(time.time() - start, 3)

    OUTPUT.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    log = {
        "agent":            "traditional_scraper",
        "site_id":          "books",
        "start_time":       time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds":  elapsed,
        "tokens_input":     0,
        "tokens_output":    0,
        "estimated_cost":   0.0,
        "num_records":      len(records),
        "status":           "success",
        "error":            None,
    }
    LOG_OUT.write_text(json.dumps(log, indent=2))

    print(f"[books] {len(records)} records → {OUTPUT}  ({elapsed}s)")
    return records


if __name__ == "__main__":
    main()
