"""
naukri.py
Search Naukri job listings (India).
"""

from playwright.sync_api import Page
from typing import List, Dict
import time
import urllib.parse

def search_jobs(page: Page, role: str, location: str, max_results: int = 10, max_age_days: int = 7) -> List[Dict]:
    jobs = []
    q = urllib.parse.quote_plus(role)
    l = urllib.parse.quote_plus(location)
    query_params = urllib.parse.urlencode({
        "jobAge": max_age_days,
        # "sort": "date",
    })
    url = f"https://www.naukri.com/{q}-jobs-in-{l}?{query_params}"
    print(f"Naukri search URL: {url}")
    page.goto(url)
    time.sleep(2)
    # Naukri opens many popups; try to close common ones
    try:
        close_btn = page.query_selector("button[aria-label='close']") or page.query_selector(".close")
        if close_btn:
            close_btn.click()
    except Exception:
        pass

    cards = page.query_selector_all(".jobTuple, div.srp-jobtuple-wrapper, article.jobTuple, div[class*='jobTuple']")
    for i, card in enumerate(cards):
        if i >= max_results:
            break
        try:
            title_el = (
                card.query_selector("a.title")
                or card.query_selector("a[title][href*='job-listings']")
                or card.query_selector("a[href*='job-listings']")
            )
            company_el = (
                card.query_selector(".companyInfo .subTitle")
                or card.query_selector("a.comp-name")
                or card.query_selector(".comp-name")
            )
            link = title_el.get_attribute("href") if title_el else None
            loc_el = (
                card.query_selector(".jobTuple .location .ellipsis")
                or card.query_selector(".locWdth")
                or card.query_selector("[title*='location']")
            )
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
