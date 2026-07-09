"""
main.py
Orchestrator CLI. Use Playwright to search and attempt quick-applies across sites.
"""

import argparse
from playwright.sync_api import sync_playwright
from config import config
from scrapers import linkedin, indeed, naukri
from apply import LinkedInApply, IndeedApply, NaukriApply, get_new_jobs_only
from database import db
import os
import time
import random

# Site configuration mapping
SITE_CONFIGS = {
    # "LinkedIn": {
    #     "scraper": linkedin.search_jobs,
    #     "applier_class": LinkedInApply,
    #     "login_url": "https://www.linkedin.com/feed/",
    #     "login_check": None,
    # },
    # "Indeed": {
    #     "scraper": indeed.search_jobs,
    #     "applier_class": IndeedApply,
    #     "login_url": "https://www.indeed.com/",
    #     "login_check": None,
    # },
    "Naukri": {
        "scraper": naukri.search_jobs,
        "applier_class": NaukriApply,
        "login_url": "https://www.naukri.com/mnjuser/homepage",
        "login_check": None,
    }
}

def is_linkedin_logged_in(page):
    """Check if user is logged in to LinkedIn"""
    try:
        # Check for common logged-in indicators
        logged_in_indicators = [
            "button:has-text('Start a post')",
            "div.feed-identity-module",
            "a[href*='/mynetwork/']",
            "img.global-nav__me-photo",
            "nav.global-nav"
        ]
        
        for selector in logged_in_indicators:
            if page.query_selector(selector) is not None:
                return True
        
        # Additional check: Look for profile dropdown
        try:
            has_profile_menu = page.evaluate("""
                () => {
                    const menus = Array.from(document.querySelectorAll('div[data-control-name*="identity"]'));
                    const profilePics = Array.from(document.querySelectorAll('img[alt*="Profile"]'));
                    return menus.length > 0 || profilePics.length > 0;
                }
            """)
            return has_profile_menu
        except:
            return False
            
    except:
        return False

def is_indeed_logged_in(page):
    """Check if user is logged in to Indeed"""
    try:
        # Check for common logged-in indicators
        logged_in_indicators = [
            "a[href*='/account']",
            "button:has-text('Account')",
            "span.gnav-AccountMenu-userName",
            "div.gnav-account-menu"
        ]
        
        for selector in logged_in_indicators:
            if page.query_selector(selector) is not None:
                return True
        
        # Check URL for account pages
        current_url = page.url
        if '/account' in current_url or '/myjobs' in current_url:
            return True
        
        # Check for sign-out button (opposite check)
        if page.query_selector("a:has-text('Sign out')") or page.query_selector("button:has-text('Sign out')"):
            return True
            
        return False
    except:
        return False

def is_naukri_logged_in(page):
    """Check if user is logged in to Naukri"""
    try:
        logged_in_indicators = [
            "a:has-text('Logout')",
            "a:has-text('My Naukri')",
            "div.nI-gNb-drawer__bars",
            "img[alt*='profile']",
            "a[href*='mnjuser/profile']",
            "a[href*='mnjuser/homepage']",
        ]

        for selector in logged_in_indicators:
            if page.query_selector(selector) is not None:
                return True

        current_url = page.url.lower()
        if "mnjuser/homepage" in current_url or "mnjuser/profile" in current_url:
            return True

        page_text = page.content().lower()
        return "logout" in page_text or "my naukri" in page_text
    except:
        return False

def check_and_wait_for_login(page, site_name, site_config, headless=False):
    """
    Check if user is logged in. If not, navigate to login page and wait.
    """
    print(f"\n{'='*60}")
    print(f"Checking {site_name} login status")
    print('='*60)
    
    login_url = site_config["login_url"]
    login_check_fn = site_config["login_check"]
    
    try:
        print(f"Navigating to {login_url}...")
        
        # Use simpler navigation for login checks
        try:
            page.goto(login_url, timeout=45000)
        except:
            # If initial navigation fails, try with networkidle
            page.goto(login_url, wait_until="networkidle", timeout=45000)
        
        time.sleep(3)
        
        # Check if already logged in
        if login_check_fn(page):
            print(f"✓ Already logged in to {site_name}")
            return True
        
        print(f"⚠ Not logged in to {site_name}")
        
        if headless:
            print(f"⚠ Running in headless mode. Cannot log in manually.")
            print(f"⚠ Please run with --no-headless flag to log in first, then use --headless for automation.")
            return False
        
        print(f"\n{'='*60}")
        print(f"MANUAL LOGIN REQUIRED")
        print('='*60)
        print(f"Please log in to {site_name} manually in the browser window.")
        print(f"The browser will wait for you to complete the login.")
        print(f"After logging in, the page will automatically refresh.")
        print(f"Timeout: 3 minutes")
        print('='*60)
        
        # Wait up to 3 minutes for manual login
        max_wait_seconds = 180
        check_interval = 3
        attempts = max_wait_seconds // check_interval
        
        for attempt in range(attempts):
            time.sleep(check_interval)
            
            # Try to check login status without refreshing (to avoid triggering Cloudflare)
            try:
                if login_check_fn(page):
                    print(f"\n✓ Successfully logged in to {site_name}!")
                    print(f"Login confirmed, continuing with automation...")
                    return True
            except:
                pass
            
            # Every 30 seconds, give status update
            if attempt % 10 == 0 and attempt > 0:
                print(f"Still waiting for login... ({attempt * check_interval}s / {max_wait_seconds}s)")
        
        print(f"\n✗ Login timeout for {site_name} after {max_wait_seconds} seconds.")
        print(f"Skipping {site_name} for this session.")
        return False
        
    except Exception as e:
        print(f"Error checking login for {site_name}: {e}")
        return False

def setup_browser_context(playwright, user_data_dir, headless=False, use_simple_stealth=True):
    """
    Setup browser with appropriate stealth measures.
    use_simple_stealth=True uses simpler stealth that works better with Cloudflare.
    """
    print("Launching browser...")
    
    # Simpler stealth that works better with Cloudflare
    if use_simple_stealth:
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            # Minimal arguments to appear more human
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ],
            viewport={'width': 1366, 'height': 768},
            # Add human-like user agent
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Remove most anti-detection flags for Cloudflare compatibility
        )
        
        # Add only essential stealth script
        page = browser.new_page()
        page.add_init_script("""
            // Minimal stealth - just remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
        """)
        
    else:
        # Use the original complex stealth
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-features=BlockInsecurePrivateNetworkRequests',
            ],
            ignore_default_args=[
                '--enable-automation',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-first-run',
                '--safebrowsing-disable-auto-update',
                '--disable-component-update',
                '--disable-client-side-phishing-detection',
            ],
            viewport={'width': 1366, 'height': 768},
            user_agent=config.USER_AGENT if hasattr(config, 'USER_AGENT') else None,
        )
        
        page = browser.new_page()
        page.add_init_script("""
            // Override navigator properties
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Chrome only
            window.chrome = {
                runtime: {},
            };
        """)
    
    return browser, page

def handle_cloudflare_interactive(page, site_name):
    """
    Handle Cloudflare verification interactively.
    Returns True if verification passed, False if failed.
    """
    print(f"\n{'='*60}")
    print(f"⚠️  CLOUDFLARE VERIFICATION DETECTED ON {site_name.upper()}")
    print('='*60)
    print("\nCloudflare is blocking access. Please manually complete the verification:")
    print("1. Look at the browser window")
    print("2. Complete any CAPTCHA or verification challenges")
    print("3. Wait for the page to load normally")
    print("4. The script will continue automatically")
    print("\nYou have 2 minutes to complete this.")
    print("="*60)
    
    start_time = time.time()
    timeout = 120  # 2 minutes
    
    while time.time() - start_time < timeout:
        # Check if Cloudflare is still present
        try:
            page_content = page.content().lower()
            cloudflare_indicators = ['cloudflare', 'just a moment', 'checking your browser', 'verify you are human']
            
            # Check if Cloudflare is gone
            if not any(indicator in page_content for indicator in cloudflare_indicators):
                print("✓ Cloudflare verification appears to be completed!")
                time.sleep(2)
                return True
            
            # Wait and check again
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            
            if elapsed % 15 == 0:
                print(f"⏳ Still waiting... ({elapsed}s elapsed)")
                
        except Exception as e:
            print(f"Error checking Cloudflare status: {e}")
            time.sleep(5)
    
    print("✗ Cloudflare verification timed out after 2 minutes.")
    return False

def run_job_search_and_apply(max_per_site=5, headless=None, use_simple_stealth=True):
    """
    Main routine with improved Cloudflare handling.
    """
    headless = config.HEADLESS if headless is None else headless
    
    if headless:
        print("\n⚠  WARNING: Running in headless mode.")
        print("⚠  Cloudflare may be more aggressive in headless mode.")
        print("⚠  Consider using --no-headless for first run or problematic sites.\n")
    
    # Create user data directory if it doesn't exist
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    
    # Initialize site configs
    # SITE_CONFIGS["LinkedIn"]["login_check"] = is_linkedin_logged_in
    # SITE_CONFIGS["Indeed"]["login_check"] = is_indeed_logged_in
    SITE_CONFIGS["Naukri"]["login_check"] = is_naukri_logged_in
    
    with sync_playwright() as p:
        # Setup browser - use simpler stealth for better Cloudflare compatibility
        browser, page = setup_browser_context(p, config.USER_DATA_DIR, headless, use_simple_stealth)
        
        logged_in_sites = {}
        site_appliers = {}
        
        # Initialize appliers for each site
        for site_name, site_config in SITE_CONFIGS.items():
            if site_config["applier_class"]:
                try:
                    applier = site_config["applier_class"](config)
                    site_appliers[site_name] = applier
                    print(f"✓ Initialized {site_name} applier")
                except Exception as e:
                    print(f"✗ Failed to initialize {site_name} applier: {e}")
                    site_appliers[site_name] = None
        
        # Process each site
        for site_name, site_config in SITE_CONFIGS.items():
            print(f"\n{'='*60}")
            print(f"PROCESSING: {site_name}")
            print('='*60)
            
            # Check login status
            logged_in = check_and_wait_for_login(page, site_name, site_config, headless)
            logged_in_sites[site_name] = logged_in
            
            if not logged_in:
                print(f"Skipping {site_name} due to login failure\n")
                continue
            
            # Perform job search with Cloudflare handling
            print(f"\nSearching for jobs on {site_name}...")
            try:
                # Try to search jobs
                jobs = site_config["scraper"](
                    page, 
                    config.JOB_KEYWORDS or "software engineer", 
                    config.LOCATION or "India", 
                    max_results=max_per_site
                )
                print(f"✓ Found {len(jobs)} jobs on {site_name}")
                
            except Exception as e:
                print(f"✗ Error searching {site_name}: {e}")
                
                # Check if it's a Cloudflare error
                error_str = str(e).lower()
                if any(cf_term in error_str for cf_term in ['cloudflare', 'captcha', 'just a moment']):
                    print(f"\n⚠️  Possible Cloudflare block detected!")
                    
                    # Try interactive Cloudflare bypass
                    if not headless:
                        print("Attempting interactive Cloudflare bypass...")
                        if handle_cloudflare_interactive(page, site_name):
                            # Retry the search after Cloudflare bypass
                            try:
                                jobs = site_config["scraper"](
                                    page, 
                                    config.JOB_KEYWORDS or "software engineer", 
                                    config.LOCATION or "India", 
                                    max_results=max_per_site
                                )
                                print(f"✓ Found {len(jobs)} jobs on {site_name} after Cloudflare bypass")
                            except Exception as retry_error:
                                print(f"✗ Still blocked after Cloudflare bypass: {retry_error}")
                                jobs = []
                        else:
                            jobs = []
                    else:
                        print("⚠️  Cannot do interactive Cloudflare bypass in headless mode.")
                        jobs = []
                else:
                    jobs = []
            
            if not jobs:
                print(f"No jobs found on {site_name}, moving to next site...")
                continue
            
            # Filter out already applied jobs
            new_jobs = get_new_jobs_only(jobs)
            print(f"Filtered to {len(new_jobs)} new jobs (skipped {len(jobs) - len(new_jobs)} already applied)")
            
            if not new_jobs:
                print(f"No new jobs to apply on {site_name}, moving to next site...")
                continue
            
            # Apply to each job
            print(f"\nStarting application process for {len(new_jobs)} jobs...")
            
            for idx, job in enumerate(new_jobs, 1):
                print(f"\n{'='*50}")
                print(f"Job {idx}/{len(new_jobs)}: {job.get('role', 'N/A')} @ {job.get('company', 'N/A')}")
                print('='*50)
                
                link = job.get("link")
                if not link:
                    print("Skipping: No link provided")
                    continue
                
                # Get the applier for this site
                applier = site_appliers.get(site_name)
                
                if applier is None:
                    print(f"Auto-apply not implemented for {site_name}, marking as skipped.")
                    db.add_job(
                        link, 
                        job.get("company", "Unknown"), 
                        job.get("role", "Unknown"), 
                        status="skipped"
                    )
                    continue
                
                try:
                    # Attempt to apply
                    print(f"Attempting to apply...")
                    success = applier.attempt_apply(page, job)
                    
                    if success:
                        print(f"✓ Successfully applied!")
                    else:
                        print(f"✗ Failed to apply or application skipped")
                        db.add_job(
                            link, 
                            job.get("company", "Unknown"), 
                            job.get("role", "Unknown"), 
                            status="skipped"
                        )
                        
                except Exception as e:
                    print(f"✗ Error during application: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    db.add_job(
                        link, 
                        job.get("company", "Unknown"), 
                        job.get("role", "Unknown"), 
                        status="error",
                        notes=str(e)[:100]
                    )
                
                # Add delay between applications (human-like behavior)
                if idx < len(new_jobs):
                    delay = random.uniform(8, 15)  # Longer delays to avoid detection
                    print(f"\nWaiting {delay:.1f} seconds before next application...")
                    time.sleep(delay)
        
        # Close browser
        print("\nClosing browser...")
        browser.close()
        
        # Print session summary
        print_summary(logged_in_sites)

def print_summary(logged_in_sites):
    """Print session summary"""
    print("\n" + "="*60)
    print("SESSION SUMMARY")
    print("="*60)
    
    # Login status
    print("\nLogin Status:")
    for site, status in logged_in_sites.items():
        status_str = "✓ Logged in" if status else "✗ Not logged in"
        print(f"  {site}: {status_str}")
    
    # Database stats
    print("\nApplication Statistics:")
    try:
        stats = db.get_application_stats()
        if stats:
            for status, count in stats.items():
                print(f"  {status}: {count}")
        else:
            print("  No applications recorded yet.")
    except:
        print("  Could not retrieve statistics.")
    
    print("="*60)

def show_stats():
    """Show application statistics"""
    print("\n" + "="*60)
    print("APPLICATION STATISTICS")
    print("="*60)
    
    try:
        # Get stats from database
        stats = db.get_application_stats()
        if stats:
            total = sum(stats.values())
            print(f"\nTotal Applications Recorded: {total}")
            print("\nBreakdown by Status:")
            
            for status, count in sorted(stats.items()):
                percentage = (count / total * 100) if total > 0 else 0
                print(f"  {status}: {count} ({percentage:.1f}%)")
            
            # Show recent applications
            print("\nRecent Applications (last 10):")
            recent = db.get_recent_applications(10)
            for app in recent:
                date_str = app.get('applied_date', 'N/A')
                print(f"  • {date_str}: {app.get('role', 'N/A')} @ {app.get('company', 'N/A')} - {app.get('status', 'N/A')}")
        else:
            print("No applications recorded yet.")
            
    except Exception as e:
        print(f"Error retrieving statistics: {e}")
    
    print("="*60)

def clear_database():
    """Clear all application records (with confirmation)"""
    print("\n" + "="*60)
    print("CLEAR DATABASE")
    print("="*60)
    print("\n⚠ WARNING: This will delete ALL application records!")
    print("This action cannot be undone.\n")
    
    confirmation = input("Type 'DELETE' to confirm: ")
    if confirmation == "DELETE":
        try:
            count = db.clear_all_applications()
            print(f"\n✓ Deleted {count} application records.")
        except Exception as e:
            print(f"\n✗ Error clearing database: {e}")
    else:
        print("\n✗ Operation cancelled.")

def test_cloudflare():
    """Test Cloudflare bypass with Indeed"""
    print("\n" + "="*60)
    print("TESTING CLOUDFLARE BYPASS")
    print("="*60)
    
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        # Use simple stealth for testing
        browser, page = setup_browser_context(p, config.USER_DATA_DIR, headless=False, use_simple_stealth=True)
        
        try:
            print("Navigating to Indeed...")
            page.goto("https://www.indeed.com", timeout=45000)
            time.sleep(3)
            
            # Check for Cloudflare
            page_content = page.content().lower()
            if any(indicator in page_content for indicator in ['cloudflare', 'just a moment', 'checking your browser']):
                print("⚠️  Cloudflare detected!")
                print("\nTesting interactive bypass...")
                
                if handle_cloudflare_interactive(page, "Indeed"):
                    print("\n✅ Cloudflare bypass successful!")
                    
                    # Now test job search
                    print("\nTesting job search...")
                    jobs = indeed.search_jobs(page, "software engineer", "India", max_results=3)
                    print(f"Found {len(jobs)} jobs after Cloudflare bypass")
                else:
                    print("\n❌ Cloudflare bypass failed.")
            else:
                print("✅ No Cloudflare detected on Indeed homepage.")
                
        except Exception as e:
            print(f"Error during test: {e}")
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(
        description="Multi-site Job Auto-Application Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s apply --max 10 --no-headless   # Apply to up to 10 jobs per site with browser visible
  %(prog)s apply --headless               # Run in background (headless mode)
  %(prog)s stats                          # Show application statistics
  %(prog)s clear                          # Clear all application records
  %(prog)s test-cf                        # Test Cloudflare bypass
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Search and apply to jobs")
    apply_parser.add_argument("--max", type=int, default=5, 
                             help="Maximum jobs to process per site (default: 5)")
    apply_parser.add_argument("--headless", action="store_true", 
                             help="Run browser in headless mode (no visible window)")
    apply_parser.add_argument("--no-headless", action="store_true", 
                             help="Run browser with visible window")
    apply_parser.add_argument("--complex-stealth", action="store_true",
                             help="Use complex stealth measures (may trigger Cloudflare more)")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show application statistics")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all application records")
    
    # Test Cloudflare command
    test_cf_parser = subparsers.add_parser("test-cf", help="Test Cloudflare bypass")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "apply":
        # Determine headless mode
        if args.headless and args.no_headless:
            print("Error: Cannot specify both --headless and --no-headless")
            return
        
        headless_mode = None
        if args.headless:
            headless_mode = True
        elif args.no_headless:
            headless_mode = False
        else:
            # Use config default
            headless_mode = None
        
        print("\n" + "="*60)
        print("JOB AUTO-APPLICATION BOT")
        print("="*60)
        print(f"Config: {args.max} jobs per site | Headless: {headless_mode if headless_mode is not None else 'config default'}")
        print(f"Stealth: {'Complex' if args.complex_stealth else 'Simple (recommended for Cloudflare)'}")
        print("="*60 + "\n")
        
        run_job_search_and_apply(
            max_per_site=args.max, 
            headless=headless_mode,
            use_simple_stealth=not args.complex_stealth
        )
        
    elif args.command == "stats":
        show_stats()
        
    elif args.command == "clear":
        clear_database()
        
    elif args.command == "test-cf":
        test_cloudflare()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
