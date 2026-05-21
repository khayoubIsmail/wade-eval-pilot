"""
Agent 1 - Traditional Scraper: icitri.nusamandiri.ac.id
Conference CFP page. Extracts 1 structured record.
Output: outputs/traditional_scraper/conference_icitri.json
"""

import json, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SOURCE_URL = "https://icitri.nusamandiri.ac.id/"
SNAPSHOT   = Path("data/snapshots/conferences/icitri.html")
OUTPUT     = Path("outputs/traditional_scraper/conference_icitri.json")
LOG_OUT    = Path("logs/traditional_scraper/icitri_log.json")

Path("outputs/traditional_scraper").mkdir(parents=True, exist_ok=True)
Path("logs/traditional_scraper").mkdir(parents=True, exist_ok=True)


def scrape_icitri() -> list[dict]:
    html = SNAPSHOT.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # ── Conference name: og:title contains full name ──────────────────────
    conference_name = None
    acronym = "ICITRI"

    og = soup.select_one("meta[property='og:title']")
    if og:
        raw = og.get("content", "")
        # "ICITRI 2026 - International Conference on Information Technology..."
        match = re.search(r"International Conference[^\"]+", raw, re.IGNORECASE)
        conference_name = match.group(0).strip() if match else None

    if not conference_name:
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc:
            content = meta_desc.get("content", "")
            match = re.search(r"INTERNATIONAL CONFERENCE[^(]+", content, re.IGNORECASE)
            conference_name = match.group(0).strip().title() if match else None

    # ── Important dates ───────────────────────────────────────────────────
    # Table structure:
    #   Paper Submission        → extended: "30 June 2026"
    #   Notification of Paper   → extended: "25 July 2026"
    #   Camera Ready            → extended: "7 August 2026"
    #   Conference Day          → "10 September 2026" (no extension)
    submission_deadline = None
    notification_date   = None
    conference_dates    = None

    dates_section = soup.select_one("section#important-dates")
    if dates_section:
        for row in dates_section.select("tr"):
            tds = row.select("td")
            if len(tds) < 2:
                continue
            event = tds[0].get_text(strip=True).lower()

            # Use extended date span if present
            extended_el = tds[1].select_one("span.extended-date")
            if extended_el:
                date_str = extended_el.get_text(strip=True)
            else:
                # Remove strikethough spans, clean remaining text
                for s in tds[1].select("span.old-date-strike, sup"):
                    s.decompose()
                date_str = tds[1].get_text(" ", strip=True)
                date_str = re.sub(r"\s+", " ", date_str).strip()

            # Remove badge noise
            date_str = re.sub(r"\s*extend.*", "", date_str, flags=re.IGNORECASE).strip()

            if "submission" in event and "camera" not in event:
                submission_deadline = date_str
            elif "notification" in event:
                notification_date = date_str
            elif "conference" in event or "conference day" in event:
                conference_dates = date_str

    # ── Location ─────────────────────────────────────────────────────────
    location = None
    full_text = soup.get_text()
    for pattern in [
        r"Universitas Nusa Mandiri[^,\n]{0,15},?\s*Depok[^,\n]{0,20}(?:,\s*Indonesia)?",
        r"Depok,\s*Indonesia(?:\s*\(Hybrid\))?",
    ]:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            location = match.group(0).strip()
            break

    # ── Topics: combine all research-topic ULs ────────────────────────────
    topics = []
    topic_kws = {"ai","machine","learning","data","software","computing","bio",
                 "signal","image","web","human","clinical","biometrics","knowledge",
                 "requirements","component","model","mobile","cloud","security"}
    seen_topics = set()

    for ul in soup.select("ul, ol"):
        items = ul.select("li")
        if len(items) < 3:
            continue
        texts = [li.get_text(strip=True) for li in items if li.get_text(strip=True)]
        # Skip committee/person lists
        has_person = any(
            re.search(r"\b(University|Institute|Prof\.|Dr\.|Universitas)\b", t)
            for t in texts[:3]
        )
        if has_person:
            continue
        matches = sum(1 for t in texts if any(k in t.lower() for k in topic_kws))
        if matches >= 2:
            for t in texts:
                if t not in seen_topics:
                    topics.append(t)
                    seen_topics.add(t)

    # ── Submission URL ────────────────────────────────────────────────────
    submission_url = None
    for a in soup.select("a[href*='edas'], a[href*='easychair'], a[href*='cmt']"):
        submission_url = a["href"]
        break

    source_xpath = "/html/body/section[5]"

    record = {
        "record_id":            "1",
        "conference_name":      conference_name,
        "acronym":              acronym,
        "submission_deadline":  submission_deadline,
        "notification_date":    notification_date,
        "conference_dates":     conference_dates,
        "location":             location,
        "topics":               topics,
        "submission_url":       submission_url,
        "source_url":           SOURCE_URL,
        "source_xpath":         source_xpath,
    }
    return [record]


def main():
    start   = time.time()
    records = scrape_icitri()
    elapsed = round(time.time() - start, 3)

    OUTPUT.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    log = {
        "agent":           "traditional_scraper",
        "site_id":         "conference_icitri",
        "start_time":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_seconds": elapsed,
        "tokens_input":    0, "tokens_output": 0,
        "estimated_cost":  0.0,
        "num_records":     len(records),
        "status":          "success", "error": None,
    }
    LOG_OUT.write_text(json.dumps(log, indent=2))

    print(f"[icitri] {len(records)} record → {OUTPUT}  ({elapsed}s)")
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
