"""Capture real screenshots of the running review app for the slides.

Usage: start the app (streamlit run app/streamlit_app.py), install playwright, then run
python scripts/capture_app_screens.py. Uses the Edge browser already on the machine.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from calltrace.config import load_config

URL = "http://localhost:8501"


def main() -> None:
    figures = load_config().path("reports") / "figures"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 950})
        page.goto(URL)
        page.get_by_text("Summary with evidence").wait_for(timeout=60000)
        page.wait_for_timeout(2500)
        page.screenshot(path=figures / "app_call_overview.png")

        # Click the first evidence reference, as a reviewer would.
        button = page.get_by_role("button", name="T0002").first
        button.click()
        page.get_by_text("Selected evidence: 001-T0002").wait_for(timeout=30000)
        page.wait_for_timeout(2500)
        page.screenshot(path=figures / "app_evidence_selected.png")

        # Click evidence from later in the call, so the transcript visibly scrolls to it.
        outcome_button = page.get_by_role("button", name="T0043").first
        outcome_button.click()
        page.get_by_text("Selected evidence: 001-T0043").wait_for(timeout=30000)
        page.wait_for_timeout(2500)
        page.screenshot(path=figures / "app_evidence_outcome.png")

        # The flagged call, showing limitations in the interface.
        page.locator("[data-testid=stSelectbox]").first.click()
        page.get_by_role("option", name="005").click()
        page.get_by_text("Check this call first.").wait_for(state="attached", timeout=30000)
        page.evaluate("document.querySelector('[data-testid=stMain]').scrollTo(0, 0)")
        page.wait_for_timeout(2500)
        page.screenshot(path=figures / "app_flagged_call.png")
        browser.close()
    print(figures)


if __name__ == "__main__":
    main()
