"""
glassdoor.py
Search Glassdoor job listings and extract basic metadata.

Glassdoor has rate-limits and anti-bot measures. Use carefully.
"""

from playwright.sync_api import Page
from typing import List, Dict
import time
import urllib.parse

def search_jobs(page: Page, role: str, location: str, max_results: int = 10) -> List[Dict]:
    jobs = []
    q = urllib.parse.quote_plus(role)
    l = urllib.parse.quote_plus(location)
    url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&locT=C&locId=&locKeyword={l}"
    page.goto(url)
    time.sleep(2)

    # Scroll to load results
    for _ in range(3):
        page.mouse.wheel(0, 800)
        time.sleep(0.8)

    cards = page.query_selector_all("li.react-job-listing")
    if not cards:
        cards = page.query_selector_all(".jl")  # fallback
    for i, card in enumerate(cards):
        if i >= max_results:
            break
        try:
            title_el = card.query_selector(".jobLink")
            company_el = card.query_selector(".jobEmpolyerName") or card.query_selector(".jobInfoItem .empLoc")
            link_el = card.query_selector("a")
            link = link_el.get_attribute("href") if link_el else None
            if link and link.startswith("/"):
                link = "https://www.glassdoor.com" + link
            role_text = title_el.inner_text().strip() if title_el else ""
            company_text = company_el.inner_text().strip() if company_el else ""
            location_text = ""  # Glassdoor often includes location in other element
            jobs.append({
                "role": role_text,
                "company": company_text,
                "location": location_text,
                "link": link
            })
        except Exception:
            continue
    return jobs
