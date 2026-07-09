from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from typing import Dict
import time
import random

from .utils.human_behavior import human_like_delay
from .utils.job_filtering import is_job_already_applied
from .autofill.indeed_autofill import IndeedAutofill
from .navigation.indeed_navigation import IndeedNavigator
from database import db

class IndeedApply:
    """Main Indeed application orchestrator"""
    
    def __init__(self, config):
        self.config = config
        self.autofill = IndeedAutofill(config)
        self.navigator = IndeedNavigator(self.autofill)
    
    def attempt_apply(self, page: Page, job: Dict) -> bool:
        """Main entry point for Indeed application"""
        link = job.get("link")
        if not link:
            print("❌ No job link provided")
            return False
        
        print(f"\n{'='*70}")
        print(f"🎯 Applying to: {job.get('role')}")
        print(f"🏢 Company: {job.get('company')}")
        print(f"🔗 Link: {link}")
        print(f"{'='*70}")
        
        try:
            # Check if already applied
            if is_job_already_applied(link):
                print(f"⏭️ Job already applied: {link}")
                return False
            
            # Navigate to job page
            if not self._navigate_to_job_page(page, link):
                return False
            
            # Check login status
            if not self.navigator.is_logged_in(page):
                print("❌ Not logged in to Indeed")
                return False
            
            # Look for apply button
            apply_button = self.navigator.find_button(page, 'apply')
            
            if not apply_button:
                print("⚠ No apply button found (may be external application)")
                return False
            
            # Click apply button
            if not self._click_apply_button(page, apply_button):
                return False
            
            # Check for external redirect
            if self.navigator.is_external_application(page):
                print("⚠ Redirected to external site, cannot auto-apply")
                return False
            
            # Start the application flow
            print("\n🚀 Starting application process...")
            success = self._handle_application_flow(page)
            
            if success:
                print("\n" + "="*70)
                print("✅ APPLICATION COMPLETED SUCCESSFULLY!")
                print("="*70)
                
                # Record in database
                db.add_job(
                    link, 
                    job.get("company", "Unknown"), 
                    job.get("role", "Unknown"), 
                    status="applied"
                )
                return True
            else:
                print("\n" + "="*70)
                print("❌ APPLICATION FAILED")
                print("="*70)
                return False
            
        except PlaywrightTimeout as e:
            print(f"⏱ Timeout error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error during application: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _navigate_to_job_page(self, page: Page, link: str) -> bool:
        """Navigate to job page with retry"""
        try:
            print("📄 Loading job page...")
            page.goto(link, wait_until="domcontentloaded", timeout=30000)
            human_like_delay(3, 5)
            return True
        except Exception as e:
            print(f"❌ Failed to load job page: {e}")
            return False
    
    def _click_apply_button(self, page: Page, apply_button) -> bool:
        """Click apply button with proper handling"""
        try:
            print("✓ Found apply button, clicking...")
            apply_button.scroll_into_view_if_needed()
            human_like_delay(1, 2)
            apply_button.click()
            human_like_delay(4, 6)
            return True
        except Exception as e:
            print(f"❌ Failed to click apply button: {e}")
            return False
        
    def _wait_for_captcha_solution_timeout(self, page: Page) -> bool:
        """
        Wait for the user to manually solve CAPTCHA or finish the step.
        Instead of a time limit, the user presses ENTER to continue.
        """
        try:
            print("⏳ Waiting for you to finish solving CAPTCHA or completing the step...")
            print("➡ Press ENTER in this terminal when you are done.")

            input()
            
            return True

        except Exception as e:
            print(f"⚠ Error while waiting: {e}")
            return False
    
    def _handle_application_flow(self, page: Page) -> bool:
        """Main application flow handler with robust error recovery"""
        max_pages = 10
        current_page_num = 0
        last_url = ""
        stuck_count = 0
        
        print("\n" + "="*60)
        print("Starting Indeed Application Flow")
        print("="*60)
        
        while current_page_num < max_pages:
            current_page_num += 1
            current_url = page.url
            
            print(f"\n📄 Page {current_page_num}/{max_pages}")
            print(f"URL: {current_url}")
            
            # Check if we're stuck on the same URL
            if current_url == last_url:
                stuck_count += 1
                if stuck_count >= 3:
                    print("⚠ Stuck on same page for 3 iterations, trying force continue...")
                    button = self.navigator.find_button(page, 'continue')
                    if button and self.navigator.click_button_with_retry(page, button):
                        stuck_count = 0
                        human_like_delay(3, 5)
                        continue
                    else:
                        print("❌ Cannot proceed, application failed")
                        return False
            else:
                stuck_count = 0
                last_url = current_url
            
            # Check application status
            status = self.navigator.check_application_status(page)
            if status == 'success':
                print("✅ APPLICATION SUCCESSFUL!")
                return True
            elif status == 'error':
                print("❌ Error detected on page")
                # Try to continue anyway
            
            # Detect page type
            page_type = self.navigator.detect_page_type(page)
            print(f"Page type: {page_type}")
            
            # Fill forms if needed
            if page_type in ['contact', 'questions', 'unknown']:
                filled = self.navigator.fill_indeed_form_intelligent(page)
                if filled > 0:
                    print(f"✓ Filled {filled} fields")
                    human_like_delay(1, 2)
            
            # Find and click continue button
            button = self.navigator.find_button(page, 'continue')
            if not button:
                # Try submit button as fallback
                if self.navigator.is_captcha_present(page):
                    print("\n🛑 CAPTCHA DETECTED - Requiring manual solution")
                    print("="*50)
                    print("Please solve the CAPTCHA manually in the browser window.")
                    print("The script will wait for you to complete it...")
                    print("="*50)

                    success = self._wait_for_captcha_solution_timeout(page)

                    if not success:
                        print("❌ CAPTCHA was not solved in time, or failed.")
                        return False
                    else:
                        print("✅ CAPTCHA solved successfully. Resuming automation...")
                        # Wait a moment after solving before proceeding
                        human_like_delay(2, 3)
                page.wait_for_timeout(10000)
                button = self.navigator.find_button(page, 'Review your application')
                button = self.navigator.find_button(page, 'submit')
            
            if not button:
                print("❌ No continue/submit button found")
                
                # Try to take a screenshot for debugging
                try:
                    page.screenshot(path=f"indeed_stuck_page_{current_page_num}.png")
                    print(f"📸 Screenshot saved: indeed_stuck_page_{current_page_num}.png")
                except:
                    pass
                
                return False
            
            # Click the button
            if not self.navigator.click_button_with_retry(page, button):
                print("❌ Failed to click continue button")
                return False
            
            # Wait for navigation/changes
            human_like_delay(3, 5)
            
            # Check again for success after clicking
            status = self.navigator.check_application_status(page)
            if status == 'success':
                print("✅ APPLICATION SUCCESSFUL!")
                return True
        
        print("⚠ Reached maximum page limit without completion")
        return False