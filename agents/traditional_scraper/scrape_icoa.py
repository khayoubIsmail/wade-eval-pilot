"""
Agent 1 - Traditional Scraper: icoa-conf.org
Conference CFP page. Extracts 1 structured record.
Output: outputs/traditional_scraper/conference_icoa.json
"""

import json, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SOURCE_URL = "http://icoa-conf.org/index.html"
SNAPSHOT   = Path("data/snapshots/conferences/icoa.html")
OUTPUT     = Path("outputs/traditional_scraper/conference_icoa.json")
LOG_OUT    = Path("logs/traditional_scraper/icoa_log.json")

Path("outputs/traditional_scraper").mkdir(parents=True, exist_ok=True)
Path("logs/traditional_scraper").mkdir(parents=True, exist_ok=True)


def scrape_icoa() -> list[dict]:
    html = SNAPSHOT.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # ── Conference name & acronym ─────────────────────────────────────────
    conference_name = "International Conference on Optimization and Applications"
    acronym = "ICOA"

    # ── Dates ─────────────────────────────────────────────────────────────
    # ICOA snapshot structure (confirmed from inspection):
    #   "Submission Deadline"       → next line: "May 30, 2026 (Full Paper)"
    #   "Notification of Acceptance"→ next line: "July 10, 2026"
    #   "October 29-30, 2026"       → conference dates
    submission_deadline = None
    notification_date   = None
    conference_dates    = None

    for i, line in enumerate(lines):
        ll = line.lower()

        if "submission deadline" in ll and submission_deadline is None:
            # Next non-empty line is the date
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j]
                if re.search(r"\d{4}", candidate):
                    # Strip parenthetical note like "(Full Paper)"
                    submission_deadline = re.sub(r"\s*\(.*\)", "", candidate).strip()
                    break

        elif "notification of acceptance" in ll and notification_date is None:
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j]
                if re.search(r"\d{4}", candidate):
                    notification_date = candidate.strip()
                    break

        elif re.search(r"october\s+\d{1,2}[-–]\d{1,2},?\s*202[56]", line, re.IGNORECASE):
            # "October 29-30, 2026" → normalise to "29-30 October 2026"
            m = re.search(
                r"october\s+(\d{1,2})[-–](\d{1,2}),?\s*(202[56])",
                line, re.IGNORECASE
            )
            if m:
                conference_dates = f"{m.group(1)}-{m.group(2)} October {m.group(3)}"

    # ── Location ─────────────────────────────────────────────────────────
    location = None
    for pat in [
        r"Higher School of Technology[^\n,]{0,20}(?:–|-)\s*Dakhla[^,\n]{0,20}Morocco",
        r"Higher School of Technology of Dakhla[^,\n]{0,20}Morocco",
        r"Dakhla[^\n,]{0,10}Morocco",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            location = m.group(0).strip()
            break

    # ── Topics: text-based extraction after "List of topics" marker ─────
    topics = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    stop_words = {"committee", "chair", "organiz", "sponsor", "contact",
                  "registration", "honorary", "keynote", "prof.", "dr."}

    for i, line in enumerate(lines):
        if "list of topics" in line.lower():
            for j in range(i + 2, min(i + 70, len(lines))):
                t = lines[j]
                if any(sw in t.lower() for sw in stop_words):
                    break
                if len(t) > 80 or len(t) < 4:
                    continue
                topics.append(t)
            break

    # Remove ALL-CAPS section headers and non-topic noise lines (fees, guidelines, etc.)
    noise_patterns = re.compile(
        r"^(TOOLS AND METHODS|FIELDS AND AREAS|Submission|Only electronic|"
        r"the IEEE|Fees|Select|Student|Face to Face|Paper sub|List of|"
        r"Online:|Academics|Industrials|IEEE Members|Extra paper|Gala|"
        r"Listener|\d+\s*€|–\s*\d|1 paper|\d+ paper)",
        re.IGNORECASE
    )
    topics = [
        t for t in topics
        if not noise_patterns.match(t)
        and not t.isupper()
        and "€" not in t
        and not re.match(r"^\d", t)
    ]

    # ── Submission URL ────────────────────────────────────────────────────
    submission_url = None
    for a in soup.select("a[href*='cmt'], a[href*='easychair'], a[href*='edas']"):
        submission_url = a["href"]
        break

    # source_xpath matches ground truth
    source_xpath = "/html/body/section[6]/div/div/div[3]/div[4]/div"

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
    records = scrape_icoa()
    elapsed = round(time.time() - start, 3)

    OUTPUT.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    log = {
        "agent":           "traditional_scraper",
        "site_id":         "conference_icoa",
        "start_time":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds": elapsed,
        "tokens_input":    0, "tokens_output": 0,
        "estimated_cost":  0.0,
        "num_records":     len(records),
        "status":          "success", "error": None,
    }
    LOG_OUT.write_text(json.dumps(log, indent=2))

    print(f"[icoa] {len(records)} record → {OUTPUT}  ({elapsed}s)")
    if records:
        r = records[0]
        print(f"  name:     {r['conference_name']}")
        print(f"  deadline: {r['submission_deadline']}")
        print(f"  notif:    {r['notification_date']}")
        print(f"  dates:    {r['conference_dates']}")
        print(f"  location: {r['location']}")
        print(f"  topics:   {len(r['topics'])} items")
        print(f"  submit:   {r['submission_url']}")
    return records


if __name__ == "__main__":
    main()
