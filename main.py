"""
main.py
Orchestrator CLI. Use Playwright to search and attempt quick-applies across sites.
"""

import argparse
from playwright.sync_api import sync_playwright
from config import config
from scrapers import linkedin, indeed
from apply.apply_linkedin import attempt_apply as apply_linkedin
from apply.apply_indeed import attempt_apply as apply_indeed
from database import db
import os
from tqdm import tqdm
import time

# Simple mapping of scrapers and apply handlers
SCRAPERS = [
    ("LinkedIn", linkedin.search_jobs, apply_linkedin),
    ("Indeed", indeed.search_jobs, apply_indeed),
]

def check_and_wait_for_login(page, site_name, login_url, logged_in_check):
    """
    Check if user is logged in. If not, navigate to login page and wait.
    
    Args:
        page: Playwright page object
        site_name: Name of the site (for display)
        login_url: URL to navigate for login
        logged_in_check: Function that returns True if user is logged in
    """
    print(f"\n=== Checking {site_name} login status ===")
    
    try:
        page.goto(login_url, timeout=30000)
        time.sleep(3)
        
        if logged_in_check(page):
            print(f"✓ Already logged in to {site_name}")
            return True
        
        print(f"⚠ Not logged in to {site_name}")
        print(f"Please log in manually in the browser window...")
        print(f"Waiting for you to complete login (checking every 5 seconds)...")
        
        # Wait up to 5 minutes for login
        max_wait = 60  # 60 * 5 seconds = 5 minutes
        for i in range(max_wait):
            time.sleep(5)
            if logged_in_check(page):
                print(f"✓ Successfully logged in to {site_name}!")
                return True
            if i % 6 == 0:  # Every 30 seconds
                print(f"Still waiting... ({i*5}s elapsed)")
        
        print(f"✗ Login timeout for {site_name}. Skipping this site.")
        return False
        
    except Exception as e:
        print(f"Error checking login for {site_name}: {e}")
        return False

def is_linkedin_logged_in(page):
    """Check if user is logged in to LinkedIn"""
    try:
        # Check for common logged-in indicators
        return (
            page.query_selector("button:has-text('Start a post')") is not None or
            page.query_selector("div.feed-identity-module") is not None or
            page.query_selector("a[href*='/mynetwork/']") is not None or
            page.query_selector("img.global-nav__me-photo") is not None
        )
    except:
        return False

def is_indeed_logged_in(page):
    """Check if user is logged in to Indeed"""
    try:
        # Check for common logged-in indicators
        return (
            page.query_selector("a[href*='/account']") is not None or
            page.query_selector("button:has-text('Account')") is not None or
            page.query_selector("span.gnav-AccountMenu-userName") is not None
        )
    except:
        return False

def run_apply(max_per_site=5, headless=None):
    """
    Main routine:
    - Launch Playwright (persistent context per config.USER_DATA_DIR)
    - For each site: check login, search, then for each job check DB and attempt quick-apply
    """
    headless = config.HEADLESS if headless is None else headless
    
    if headless:
        print("WARNING: Running in headless mode. You won't be able to log in manually.")
        print("Consider using --no-headless flag for first run.")
    
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config.USER_DATA_DIR,
            headless=headless,
            # Make browser appear more "real" to avoid detection
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ],
            ignore_default_args=['--enable-automation'],
            # NOTE: set slow_mo for debugging, e.g. slow_mo=50
        )
        
        # Additional stealth measures
        page = browser.new_page()
        
        # Hide webdriver property
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # Login checks for each site
        login_checks = {
            "LinkedIn": ("https://www.linkedin.com/feed/", is_linkedin_logged_in),
            "Indeed": ("https://www.indeed.com/", is_indeed_logged_in),
        }
        
        logged_in_sites = {}
        
        for name, scraper_fn, apply_fn in SCRAPERS:
            # Check login if we have a check function for this site
            if name in login_checks:
                login_url, check_fn = login_checks[name]
                logged_in = check_and_wait_for_login(page, name, login_url, check_fn)
                logged_in_sites[name] = logged_in
                
                if not logged_in:
                    print(f"Skipping {name} due to login failure\n")
                    continue
            
            print(f"\n=== Searching {name} ===")
            try:
                jobs = scraper_fn(page, config.JOB_KEYWORDS or "software engineer", "India", max_results=max_per_site)
            except Exception as e:
                print(f"Error searching {name}: {e}")
                jobs = []

            print(f"Found {len(jobs)} jobs on {name}")
            
            for job in jobs:
                link = job.get("link")
                if not link:
                    continue
                if db.has_job(link):
                    print(f"Skipping (already applied): {job.get('role')} @ {job.get('company')}")
                    continue
                    
                print(f"Processing: {job.get('role')} @ {job.get('company')} — {link}")
                
                if apply_fn is None:
                    print(f"Auto-apply not implemented for {name}, skipping. (open link manually)")
                    # store skipped
                    db.add_job(link, job.get("company"), job.get("role"), status="skipped")
                    continue
                    
                try:
                    applied = apply_fn(page, job)
                    if applied:
                        print("-> Applied and recorded.")
                    else:
                        print("-> Skipped or couldn't auto-apply.")
                        db.add_job(link, job.get("company"), job.get("role"), status="skipped")
                except Exception as e:
                    print(f"Error applying: {e}")
                    db.add_job(link, job.get("company"), job.get("role"), status="error")
                    
                # small delay to avoid rapid-fire
                time.sleep(2)
                
        browser.close()
        
        # Print summary
        print("\n" + "="*50)
        print("SESSION SUMMARY")
        print("="*50)
        for site, status in logged_in_sites.items():
            status_str = "✓ Logged in" if status else "✗ Not logged in"
            print(f"{site}: {status_str}")

def show_stats():
    print("Jobs applied (total rows):")
    # naive count
    import sqlite3
    conn = sqlite3.connect("jobs.db")
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM applied_jobs GROUP BY status")
    rows = cur.fetchall()
    for status, count in rows:
        print(f"  {status}: {count}")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="multi-autoapply-lite CLI")
    sub = parser.add_subparsers(dest="cmd")
    sub_apply = sub.add_parser("apply", help="search & attempt auto-apply")
    sub_apply.add_argument("--max", type=int, default=5, help="max jobs per site")
    sub_apply.add_argument("--no-headless", action="store_true", help="run with browser visible")
    sub_stats = sub.add_parser("stats", help="show application stats")

    args = parser.parse_args()
    if args.cmd == "apply":
        run_apply(max_per_site=args.max, headless=not args.no_headless)
    elif args.cmd == "stats":
        show_stats()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()