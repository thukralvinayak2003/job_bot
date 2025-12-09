import time
from typing import Optional
from playwright.sync_api import Page
import random

class ModalNavigator:
    """Handles navigation within the LinkedIn Easy Apply modal"""
    
    # Button selectors organized by priority
    BUTTON_SELECTORS = {
        'submit': [
            "button[aria-label='Submit application']",
            "button:has-text('Submit application')",
            "button:has-text('Submit')",
            "footer button[aria-label*='Submit']"
        ],
        'review': [
            "button:has-text('Review')",
            "button[aria-label*='Review']"
        ],
        'next': [
            "button:has-text('Next')",
            "button[aria-label='Continue to next step']",
            "button[aria-label='Next']",
            "footer button.artdeco-button--primary"
        ]
    }
    
    # Success indicators
    SUCCESS_INDICATORS = [
        "application sent",
        "application submitted",
        "your application was sent",
        "successfully submitted",
        "application complete"
    ]
    
    def __init__(self, autofill):
        self.autofill = autofill
    
    def handle_application_modal(self, page: Page, max_steps: int = 10) -> bool:
        """Handle the multi-step Easy Apply modal"""
        for step in range(max_steps):
            print(f"\n--- Step {step + 1} ---")
            
            # Add human-like delay
            time.sleep(random.uniform(1.5, 2.5))
            
            # Scroll to top of modal
            self._scroll_modal_top(page)
            
            # Fill form fields
            print("Filling form fields...")
            self.autofill.autofill_standard_form(page)
            
            time.sleep(random.uniform(1, 2))
            
            # Find and handle action buttons
            button_type, button = self._find_action_button(page)
            
            if not button:
                if self._check_for_errors(page):
                    break
                continue
            
            # Handle the button based on type
            if button_type == 'submit':
                return self._handle_submission(page, button)
            else:
                self._click_button(button, button_type)
                continue
        
        print("⚠ Reached max steps or couldn't complete application")
        return False
    
    def _find_action_button(self, page: Page) -> tuple:
        """Find the appropriate action button in modal"""
        # Check buttons in order of priority: Submit > Review > Next
        for button_type in ['submit', 'review', 'next']:
            button = self._find_button_by_selectors(page, self.BUTTON_SELECTORS[button_type])
            if button:
                return button_type, button
        return None, None
    
    def _find_button_by_selectors(self, page: Page, selectors: list):
        """Find button using multiple selectors"""
        for selector in selectors:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible() and not btn.is_disabled():
                    return btn
            except:
                continue
        return None
    
    def _handle_submission(self, page: Page, submit_button) -> bool:
        """Handle submission of application"""
        print("Found Submit button - submitting application...")
        
        if not self._click_button(submit_button, 'submit'):
            return False
        
        # Wait for confirmation
        time.sleep(random.uniform(3, 5))
        
        # Check for success
        if self._is_application_successful(page):
            print("✓ Application submitted successfully!")
            return True
        
        print("⚠ Submit clicked but couldn't confirm success")
        return False
    
    def _click_button(self, button, button_type: str) -> bool:
        """Click button with retry logic"""
        time.sleep(random.uniform(0.5, 1))
        
        for attempt in range(2):
            try:
                if attempt == 0:
                    button.click(timeout=5000)
                else:
                    button.click(force=True)
                
                print(f"Clicked {button_type} button")
                return True
                
            except Exception as e:
                if attempt == 0:
                    print(f"Click attempt failed: {str(e)[:50]}")
                    continue
                else:
                    print(f"Failed to click {button_type}: {e}")
                    return False
    
    def _is_application_successful(self, page: Page) -> bool:
        """Check if application was successful"""
        page_text = page.content().lower()
        
        # Check for success indicators in page text
        is_success = any(indicator in page_text for indicator in self.SUCCESS_INDICATORS)
        
        # Also check if modal closed
        try:
            modal_still_visible = page.is_visible("div.jobs-easy-apply-modal")
            if not modal_still_visible:
                is_success = True
        except:
            pass
        
        return is_success
    
    def _check_for_errors(self, page: Page) -> bool:
        """Check for error messages in modal"""
        has_errors = False
        
        try:
            # Check for inline error feedback
            errors = page.query_selector_all("div.artdeco-inline-feedback--error")
            if errors:
                for err in errors:
                    if err.is_visible():
                        print(f"Error: {err.inner_text()}")
                        has_errors = True
        except:
            pass
        
        # Check for empty required fields
        try:
            required_fields = page.query_selector_all(
                "input[required], select[required], textarea[required]"
            )
            empty_required = []
            
            for field in required_fields:
                if field.is_visible():
                    val = field.input_value() if hasattr(field, 'input_value') else None
                    if not val:
                        empty_required.append(field)
            
            if empty_required:
                print(f"⚠ {len(empty_required)} required fields still empty")
                has_errors = True
        except:
            pass
        
        return has_errors
    
    def _scroll_modal_top(self, page: Page):
        """Scroll to top of modal"""
        try:
            page.evaluate("""
                const modal = document.querySelector('.jobs-easy-apply-modal, [role="dialog"]');
                if (modal) modal.scrollTop = 0;
            """)
        except:
            pass