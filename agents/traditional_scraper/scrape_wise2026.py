"""
Agent 1 - Traditional Scraper: conferences.sigappfr.org/wise2026/call-for-papers/
Conference CFP page. Extracts 1 structured record.
NOTE: conference_dates and location are not in the CFP snapshot —
the scraper correctly returns null for these, demonstrating the extraction
gap that agentic approaches may address via multi-page navigation.
Output: outputs/traditional_scraper/conference_wise2026.json
"""

import json, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SOURCE_URL = "https://conferences.sigappfr.org/wise2026/call-for-papers/"
SNAPSHOT   = Path("data/snapshots/conferences/wise2026_cfp.html")
OUTPUT     = Path("outputs/traditional_scraper/conference_wise2026.json")
LOG_OUT    = Path("logs/traditional_scraper/wise2026_log.json")

Path("outputs/traditional_scraper").mkdir(parents=True, exist_ok=True)
Path("logs/traditional_scraper").mkdir(parents=True, exist_ok=True)


def scrape_wise2026() -> list[dict]:
    html = SNAPSHOT.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # Full name not in CFP HTML; identified from WISE standard name
    conference_name = "International Conference on Web Information Systems Engineering"
    acronym = "WISE"

    # Dates: snapshot has 3 date lines as plain text
    #   17 June 2026   → submission
    #   20 July 2026   → notification
    #   25 August 2026 → camera-ready (NOT conference dates)
    # Conference dates (2-5 November 2026) not in this snapshot.
    full_text = soup.get_text(separator="\n")
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    date_re = re.compile(
        r"^(\d{1,2}(?:\s*[-–]\s*\d{1,2})?\s+\w+\s+202[56])$", re.IGNORECASE
    )
    date_values = []
    seen_dates = set()
    for line in lines:
        m = date_re.match(line)
        if m and m.group(1) not in seen_dates:
            date_values.append(m.group(1))
            seen_dates.add(m.group(1))

    submission_deadline = date_values[0] if len(date_values) > 0 else None
    notification_date   = date_values[1] if len(date_values) > 1 else None
    conference_dates    = None  # not present in this page's snapshot
    location            = None  # "Venice, Italy" not present in CFP snapshot

    # Topics: find the ul with web/AI research topics
    topics = []
    for ul in soup.select("ul"):
        items = ul.select("li")
        if len(items) >= 10:
            texts = [li.get_text(strip=True) for li in items if li.get_text(strip=True)]
            web_kws = {"web", "ai", "data", "mining", "semantic", "cloud",
                       "learning", "social", "knowledge", "computing", "linked"}
            if sum(1 for t in texts if any(k in t.lower() for k in web_kws)) >= 5:
                topics = texts
                break

    submission_url = None
    for a in soup.select("a[href*='cmt'], a[href*='easychair'], a[href*='edas']"):
        submission_url = a["href"]
        break

    source_xpath = (
        "/html/body/div[1]/div[3]/div[2]/div/div[1]/div/div/div[1]"
        "/div/div/div/div[2]/div/div/div/div[7]"
    )

    return [{
        "record_id":           "1",
        "conference_name":     conference_name,
        "acronym":             acronym,
        "submission_deadline": submission_deadline,
        "notification_date":   notification_date,
        "conference_dates":    conference_dates,
        "location":            location,
        "topics":              topics,
        "submission_url":      submission_url,
        "source_url":          SOURCE_URL,
        "source_xpath":        source_xpath,
    }]


def main():
    start   = time.time()
    records = scrape_wise2026()
    elapsed = round(time.time() - start, 3)

    OUTPUT.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    log = {
        "agent":           "traditional_scraper",
        "site_id":         "conference_wise2026",
        "start_time":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds": elapsed,
        "tokens_input":    0, "tokens_output": 0,
        "estimated_cost":  0.0,
        "num_records":     len(records),
        "status":          "success", "error": None,
    }
    LOG_OUT.write_text(json.dumps(log, indent=2))

    print(f"[wise2026] {len(records)} record → {OUTPUT}  ({elapsed}s)")
    if records:
        r = records[0]
        print(f"  name:     {r['conference_name']}")
        print(f"  deadline: {r['submission_deadline']}")
        print(f"  notif:    {r['notification_date']}")
        print(f"  dates:    {r['conference_dates']}  ← not in snapshot")
        print(f"  location: {r['location']}  ← not in snapshot")
        print(f"  topics:   {len(r['topics'])} items")
        print(f"  submit:   {r['submission_url']}")
    return records


if __name__ == "__main__":
    main()
