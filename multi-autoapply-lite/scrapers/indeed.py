"""
indeed.py
Search Indeed job listings and return basic job metadata.
"""

from playwright.sync_api import Page
from typing import List, Dict
import time
import urllib.parse

def search_jobs(page: Page, role: str, location: str, max_results: int = 10) -> List[Dict]:
    jobs = []
    q = urllib.parse.quote_plus(role)
    l = urllib.parse.quote_plus(location)
    url = f"https://www.indeed.com/jobs?q={q}&l={l}"
    
    print(f"Navigating to: {url}")
    page.goto(url, wait_until="networkidle")
    time.sleep(3)  # Increased initial wait
    
    # Scroll to load more content
    for _ in range(3):
        page.mouse.wheel(0, 1000)
        time.sleep(1)
    
    # Try multiple selectors that Indeed uses
    selectors_to_try = [
        "a.jcs-JobTitle",  # Updated selector
        "div.job_seen_beacon",  # Job card container
        "div.cardOutline",  # Alternative card selector
        "a.tapItem",  # Original selector
        ".jobsearch-SerpJobCard",  # Fallback
        "div[data-jk]",  # Jobs with data-jk attribute
    ]
    
    cards = []
    for selector in selectors_to_try:
        cards = page.query_selector_all(selector)
        if cards:
            print(f"Found {len(cards)} job cards using selector: {selector}")
            break
    
    if not cards:
        # Debug: save screenshot and HTML
        print("No job cards found. Saving debug info...")
        page.screenshot(path="indeed_debug.png")
        with open("indeed_debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("Saved indeed_debug.png and indeed_debug.html for inspection")
        return jobs
    
    for i, card in enumerate(cards):
        if i >= max_results:
            break
        try:
            # Try multiple title selectors
            title_el = (
                card.query_selector("h2.jobTitle span[title]") or
                card.query_selector("h2.jobTitle span") or
                card.query_selector("h2 span[title]") or
                card.query_selector("a.jcs-JobTitle span") or
                card.query_selector("h2") or
                card.query_selector("a.jcs-JobTitle")
            )
            
            # Try multiple company selectors
            company_el = (
                card.query_selector("span[data-testid='company-name']") or
                card.query_selector(".companyName") or
                card.query_selector("span.companyName") or
                card.query_selector("[data-testid='company-name']")
            )
            
            # Try multiple location selectors
            loc_el = (
                card.query_selector("div[data-testid='text-location']") or
                card.query_selector(".companyLocation") or
                card.query_selector("span.companyLocation") or
                card.query_selector("[data-testid='text-location']")
            )
            
            # Get link - check if card itself is a link or has a link child
            link = None
            if card.evaluate("el => el.tagName") == "A":
                link = card.get_attribute("href")
            else:
                link_el = card.query_selector("a.jcs-JobTitle") or card.query_selector("a")
                if link_el:
                    link = link_el.get_attribute("href")
            
            # Construct full URL
            if link:
                if link.startswith("/"):
                    link = "https://www.indeed.com" + link
                elif not link.startswith("http"):
                    link = "https://www.indeed.com/" + link
            
            # Extract text
            role_text = title_el.inner_text().strip() if title_el else ""
            company_text = company_el.inner_text().strip() if company_el else ""
            location_text = loc_el.inner_text().strip() if loc_el else ""
            
            # Only add if we have at least a title and link
            if role_text and link:
                jobs.append({
                    "role": role_text,
                    "company": company_text,
                    "location": location_text,
                    "link": link
                })
                print(f"  [{i+1}] {role_text} @ {company_text}")
            
        except Exception as e:
            print(f"Error parsing job card {i}: {e}")
            continue
    
    print(f"Successfully parsed {len(jobs)} jobs")
    return jobs