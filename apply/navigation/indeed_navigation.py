import time
import random
from typing import Optional
from playwright.sync_api import Page

class IndeedNavigator:
    """Indeed-specific navigation and flow control"""
    
    # Button selectors for Indeed
    BUTTON_SELECTORS = {
        'continue': [
            "button[data-testid='continue-button']",
            "button[data-testid='submit-button']",
            "button.ia-continueButton",
            "button.ia-ContinuationButton",
            "button:has-text('Continue')",
            "button:has-text('Continue to next step')",
            "button:has-text('Review your application')",
            "button:has-text('Next')",
        ],
        
        'submit': [
            "button:has-text('Submit')",
            "button:has-text('Submit your application')",
            "button[data-testid='submit-application-button']",  # ADD THIS LINE
            "button[name='submit-application']",  
            "button[type='submit']",
        ],
        'apply': [
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "button.ia-continueButton",
            "button[data-indeed-apply-button-label]",
            ".indeed-apply-button",
            "a:has-text('Apply now')",
        ]
    }
    
    # Success indicators
    SUCCESS_INDICATORS = [
        "text=Application submitted",
        "text=Successfully applied",
        "text=Your application has been sent",
        "text=Application complete",
        "div.ia-SuccessMessage",
        "h1:has-text('Application submitted')",
        "[data-testid='success-message']",
    ]
    
    # Error indicators
    ERROR_INDICATORS = [
        "div.icl-Alert--error",
        "div.error-message",
        "span.error",
        "[role='alert'][aria-live='assertive']",
        "div[class*='error']",
    ]

    def __init__(self, autofill):
        self.autofill = autofill

    def is_captcha_present(self, page: Page) -> bool:
        """
        Detect Google reCAPTCHA (v2, v3, invisible, image puzzle),
        Cloudflare Turnstile, and Cloudflare challenge pages.
        Inspects main page and all frames.
        """
        try:
            # 1. Check title & URL for captcha indicators
            try:
                title = page.title().lower()
                if any(t in title for t in ["just a moment", "security check", "robot", "captcha"]):
                    return True
            except Exception:
                pass

            # 2. Check main page HTML content for static captcha / cloudflare page
            try:
                content_sample = page.content()[:10000].lower()
                if "indeed_cloudflare_static_page" in content_sample or "additional verification required" in content_sample:
                    return True
            except Exception:
                pass

            # 3. Target selectors for reCAPTCHA (v2/v3/checkbox/puzzle) and Turnstile
            selectors = [
                "#recaptcha-anchor",
                ".recaptcha-checkbox",
                ".rc-anchor-checkbox-holder",
                ".rc-anchor-center-item",
                ".recaptcha-checkbox-border",
                ".recaptcha-checkbox-checkmark",
                ".rc-imageselect",
                "#rc-imageselect",
                ".rc-audiochallenge-tdownload",
                "iframe[src*='recaptcha']",
                "iframe[src*='google.com/recaptcha']",
                "iframe[title*='recaptcha' i]",
                "iframe[title*='reCAPTCHA' i]",
                "input[name='cf-turnstile-response']",
                "iframe[src*='challenges.cloudflare.com']",
                ".cf-turnstile-wrapper",
                "#challenge-stage",
                "#challenge-running",
            ]

            # Check main page
            for selector in selectors:
                try:
                    el = page.query_selector(selector)
                    if el and el.is_visible():
                        return True
                except Exception:
                    continue

            # Check all frames (including recaptcha / cloudflare iframes)
            for frame in page.frames:
                try:
                    frame_url = frame.url.lower()
                    if "recaptcha" in frame_url or "cloudflare" in frame_url or "google.com" in frame_url:
                        for selector in selectors:
                            try:
                                el = frame.query_selector(selector)
                                if el:
                                    return True
                            except Exception:
                                continue
                    else:
                        for selector in ["#recaptcha-anchor", ".recaptcha-checkbox", ".rc-anchor-checkbox-holder", ".recaptcha-checkbox-border", ".rc-imageselect"]:
                            try:
                                el = frame.query_selector(selector)
                                if el:
                                    return True
                            except Exception:
                                continue
                except Exception:
                    continue

            return False

        except Exception as e:
            print(f"⚠ Error in CAPTCHA detection: {e}")
            return False

    def find_button(self, page: Page, button_type: str) -> Optional:
        """Find button by type with comprehensive selectors"""
        if button_type not in self.BUTTON_SELECTORS:
            return None
        
        for selector in self.BUTTON_SELECTORS[button_type]:
            try:
                buttons = page.query_selector_all(selector)
                for button in buttons:
                    if button.is_visible() and button.is_enabled():
                        print(f"✓ Found {button_type} button: {selector}")
                        return button
            except:
                continue
        
        return None
    
    def click_button_with_retry(self, page: Page, button) -> bool:
        """Click button with multiple methods and retry logic"""
        try:
            # Scroll button into view
            button.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.5, 1))
            
            click_methods = [
                ("Standard click", lambda: button.click(timeout=5000)),
                ("Force click", lambda: button.click(force=True, timeout=5000)),
                ("JS click", lambda: page.evaluate("el => el.click()", button)),
                ("Dispatch click", lambda: button.dispatch_event('click')),
            ]
            
            for method_name, click_func in click_methods:
                try:
                    click_func()
                    print(f"✓ Button clicked using: {method_name}")
                    time.sleep(random.uniform(2, 4))
                    return True
                except Exception as e:
                    print(f"⚠ {method_name} failed: {str(e)[:100]}")
                    continue
            
            return False
            
        except Exception as e:
            print(f"⚠ Error clicking button: {e}")
            return False
    
    def detect_page_type(self, page: Page) -> str:
        """Detect what type of Indeed application page we're on"""
        try:
            url = page.url.lower()
            
            # Check URL patterns
            if 'resume' in url or 'cv' in url:
                return 'resume'
            elif 'contact' in url or 'personal' in url:
                return 'contact'
            elif 'question' in url or 'screening' in url:
                return 'questions'
            elif 'review' in url:
                return 'review'
            elif 'confirmation' in url or 'success' in url:
                return 'success'
            
            # Check page content
            content = page.content().lower()
            
            if 'resume' in content[:5000]:
                return 'resume'
            elif 'contact information' in content[:5000]:
                return 'contact'
            elif any(term in content[:5000] for term in ['screening', 'question', 'eligibility']):
                return 'questions'
            
            return 'unknown'
            
        except:
            return 'unknown'
    
    def check_application_status(self, page: Page) -> str:
        """Check if application was successful, errored, or is in-progress,
        including SmartApply post-apply detection."""
        try:
            url = page.url.lower()

            # ---------------------------------------------
            # ✅ 1. SmartApply Post-Apply = Guaranteed Success
            # ---------------------------------------------
            if "smartapply" in url and "post-apply" in url:
                print("✓ SmartApply post-apply page detected → Application SUCCESS")
                return "success"

            # ---------------------------------------------
            # 2. Success indicators normally found
            # ---------------------------------------------
            for selector in self.SUCCESS_INDICATORS:
                if page.query_selector(selector):
                    return 'success'

            # ---------------------------------------------
            # 3. Check URL patterns for success
            # ---------------------------------------------
            if any(term in url for term in ['success', 'confirmation', 'complete']):
                return 'success'

            # ---------------------------------------------
            # 4. Error indicators
            # ---------------------------------------------
            for selector in self.ERROR_INDICATORS:
                elements = page.query_selector_all(selector)
                for elem in elements:
                    if elem.is_visible():
                        return 'error'

            return 'in_progress'

        except Exception:
            return 'unknown'


    def is_logged_in(self, page: Page) -> bool:
        """Check if user is logged in to Indeed"""
        try:
            # Check for sign in prompts
            if page.query_selector("a:has-text('Sign in')") or page.query_selector("button:has-text('Sign in')"):
                return False
            
            # Check for logged in indicators
            logged_in_indicators = [
                "a[href*='/account']",
                "button:has-text('Account')",
                "span.gnav-AccountMenu-userName",
                "div.gnav-account-menu"
            ]
            
            for selector in logged_in_indicators:
                if page.query_selector(selector):
                    return True
            
            return False
        except:
            return False
    
    def is_external_application(self, page: Page) -> bool:
        """Check if this is an external application (not handled by Indeed)"""
        try:
            # Check URL
            url = page.url.lower()
            if 'company' in url and 'indeed' not in url:
                return True
            
            # Check for external application messages
            external_selectors = [
                "text=Apply on company site",
                "text=Continue to company site",
                "text=External application",
                "text=Company's website"
            ]
            
            for selector in external_selectors:
                if page.query_selector(selector):
                    return True
            
            return False
        except:
            return False
    
    def fill_indeed_form_intelligent(self, page: Page) -> int:
        """Intelligently fill Indeed form fields using AI."""
        filled_count = 0
        
        try:
            print("📝 Analyzing and filling form fields with AI...")
            
            # Get all interactive form elements
            form_elements = page.query_selector_all("""
                input:not([type='hidden']):not([type='submit']),
                select,
                textarea
            """)
            
            print(f"Found {len(form_elements)} form elements to process")
            
            for i, field in enumerate(form_elements):
                try:
                    if not field.is_visible():
                        continue
                    
                    field_name = field.get_attribute('name') or ''
                    context = self.autofill.get_field_label_and_context(page, field)
                    
                    # Determine field type (potentially for logging; AI uses context)
                    field_type = self.autofill.analyze_field_type(context, field_name) 
                    
                    if field_type == 'unknown':
                        # Still attempt to fill unknown fields using AI
                        # print(f"   Skipping unknown field type.") # Remove or comment if always attempting
                        pass # Allow AI to process unknown types too
                    
                    # Try to fill the field - This call now triggers the AI in autofill
                    was_filled = self.autofill.fill_field_intelligently(page, field, field_type, context)
                    
                    if was_filled:
                        filled_count += 1
                        print(f"✓ Filled field #{i+1} ({field_type}) with AI")
                        time.sleep(random.uniform(0.3, 0.8)) # Small delay after AI fills
                    else:
                        print(f"✗ Failed to fill field #{i+1} ({field_type}) with AI")
                    
                except Exception as e:
                    print(f"⚠ Error processing field #{i+1}: {e}")
                    continue # Continue with the next field even if one fails
            
            print(f"✅ Successfully filled {filled_count} fields using AI")
            return filled_count
            
        except Exception as e:
            print(f"⚠ Error in AI-driven form filling: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            return filled_count
