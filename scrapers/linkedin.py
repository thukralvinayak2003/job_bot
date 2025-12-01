from playwright.sync_api import Page
from typing import List, Dict
import time
from database import db

def search_jobs(page: Page, role: str, location: str, max_results: int = 10) -> List[Dict]:
    jobs = []
    
    # Get already applied jobs from database to filter them out
    applied_jobs = db.get_applied_job_links()
    print(f"Found {len(applied_jobs)} already applied jobs in database")
    
    query = role.replace(" ", "%20")
    # Force India as the search location
    location = "India"
    loc = "India".replace(" ", "%20")

    url = f"https://www.linkedin.com/jobs/search?keywords={query}&location={loc}"

    print(f"Navigating to: {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(4)

        current_page = 1
        max_pages = 3  # Limit pages to avoid infinite scrolling
        
        while len(jobs) < max_results and current_page <= max_pages:
            print(f"\n--- Searching Page {current_page} ---")
            
            # Scroll to load lazy elements
            for _ in range(4):
                page.evaluate("window.scrollBy(0, 1200)")
                time.sleep(1)

            # NEW LinkedIn 2025 job card selectors
            job_cards = page.query_selector_all("li.jobs-search-results__list-item")

            if not job_cards:
                job_cards = page.query_selector_all("div[data-job-id]")

            if not job_cards:
                print("⚠ No job cards detected on this page.")
                break

            print(f"Found {len(job_cards)} cards on page {current_page}")

            jobs_found_on_page = 0
            for i, card in enumerate(job_cards):
                try:
                    # Stop if we have enough new jobs
                    if len(jobs) >= max_results:
                        break
                        
                    # Best-effort: try specific elements first, then fallback to splitting card text
                    link_el = (
                        card.query_selector("a.base-card__full-link") or
                        card.query_selector("a[href*='/jobs/view/']") or
                        card.query_selector("a[data-control-name='job_card_click']") or
                        card.query_selector("a")
                    )

                    link = None
                    if link_el:
                        link = link_el.get_attribute("href")
                        if link and link.startswith("/"):
                            link = "https://www.linkedin.com" + link
                        if link and "?" in link:
                            link = link.split("?")[0]

                    # Skip if no link found
                    if not link:
                        continue
                        
                    # Skip if already applied to this job
                    if link in applied_jobs:
                        print(f"⏭️  Skipping already applied job: {link}")
                        continue

                    # Try explicit title/company/location selectors
                    title_el = (
                        card.query_selector("h3.base-search-card__title") or
                        card.query_selector("h3") or
                        card.query_selector(".job-card-list__title") or
                        card.query_selector(".job-card-container__title")
                    )

                    company_el = (
                        card.query_selector("h4.base-search-card__subtitle") or
                        card.query_selector("h4") or
                        card.query_selector(".job-card-container__company-name") or
                        card.query_selector(".result-card__subtitle-link")
                    )

                    loc_el = (
                        card.query_selector("span.job-search-card__location") or
                        card.query_selector("span.job-result-card__location") or
                        card.query_selector(".job-card-container__metadata-item") or
                        card.query_selector(".job-card-list__location")
                    )

                    role_text = title_el.inner_text().strip() if title_el and title_el.inner_text() else ""
                    company_text = company_el.inner_text().strip() if company_el and company_el.inner_text() else ""
                    location_text = loc_el.inner_text().strip() if loc_el and loc_el.inner_text() else location

                    # Fallback: use full card text lines if specific selectors didn't produce values
                    if (not role_text or not company_text) and card.inner_text():
                        parts = [s.strip() for s in card.inner_text().splitlines() if s.strip()]
                        # Heuristics: first non-empty line likely role, second likely company
                        if not role_text and len(parts) >= 1:
                            role_text = parts[0]
                        if not company_text and len(parts) >= 2:
                            company_text = parts[1]
                        if (not location_text or location_text == location) and len(parts) >= 3:
                            # sometimes location is third line
                            location_text = parts[2]

                    if role_text and link:
                        jobs.append({
                            "role": role_text,
                            "company": company_text,
                            "location": location_text,
                            "link": link
                        })
                        jobs_found_on_page += 1
                        print(f"  [{len(jobs)}] {role_text} @ {company_text}")

                except Exception as e:
                    print(f"Error parsing job card {i}: {e}")
                    continue

            print(f"Found {jobs_found_on_page} new jobs on page {current_page}")
            
            # Check if we need more jobs and there's a next page
            if len(jobs) < max_results:
                if go_to_next_page(page):
                    current_page += 1
                    time.sleep(3)  # Wait for next page to load
                else:
                    print("No more pages available or cannot navigate to next page")
                    break
            else:
                break

        print(f"\n✅ Successfully parsed {len(jobs)} new LinkedIn jobs across {current_page} pages")
        print(f"⏭️  Filtered out {len(applied_jobs)} already applied jobs")

    except Exception as e:
        print(f"Error during LinkedIn search: {e}")

    return jobs

def go_to_next_page(page: Page) -> bool:
    """
    Try to navigate to the next page of job results.
    Returns True if successful, False otherwise.
    """
    try:
        # Try different selectors for next page button
        next_selectors = [
            "button[aria-label='Next']",
            "button[aria-label*='next']",
            "li.artdeco-pagination__indicator--number:last-child button",
            "button.artdeco-pagination__button--next",
            "button[data-test-pagination-next-btn]"
        ]
        
        for selector in next_selectors:
            try:
                next_btn = page.query_selector(selector)
                if next_btn and next_btn.is_enabled() and next_btn.is_visible():
                    # Check if it's not the current page
                    if next_btn.get_attribute("disabled") is None:
                        print("Clicking next page button...")
                        next_btn.click()
                        time.sleep(2)
                        return True
            except:
                continue
        
        # Alternative: Look for pagination and click the next number
        pagination_items = page.query_selector_all("li.artdeco-pagination__indicator--number button")
        if pagination_items:
            current_active = page.query_selector("li.artdeco-pagination__indicator--number.active button")
            if current_active:
                current_text = current_active.inner_text().strip()
                for item in pagination_items:
                    if item.inner_text().strip() == str(int(current_text) + 1):
                        print(f"Clicking page {int(current_text) + 1}...")
                        item.click()
                        time.sleep(2)
                        return True
        
        print("No next page button found or already on last page")
        return False
        
    except Exception as e:
        print(f"Error navigating to next page: {e}")
        return False