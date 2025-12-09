from playwright.sync_api import Page
from typing import Dict
import time
import random as random
from .utils.human_behavior import human_like_delay, scroll_slowly, scroll_element_into_view
from .utils.job_filtering import get_new_jobs_only, is_job_already_applied
from .autofill.base_autofill import BaseAutofill
from .navigation.modal_navigation import ModalNavigator
from database import db

class LinkedInApply:
    """Main LinkedIn application orchestrator"""
    
    EASY_APPLY_SELECTORS = [
        "button:has-text('Easy Apply')",
        "button.jobs-apply-button",
        "button[aria-label*='Easy Apply']",
        "button.jobs-apply-button--top-card",
        "button:has-text('Apply')",
        "div.jobs-apply-button--top-card button"
    ]
    
    MODAL_SELECTORS = [
        "div.jobs-easy-apply-modal",
        "div[role='dialog']",
        "div.artdeco-modal",
        "div[data-test='modal']"
    ]
    
    def __init__(self, config):
        self.config = config
        self.autofill = BaseAutofill(config)
        self.modal_navigator = ModalNavigator(self.autofill)
    
    def attempt_apply(self, page: Page, job: Dict) -> bool:
        """Try to apply to a LinkedIn job with multi-step form support"""
        link = job.get("link")
        if not link:
            return False
        
        # Double-check if job is already applied
        if is_job_already_applied(link):
            print(f"⏭️  Job already applied: {link}")
            return False
        
        try:
            return self._process_job_application(page, job)
            
        except Exception as e:
            print(f"Error in LinkedIn apply: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _process_job_application(self, page: Page, job: Dict) -> bool:
        """Process job application step by step"""
        link = job.get("link")
        
        print(f"Navigating to job page...")
        
        # Navigate to job page
        if not self._navigate_to_job_page(page, link):
            return False
        
        # Human-like behavior
        human_like_delay(2, 4)
        scroll_slowly(page)
        time.sleep(2)
        
        # Find and click Easy Apply button
        easy_apply_button = self._find_easy_apply_button(page)
        
        if not easy_apply_button:
            return self._handle_no_easy_apply(page, job)
        
        # Click the button
        if not self._click_easy_apply_button(easy_apply_button):
            return False
        
        # Wait for modal
        human_like_delay(2, 4)
        modal = self._wait_for_modal(page)
        
        if not modal:
            return self._handle_no_modal(page, job)
        
        print("Easy Apply modal detected, filling form...")
        
        # Handle the multi-step modal
        return self.modal_navigator.handle_application_modal(page)
    
    def _navigate_to_job_page(self, page: Page, link: str, max_attempts: int = 3) -> bool:
        """Navigate to job page with retry logic"""
        wait_strategies = ["domcontentloaded", "networkidle", "commit"]
        
        for attempt in range(max_attempts):
            try:
                page.goto(link, timeout=45000, wait_until=wait_strategies[attempt])
                return True
            except Exception as e:
                print(f"Navigation attempt {attempt + 1} failed: {str(e)[:50]}")
                if attempt < max_attempts - 1:
                    time.sleep(3)
                    continue
        
        print("All navigation attempts failed")
        return False
    
    def _find_easy_apply_button(self, page: Page):
        """Find Easy Apply button with multiple strategies"""
        # Strategy 1: Wait for specific selector
        try:
            ea = page.wait_for_selector(
                "button:has-text('Easy Apply')",
                timeout=10000,
                state="visible"
            )
            if ea and ea.is_visible():
                return ea
        except:
            pass
        
        # Strategy 2: Try alternative selectors
        for selector in self.EASY_APPLY_SELECTORS:
            try:
                button = page.query_selector(selector)
                if button and button.is_visible():
                    # Verify it's not "Applied" button
                    text = button.inner_text().lower()
                    if ("easy" in text or "apply" in text) and "applied" not in text:
                        return button
            except:
                continue
        
        return None
    
    def _click_easy_apply_button(self, button) -> bool:
        """Click Easy Apply button with retry"""
        human_like_delay(0.5, 1.5)
        
        # Scroll button into view
        scroll_element_into_view(button)
        
        # Click with retry
        for click_attempt in range(3):
            try:
                if click_attempt == 0:
                    button.click(timeout=5000)
                else:
                    button.click(force=True)
                
                print("Clicked Easy Apply button")
                return True
                
            except Exception as e:
                print(f"Click attempt {click_attempt + 1} failed: {str(e)[:50]}")
                if click_attempt < 2:
                    time.sleep(1)
                    continue
        
        print("Failed to click Easy Apply button")
        return False
    
    def _wait_for_modal(self, page: Page):
        """Wait for Easy Apply modal to appear"""
        for selector in self.MODAL_SELECTORS:
            try:
                modal = page.wait_for_selector(
                    selector,
                    timeout=10000,
                    state="visible"
                )
                if modal:
                    print(f"Modal appeared: {selector}")
                    return modal
            except:
                continue
        
        return None
    
    def _handle_no_easy_apply(self, page: Page, job: Dict) -> bool:
        """Handle case when no Easy Apply button is found"""
        print("No Easy Apply button found")
        
        # Check if already applied
        page_text = page.content().lower()
        if "applied" in page_text or "already applied" in page_text:
            print("Already applied to this job")
            db.add_job(
                job.get("link"),
                job.get("company"),
                job.get("role"),
                status="already_applied"
            )
            return True
        
        # Take screenshot for debugging
        try:
            page.screenshot(path=f"debug_no_button_{int(time.time())}.png")
        except:
            pass
        
        return False
    
    def _handle_no_modal(self, page: Page, job: Dict) -> bool:
        """Handle case when modal doesn't appear"""
        print("Easy Apply modal did not appear")
        
        # Check if already applied
        page_text = page.content().lower()
        if "application sent" in page_text or "already applied" in page_text:
            print("Already applied to this job")
            db.add_job(
                job.get("link"),
                job.get("company"),
                job.get("role"),
                status="already_applied"
            )
            return True
        
        return False