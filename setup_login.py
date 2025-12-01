"""
setup_login.py
One-time setup script to manually log in to job sites and save sessions.
Run this before using the main automation script.
"""

from playwright.sync_api import sync_playwright
from config import config
import os
import time

def setup_logins():
    """
    Opens browser for manual login to all job sites.
    Sessions will be saved in USER_DATA_DIR for future use.
    """
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    
    print("="*60)
    print("LOGIN SETUP WIZARD")
    print("="*60)
    print("\nThis will open a browser where you can manually log in to:")
    print("  1. LinkedIn")
    print("  2. Indeed")
    print("  3. Naukri")
    print("  4. Glassdoor")
    print("\nYour login sessions will be saved for future automation runs.")
    print("\nIMPORTANT: Use EMAIL/PASSWORD login, NOT 'Sign in with Google'")
    print("="*60)
    
    input("\nPress ENTER to continue...")
    
    sites = [
        ("LinkedIn", "https://www.linkedin.com/login"),
        ("Indeed", "https://secure.indeed.com/auth"),
        ("Naukri", "https://www.naukri.com/nlogin/login"),
        ("Glassdoor", "https://www.glassdoor.co.in/profile/login_input.htm"),
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config.USER_DATA_DIR,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ],
            ignore_default_args=['--enable-automation'],
        )
        
        page = browser.new_page()
        
        # Hide webdriver property
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        for site_name, login_url in sites:
            print(f"\n{'='*60}")
            print(f"LOGGING IN TO: {site_name}")
            print(f"{'='*60}")
            print(f"Opening: {login_url}")
            print("\nPlease:")
            print("  1. Log in using your EMAIL and PASSWORD")
            print("  2. Complete any 2FA/verification if needed")
            print("  3. Make sure you're fully logged in (see your profile)")
            print(f"\nPress ENTER here after you've logged in to {site_name}...")
            
            try:
                page.goto(login_url, timeout=30000)
                time.sleep(2)
                
                # Wait for user to confirm login
                input()
                
                print(f"✓ Session saved for {site_name}")
                
            except Exception as e:
                print(f"✗ Error with {site_name}: {e}")
                continue
        
        browser.close()
    
    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print("\nYour login sessions have been saved.")
    print("You can now run: python main.py apply --max 5 --no-headless")
    print("\nNote: Sessions may expire after some time. Re-run this script if needed.")

if __name__ == "__main__":
    setup_logins()