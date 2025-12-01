"""
naukri.py
Search Naukri job listings (India).
"""

from playwright.sync_api import Page
from typing import List, Dict
import time
import urllib.parse

def search_jobs(page: Page, role: str, location: str, max_results: int = 10) -> List[Dict]:
    jobs = []
    q = urllib.parse.quote_plus(role)
    l = urllib.parse.quote_plus(location)
    url = f"https://www.naukri.com/{q}-jobs-in-{l}"
    page.goto(url)
    time.sleep(2)
    # Naukri opens many popups; try to close common ones
    try:
        close_btn = page.query_selector("button[aria-label='close']") or page.query_selector(".close")
        if close_btn:
            close_btn.click()
    except Exception:
        pass

    cards = page.query_selector_all(".jobTuple")
    for i, card in enumerate(cards):
        if i >= max_results:
            break
        try:
            title_el = card.query_selector("a.title")
            company_el = card.query_selector(".companyInfo .subTitle")
            link = title_el.get_attribute("href") if title_el else None
            loc_el = card.query_selector(".jobTuple .location .ellipsis")
            role_text = title_el.inner_text().strip() if title_el else ""
            company_text = company_el.inner_text().strip() if company_el else ""
            location_text = loc_el.inner_text().strip() if loc_el else ""
            jobs.append({
                "role": role_text,
                "company": company_text,
                "location": location_text,
                "link": link
            })
        except Exception:
            continue
    return jobs
