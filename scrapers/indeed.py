
from playwright.sync_api import Page
from typing import List, Dict
import time
import urllib.parse

def search_jobs(page: Page, role: str, location: str, max_results: int = 10) -> List[Dict]:
    jobs = []
    q = urllib.parse.quote_plus(role)
    l = urllib.parse.quote_plus(location)
    
    # Use regional Indeed site for India
    if "india" in location.lower():
        base_url = "https://in.indeed.com"
    else:
        base_url = "https://www.indeed.com"
    
    url = f"{base_url}/jobs?q={q}&l={l}"
    
    print(f"Navigating to: {url}")
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)
        
        # Scroll to load more content
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(1.5)
        
        # Try multiple selectors
        selectors_to_try = [
            "div.job_seen_beacon",  # Most common current selector
            "td.resultContent",  # Table-based layout
            "div.cardOutline",
            "a.jcs-JobTitle",
            "div[data-jk]",  # Jobs with data-jk attribute
            "li.css-5lfssm",  # Alternative list item
            "div.slider_container > div",
        ]
        
        cards = []
        for selector in selectors_to_try:
            cards = page.query_selector_all(selector)
            if cards:
                print(f"Found {len(cards)} job cards using selector: {selector}")
                break
        
        if not cards:
            print("No job cards found. Saving debug info...")
            page.screenshot(path="indeed_debug.png")
            with open("indeed_debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Saved indeed_debug.png and indeed_debug.html")
            
            # Check if we hit a CAPTCHA
            captcha_text = page.content().lower()
            if "captcha" in captcha_text or "robot" in captcha_text:
                print("⚠️  CAPTCHA detected! Indeed is blocking automated access.")
                print("Solutions:")
                print("  1. Run with --no-headless and solve CAPTCHA manually")
                print("  2. Use a different IP/VPN")
                print("  3. Add delays between requests")
            
            return jobs
        
        for i, card in enumerate(cards):
            if i >= max_results:
                break
            try:
                # Multiple title selectors
                title_el = (
                    card.query_selector("h2.jobTitle span") or
                    card.query_selector("h2 span[title]") or
                    card.query_selector("a.jcs-JobTitle span") or
                    card.query_selector("h2.jobTitle") or
                    card.query_selector("a[data-jk]") or
                    card.query_selector("h2")
                )
                
                # Multiple company selectors
                company_el = (
                    card.query_selector("span[data-testid='company-name']") or
                    card.query_selector("span.companyName") or
                    card.query_selector("div.company_location > span:first-child") or
                    card.query_selector("[data-testid='company-name']")
                )
                
                # Multiple location selectors
                loc_el = (
                    card.query_selector("div[data-testid='text-location']") or
                    card.query_selector("div.companyLocation") or
                    card.query_selector("span.companyLocation") or
                    card.query_selector(".css-1p0sjhy")
                )
                
                # Get link
                link = None
                
                # Method 1: Check data-jk attribute (job key)
                job_key = card.get_attribute("data-jk")
                if job_key:
                    link = f"{base_url}/viewjob?jk={job_key}"
                else:
                    # Method 2: Find link element
                    link_el = (
                        card.query_selector("a.jcs-JobTitle") or
                        card.query_selector("h2.jobTitle a") or
                        card.query_selector("a[data-jk]") or
                        card.query_selector("a[id^='job_']")
                    )
                    
                    if link_el:
                        link = link_el.get_attribute("href")
                        if link and link.startswith("/"):
                            link = base_url + link
                        elif link and not link.startswith("http"):
                            link = base_url + "/" + link
                
                # Extract text
                role_text = title_el.inner_text().strip() if title_el else ""
                company_text = company_el.inner_text().strip() if company_el else ""
                location_text = loc_el.inner_text().strip() if loc_el else location
                
                # Clean up role text (remove "new" badges, etc.)
                if role_text:
                    role_text = role_text.replace("new", "").strip()
                
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
        
        print(f"Successfully parsed {len(jobs)} Indeed jobs")
        
    except Exception as e:
        print(f"Error during Indeed search: {e}")
    
    return jobs

