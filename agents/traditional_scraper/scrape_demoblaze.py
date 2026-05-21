"""
Agent 1 - Traditional Scraper: demoblaze.com
DemoBlaze is JS-rendered. We use the saved snapshot (captured after JS loaded).
Output: outputs/traditional_scraper/ecommerce_demoblaze.json
"""

import json, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.demoblaze.com/index.html"
SNAPSHOT   = Path("data/snapshots/ecommerce/demoblaze.html")
OUTPUT     = Path("outputs/traditional_scraper/ecommerce_demoblaze.json")
LOG_OUT    = Path("logs/traditional_scraper/demoblaze_log.json")
BASE_URL   = "https://www.demoblaze.com"

Path("outputs/traditional_scraper").mkdir(parents=True, exist_ok=True)
Path("logs/traditional_scraper").mkdir(parents=True, exist_ok=True)


def scrape_demoblaze() -> list[dict]:
    html  = SNAPSHOT.read_text(encoding="utf-8")
    soup  = BeautifulSoup(html, "html.parser")

    # DemoBlaze structure: div.card.h-100 > div.card-block > h4.card-title > a.hrefch
    cards   = soup.select("div.card.h-100")
    records = []

    for i, card in enumerate(cards, start=1):
        name_el  = card.select_one("h4.card-title a.hrefch")
        price_el = card.select_one("h5")

        if not name_el:
            # fallback: any link inside card-title
            name_el = card.select_one(".card-title a")
        if not name_el:
            continue

        name = name_el.get_text(strip=True)
        href = name_el.get("href", "")
        product_url = BASE_URL + "/" + href if not href.startswith("http") else href

        # Price: raw text like "$360" — keep as-is to match ground truth
        price = None
        if price_el:
            price = price_el.get_text(strip=True)
            if price and not price.startswith("$"):
                price = "$" + price

        # DemoBlaze has no rating or availability on listing page
        source_xpath = (
            f"/html/body/div[5]/div/div[2]/div/div[{i}]/div/div/h4/a"
        )

        records.append({
            "record_id":    str(i),
            "name":         name,
            "price":        price,
            "rating":       None,
            "availability": None,
            "product_url":  product_url,
            "source_url":   SOURCE_URL,
            "source_xpath": source_xpath,
        })

    return records[:9]


def main():
    start   = time.time()
    records = scrape_demoblaze()
    elapsed = round(time.time() - start, 3)

    OUTPUT.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    log = {
        "agent":           "traditional_scraper",
        "site_id":         "ecommerce_demoblaze",
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

    print(f"[demoblaze] {len(records)} records → {OUTPUT}  ({elapsed}s)")
    return records[:9]


if __name__ == "__main__":
    main()
