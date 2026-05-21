import yaml
import json
from pathlib import Path
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright


def ensure_parent(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def capture_site(page, site):
    page.goto(site["url"], wait_until="domcontentloaded", timeout=90000)

    # General wait for dynamic content
    page.wait_for_timeout(5000)

    # Demoblaze products need JS rendering
    if site["id"] == "ecommerce_demoblaze":
        try:
            page.wait_for_selector(".card-title", timeout=20000)
            page.wait_for_timeout(3000)
        except Exception:
            print("Warning: Demoblaze product cards not detected.")

    # WISE CFP page: wait for main page content
    if site["id"] == "conference_wise2026":
        try:
            page.wait_for_selector("body", timeout=20000)
            page.wait_for_timeout(3000)
        except Exception:
            print("Warning: WISE CFP content not fully detected.")

    return page.content()


def main():
    with open("config/sites.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    run_log = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        for site in config["sites"]:
            print(f"Capturing: {site['id']}")
            page = context.new_page()
            timestamp = datetime.now(timezone.utc).isoformat()

            try:
                html = capture_site(page, site)

                ensure_parent(site["snapshot_path"])
                ensure_parent(site["screenshot_path"])

                Path(site["snapshot_path"]).write_text(html, encoding="utf-8")
                page.screenshot(path=site["screenshot_path"], full_page=True)

                status = "success"
                error = None

            except Exception as e:
                status = "failed"
                error = str(e)
                print(f"FAILED: {site['id']} -> {error}")

            run_log.append({
                "site_id": site["id"],
                "url": site["url"],
                "snapshot_path": site["snapshot_path"],
                "screenshot_path": site["screenshot_path"],
                "captured_at_utc": timestamp,
                "status": status,
                "error": error
            })

            page.close()

        context.close()
        browser.close()

    Path("logs").mkdir(exist_ok=True)
    Path("logs/capture_log.json").write_text(
        json.dumps(run_log, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Done. Check logs/capture_log.json")


if __name__ == "__main__":
    main()