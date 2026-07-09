# navigation/modal_navigation.py

import time
import random
from typing import Optional
from playwright.sync_api import Page, Locator


class ModalNavigator:
    """Handles navigation within the LinkedIn Easy Apply modal (STRICTLY scoped)"""

    MODAL_ROOT_SELECTORS = [
        "div.jobs-easy-apply-modal",
        "div[role='dialog'].artdeco-modal"
    ]

    BUTTON_SELECTORS = {
        "submit": [
            "button[aria-label='Submit application']",
            "button:has-text('Submit application')",
            "button:has-text('Submit')"
        ],
        "review": [
            "button:has-text('Review')",
            "button[aria-label*='Review']"
        ],
        "next": [
            "button:has-text('Next')",
            "button[aria-label='Continue to next step']"
        ]
    }

    # Updated to NOT block "discard" in the save dialog
    BLOCKED_BUTTON_TEXT = ["cancel"]

    SUCCESS_INDICATORS = [
        "application sent",
        "application submitted",
        "your application was sent",
        "application complete"
    ]

    def __init__(self, autofill):
        self.autofill = autofill

    # -------------------------
    # Public API
    # -------------------------
    def handle_application_modal(self, page: Page, max_steps: int = 10) -> bool:
        for step in range(max_steps):
            print(f"\n--- Modal Step {step + 1} ---")
            time.sleep(random.uniform(1.2, 2.2))

            modal = self._get_active_modal(page)
            if not modal:
                print("❌ Modal not visible anymore")
                return False

            # Check if this is the "Save this application?" dialog
            if self._is_save_dialog(modal):
                print("⚠️  'Save this application?' dialog detected - clicking Discard")
                if self._handle_save_dialog(modal):
                    return False  # Application was discarded
                continue

            self._scroll_modal_top(modal)

            print("Filling fields...")
            self.autofill.autofill_standard_form(page)

            # CRITICAL: Check for unfilled required fields (especially radio buttons)
            if self._has_unfilled_required_fields(modal):
                print("⚠️  Unfilled required fields detected (possibly radio buttons)")
                
                # Try one more time to fill them
                print("   Attempting to fill required fields again...")
                self.autofill.autofill_standard_form(page)
                time.sleep(1.0)
                
                # Check again
                if self._has_unfilled_required_fields(modal):
                    print("❌ Still have unfilled required fields - stopping")
                    return False

            time.sleep(random.uniform(0.8, 1.5))

            button_type, button = self._find_action_button(modal)
            if not button:
                if self._check_for_errors(modal):
                    print("⚠ Errors detected, stopping")
                    return False
                continue

            if button_type == "submit":
                return self._submit(page, modal, button)

            self._safe_click(button, button_type)

        print("⚠ Max modal steps reached")
        return False

    # -------------------------
    # Modal helpers
    # -------------------------
    def _get_active_modal(self, page: Page) -> Optional[Locator]:
        for selector in self.MODAL_ROOT_SELECTORS:
            try:
                modal = page.locator(selector)
                if modal.count() and modal.first.is_visible():
                    return modal.first
            except:
                pass
        return None

    def _is_save_dialog(self, modal: Locator) -> bool:
        """Check if this is the 'Save this application?' dialog"""
        try:
            modal_text = modal.inner_text().lower()
            
            # Check for specific text patterns
            save_indicators = [
                "save this application" in modal_text,
                "save to return to this application" in modal_text,
                ("any uploaded files will not be saved" in modal_text and 
                 "discard" in modal_text and "save" in modal_text)
            ]
            
            return any(save_indicators)
        except:
            return False

    def _handle_save_dialog(self, modal: Locator) -> bool:
        """Handle the 'Save this application?' dialog - click Discard"""
        try:
            # Look for the Discard button
            discard_selectors = [
                "button:has-text('Discard')",
                "button[aria-label*='Discard']",
                "button:has-text('discard')"
            ]
            
            for selector in discard_selectors:
                try:
                    discard_btn = modal.locator(selector)
                    if discard_btn.count() and discard_btn.first.is_visible():
                        discard_btn.first.click(timeout=3000)
                        print("✓ Clicked Discard on save dialog")
                        time.sleep(1.0)
                        return True
                except:
                    continue
            
            print("⚠️  Could not find Discard button")
            return False
            
        except Exception as e:
            print(f"⚠️  Error handling save dialog: {e}")
            return False

    def _has_unfilled_required_fields(self, modal: Locator) -> bool:
        """Check if there are unfilled required fields (especially radio buttons)"""
        try:
            # Look for validation error messages
            error_selectors = [
                "div.artdeco-inline-feedback--error",
                "span.artdeco-inline-feedback__message",
                "[role='alert']"
            ]
            
            for selector in error_selectors:
                errors = modal.locator(selector)
                if errors.count() > 0:
                    print(f"   Found validation errors: {errors.count()}")
                    return True
            
            # Look for unfilled required radio button groups
            try:
                radio_groups = modal.evaluate("""
                    () => {
                        const radioInputs = document.querySelectorAll('input[type="radio"][required]');
                        const groups = new Set();
                        
                        radioInputs.forEach(radio => {
                            const name = radio.getAttribute('name');
                            if (name) groups.add(name);
                        });
                        
                        let unfilledGroups = [];
                        groups.forEach(name => {
                            const radios = document.querySelectorAll(`input[type="radio"][name="${name}"]`);
                            const isAnyChecked = Array.from(radios).some(r => r.checked);
                            if (!isAnyChecked) {
                                unfilledGroups.push(name);
                            }
                        });
                        
                        return unfilledGroups;
                    }
                """)
                
                if radio_groups and len(radio_groups) > 0:
                    print(f"   Found {len(radio_groups)} unfilled required radio groups")
                    return True
                    
            except Exception as e:
                print(f"   Could not check radio groups: {e}")
            
            return False
            
        except Exception as e:
            print(f"   Error checking required fields: {e}")
            return False

    def _find_action_button(self, modal: Locator):
        for button_type in ["submit", "review", "next"]:
            for selector in self.BUTTON_SELECTORS[button_type]:
                try:
                    btn = modal.locator(selector)
                    if btn.count():
                        btn = btn.first
                        text = (btn.inner_text() or "").lower()
                        if (
                            btn.is_visible()
                            and btn.is_enabled()
                            and not any(x in text for x in self.BLOCKED_BUTTON_TEXT)
                        ):
                            return button_type, btn
                except:
                    continue
        return None, None

    # -------------------------
    # Actions
    # -------------------------
    def _submit(self, page: Page, modal: Locator, button: Locator) -> bool:
        print("Submitting application...")
        if not self._safe_click(button, "submit"):
            return False

        time.sleep(random.uniform(3, 5))
        return self._is_success(page)

    def _safe_click(self, button: Locator, label: str) -> bool:
        for attempt in range(2):
            try:
                button.scroll_into_view_if_needed()
                button.click(timeout=5000, force=attempt == 1)
                print(f"Clicked {label}")
                return True
            except Exception as e:
                print(f"{label} click failed ({attempt + 1}): {str(e)[:60]}")
        return False

    # -------------------------
    # Validation
    # -------------------------
    def _is_success(self, page: Page) -> bool:
        text = page.content().lower()
        if any(s in text for s in self.SUCCESS_INDICATORS):
            print("✓ Application submitted")
            return True

        try:
            if not page.is_visible("div.jobs-easy-apply-modal"):
                print("✓ Modal closed → success assumed")
                return True
        except:
            pass

        return False

    def _check_for_errors(self, modal: Locator) -> bool:
        try:
            errors = modal.locator("div.artdeco-inline-feedback--error")
            if errors.count():
                print("❌ Validation errors present")
                return True
        except:
            pass
        return False

    def _scroll_modal_top(self, modal: Locator):
        try:
            modal.evaluate("el => el.scrollTop = 0")
        except:
            pass