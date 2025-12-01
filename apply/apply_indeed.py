"""
apply_indeed.py
Enhanced Indeed apply routine with specific form handling for Indeed's application system.
"""

from playwright.sync_api import Page
from apply.apply_common import fill_contact_fields, fill_standard_form_fields
from database import db
import time
import random

def human_like_delay(min_seconds=1, max_seconds=3):
    """Add random delays to mimic human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def fill_indeed_specific_form(page: Page):
    """Fill Indeed-specific form fields that aren't covered by the common form filler"""
    try:
        print("📝 Filling Indeed-specific form fields...")
        filled_count = 0
        
        # Get all form elements
        inputs = page.query_selector_all("input, select, textarea")
        
        for field in inputs:
            try:
                if not field.is_visible():
                    continue
                
                field_type = field.get_attribute('type') or ''
                tag_name = field.evaluate("el => el.tagName.toLowerCase()")
                field_name = field.get_attribute('name') or ''
                placeholder = field.get_attribute('placeholder') or ''
                field_id = field.get_attribute('id') or ''
                
                # Get context
                context = get_indeed_field_context(page, field).lower()
                all_context = f"{field_name} {placeholder} {field_id} {context}".lower()
                
                # Skip if already filled
                if tag_name == 'input' and field_type not in ['checkbox', 'radio']:
                    current_value = field.input_value()
                    if current_value and current_value.strip():
                        continue
                elif tag_name == 'select':
                    current_value = field.evaluate("el => el.value")
                    if current_value and current_value != "":
                        continue
                elif field_type == 'radio':
                    # Skip radio buttons that are already checked
                    if field.is_checked():
                        continue
                
                # Handle Indeed-specific fields
                from config import config
                
                # Work authorization fields
                if any(keyword in all_context for keyword in ['authorized', 'eligible', 'sponsorship', 'visa']):
                    if tag_name == 'select':
                        select_indeed_dropdown_option(field, "yes")
                        print("✓ Selected work authorization: Yes")
                        filled_count += 1
                    elif field_type == 'radio':
                        # Find and select the "yes" radio button in the same group
                        select_radio_option(page, field_name, "yes")
                        print("✓ Selected work authorization radio: Yes")
                        filled_count += 1
                
                # Experience fields
                elif any(keyword in all_context for keyword in ['years', 'experience']):
                    if tag_name == 'select':
                        select_indeed_dropdown_option(field, "2")
                        print("✓ Selected experience: 2 years")
                        filled_count += 1
                    else:
                        field.fill("2")
                        print("✓ Filled experience: 2 years")
                        filled_count += 1
                
                # Notice period fields
                elif any(keyword in all_context for keyword in ['notice', 'availability']):
                    if tag_name == 'select':
                        select_indeed_dropdown_option(field, "30")
                        print("✓ Selected notice period: 30 days")
                        filled_count += 1
                    else:
                        field.fill("30")
                        print("✓ Filled notice period: 30 days")
                        filled_count += 1
                
                # Salary expectations
                elif any(keyword in all_context for keyword in ['salary', 'compensation', 'ctc']):
                    if 'current' in all_context:
                        field.fill("6")
                        print("✓ Filled current salary")
                        filled_count += 1
                    else:
                        field.fill("7")
                        print("✓ Filled expected salary")
                        filled_count += 1
                
                # Location fields
                elif any(keyword in all_context for keyword in ['location', 'city', 'address']):
                    field.fill(config.LOCATION)
                    print("✓ Filled location")
                    filled_count += 1
                
                # Checkboxes for agreements
                elif field_type == 'checkbox' and not field.is_checked():
                    if any(keyword in all_context for keyword in ['agree', 'accept', 'certify']):
                        field.check()
                        print("✓ Checked agreement checkbox")
                        filled_count += 1
                
                # Auto-select "yes" or "true" for radio buttons
                elif field_type == 'radio':
                    radio_filled = handle_radio_button_selection(page, field, all_context)
                    if radio_filled:
                        filled_count += 1
                        
            except Exception as e:
                continue
        
        print(f"✓ Filled {filled_count} Indeed-specific fields")
        return filled_count > 0
        
    except Exception as e:
        print(f"⚠ Error filling Indeed form: {e}")
        return False

def handle_radio_button_selection(page: Page, field, all_context: str):
    """Handle radio button selection with auto yes/true preference"""
    try:
        field_name = field.get_attribute('name') or ''
        field_value = field.get_attribute('value') or ''
        field_id = field.get_attribute('id') or ''
        
        # Skip if already checked
        if field.is_checked():
            return False
        
        # Get the radio button group
        if field_name:
            radio_group = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
        else:
            return False
        
        # Analyze context to determine preferred selection
        preferred_value = determine_preferred_radio_value(all_context, field_value.lower())
        
        if preferred_value:
            # Check if this field matches the preferred value
            if field_value.lower() == preferred_value.lower():
                field.check()
                print(f"✓ Selected radio: {field_value} (preferred)")
                return True
            else:
                # Check if preferred option exists and select it
                for radio in radio_group:
                    if radio.get_attribute('value') and radio.get_attribute('value').lower() == preferred_value.lower():
                        if not radio.is_checked():
                            radio.check()
                            print(f"✓ Selected radio: {radio.get_attribute('value')} (preferred)")
                            return True
        
        return False
        
    except Exception as e:
        print(f"⚠ Error handling radio button: {e}")
        return False

def determine_preferred_radio_value(context: str, field_value: str):
    """Determine the preferred value for radio buttons based on context"""
    context_lower = context.lower()
    field_value_lower = field_value.lower()
    
    # Positive responses for binary questions
    positive_indicators = ['yes', 'true', 'agree', 'accept', 'approved', 'authorized', 'eligible', 'available']
    negative_indicators = ['no', 'false', 'disagree', 'reject', 'denied', 'unauthorized', 'ineligible', 'unavailable']
    
    # Check context for question type
    question_context = context_lower
    
    # For questions that typically want "yes" answers
    if any(keyword in question_context for keyword in [
        'authorized', 'eligible', 'sponsorship', 'visa', 'work authorization',
        'agree', 'accept', 'certify', 'acknowledge', 'confirm',
        'available', 'willing', 'able to', 'can you', 'do you have',
        'have you', 'are you', 'will you'
    ]):
        # Find the positive option
        for positive in positive_indicators:
            if field_value_lower == positive:
                return positive
        
        # If no match found, default to first positive option available
        return "yes"
    
    # For questions that might want "no" answers (like criminal history)
    elif any(keyword in question_context for keyword in [
        'criminal', 'felony', 'convicted', 'charged', 'arrested',
        'terminated', 'fired', 'dismissed'
    ]):
        # Prefer "no" for these sensitive questions
        for negative in negative_indicators:
            if field_value_lower == negative:
                return negative
        return "no"
    
    # Default to positive response for most questions
    return "yes"

def select_radio_option(page: Page, field_name: str, preferred_value: str):
    """Select a specific radio option by value in a group"""
    try:
        if not field_name:
            return False
            
        radio_buttons = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
        
        for radio in radio_buttons:
            value = radio.get_attribute('value') or ''
            if preferred_value.lower() in value.lower():
                if not radio.is_checked():
                    radio.check()
                    return True
        
        # Fallback: select first available radio button
        for radio in radio_buttons:
            if not radio.is_checked() and radio.is_enabled():
                radio.check()
                return True
        
        return False
    except Exception as e:
        print(f"⚠ Error selecting radio option: {e}")
        return False

def get_indeed_field_context(page: Page, field):
    """Get context for Indeed form fields"""
    try:
        context_parts = []
        
        # Get label
        field_id = field.get_attribute('id')
        if field_id:
            label = page.query_selector(f"label[for='{field_id}']")
            if label:
                context_parts.append(label.inner_text())
        
        # Get parent text
        parent = field.evaluate_handle('(el) => el.closest("div, li, label")')
        if parent:
            parent_text = parent.inner_text()
            if parent_text:
                context_parts.append(parent_text)
        
        # For radio buttons, get all labels in the group
        field_type = field.get_attribute('type')
        if field_type == 'radio':
            field_name = field.get_attribute('name')
            if field_name:
                # Get all radio buttons in group and their labels
                radio_group = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
                for radio in radio_group:
                    radio_id = radio.get_attribute('id')
                    if radio_id:
                        radio_label = page.query_selector(f"label[for='{radio_id}']")
                        if radio_label:
                            label_text = radio_label.inner_text()
                            if label_text and label_text not in context_parts:
                                context_parts.append(label_text)
        
        return " ".join(context_parts)
    except:
        return ""

def select_indeed_dropdown_option(field, option_value: str):
    """Select option in Indeed dropdown"""
    try:
        options = field.query_selector_all("option")
        for option in options:
            option_text = option.inner_text().lower()
            if option_value.lower() in option_text:
                option.click()
                return True
        
        # Fallback: select first non-empty option
        for option in options:
            if option.get_attribute('value') and option.get_attribute('value') != "":
                option.click()
                return True
        return False
    except:
        return False

def handle_indeed_application_flow(page: Page):
    """Main function to handle Indeed's multi-page application flow"""
    try:
        max_pages = 8
        current_page = 0
        
        while current_page < max_pages:
            current_page += 1
            print(f"\n📄 Processing page {current_page} of {max_pages}...")
            
            current_url = page.url.lower()
            print(f"Current URL: {current_url}")
            
            # Check what type of page we're on
            if any(page_type in current_url for page_type in [
                "resume-selection", 
                "resume-module", 
                "relevant-experience"
            ]):
                print("✓ Simple page detected - just clicking Continue")
                # These pages typically just need Continue clicked
                if not click_indeed_continue_button(page):
                    return False
                
            elif any(page_type in current_url for page_type in [
                "contact-info", 
                "contact-information",
                "questions",
                "application-questions"
            ]):
                print("✓ Form page detected - filling fields")
                # Fill forms on these pages
                fill_contact_fields(page)
                fill_standard_form_fields(page)
                fill_indeed_specific_form(page)
                
                if not click_indeed_continue_button(page):
                    return False
                    
            else:
                print("✓ Unknown page - trying to fill forms and continue")
                # Try to fill any forms and click continue
                fill_contact_fields(page)
                fill_standard_form_fields(page)
                fill_indeed_specific_form(page)
                
                if not click_indeed_continue_button(page):
                    return False
            
            # Wait for next page to load
            human_like_delay(2, 4)
            
            # Check if application was submitted
            if check_indeed_success(page):
                return True
            
            # Check if we're stuck (same URL for multiple pages)
            if current_page > 3 and "resume-module/relevant-experience" in current_url:
                print("⚠ Seems stuck on relevant experience page")
                # Try force continue
                if click_indeed_continue_button(page, force=True):
                    continue
                else:
                    print("❌ Cannot proceed from this page")
                    return False
        
        print("⚠ Reached maximum page limit")
        return False
        
    except Exception as e:
        print(f"⚠ Error in application flow: {e}")
        return False

def click_indeed_continue_button(page: Page, force=False):
    """Click Continue/Next/Submit button on Indeed pages"""
    try:
        print("🔍 Looking for action button...")
        human_like_delay(1, 2)
        
        # Comprehensive button selectors for Indeed
        button_selectors = [
            # Text-based selectors
            "button:has-text('Continue')",
            "button:has-text('Continue to next step')",
            "button:has-text('Next')",
            "button:has-text('Next step')",
            "button:has-text('Submit application')",
            "button:has-text('Submit your application')",
            "button:has-text('Submit')",
            
            # Indeed-specific classes
            "button.ia-continueButton",
            "button.ia-ContinuationButton",
            "button.ia-SubmitButton",
            "button.ia-Button--primary",
            
            # Data attributes
            "button[data-testid='continue-button']",
            "button[data-testid='submit-button']",
            "button[data-tn-element='continueButton']",
            
            # Type attributes
            "button[type='submit']",
            "input[type='submit']",
        ]
        
        # Try all selectors
        for selector in button_selectors:
            try:
                buttons = page.query_selector_all(selector)
                for button in buttons:
                    if is_indeed_button_clickable(button):
                        print(f"✓ Found button: {selector}")
                        return click_indeed_button_safely(page, button)
            except Exception as e:
                continue
        
        # If force mode, try any button at the bottom
        if force:
            print("⚠ Force mode: Trying any clickable button...")
            all_buttons = page.query_selector_all("button")
            # Try buttons from bottom up (action buttons are usually at bottom)
            for button in reversed(all_buttons):
                if is_indeed_button_clickable(button):
                    button_text = button.inner_text().strip()
                    print(f"✓ Trying force click on: '{button_text}'")
                    return click_indeed_button_safely(page, button)
        
        print("❌ No clickable button found")
        return False
        
    except Exception as e:
        print(f"⚠ Error finding button: {e}")
        return False

def is_indeed_button_clickable(button):
    """Check if button is clickable"""
    try:
        return (button and 
                button.is_visible() and 
                not button.is_disabled() and
                button.is_enabled())
    except:
        return False

def click_indeed_button_safely(page: Page, button):
    """Safely click button with multiple methods"""
    try:
        # Scroll into view
        button.scroll_into_view_if_needed()
        human_like_delay(0.5, 1)
        
        # Try different click methods
        methods = [
            lambda: button.click(),
            lambda: page.evaluate("(element) => element.click()", button),
            lambda: page.mouse.click(
                button.bounding_box()['x'] + button.bounding_box()['width']/2,
                button.bounding_box()['y'] + button.bounding_box()['height']/2
            ) if button.bounding_box() else False
        ]
        
        for method in methods:
            try:
                method()
                print("✓ Button clicked successfully")
                human_like_delay(2, 4)  # Wait for navigation
                return True
            except Exception as e:
                continue
        
        print("❌ All click methods failed")
        return False
        
    except Exception as e:
        print(f"⚠ Error clicking button: {e}")
        return False

def check_indeed_success(page: Page):
    """Check if Indeed application was successful"""
    human_like_delay(2, 3)
    
    # Success indicators
    success_indicators = [
        "text=Application submitted",
        "text=Successfully applied",
        "text=Your application has been sent",
        "text=Application complete",
        "div.ia-SuccessMessage",
        "h1:has-text('Application submitted')",
    ]
    
    for indicator in success_indicators:
        if page.query_selector(indicator):
            print("✅ APPLICATION SUBMITTED SUCCESSFULLY!")
            return True
    
    # Error indicators
    error_indicators = [
        "div.icl-Alert--error",
        "div.error-message",
        "span.error",
        "div[role='alert']"
    ]
    
    for indicator in error_indicators:
        if page.query_selector(indicator):
            error_text = page.query_selector(indicator).inner_text()
            print(f"❌ Error: {error_text}")
            return False
    
    return None  # Unknown state

def attempt_apply(page: Page, job: dict):
    """Main Indeed apply function"""
    link = job.get("link")
    if not link:
        return False
    
    print(f"\n{'='*60}")
    print(f"🔗 Opening: {job.get('role')} @ {job.get('company')}")
    print(f"{'='*60}")
    
    try:
        # Navigate to job page
        page.goto(link, wait_until="domcontentloaded", timeout=30000)
        human_like_delay(3, 5)
        
        # Check if logged in
        if page.query_selector("a:has-text('Sign in')"):
            print("⚠ Not logged in to Indeed. Please log in first.")
            return False
        
        # Look for apply button
        apply_selectors = [
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "button.ia-continueButton",
            ".indeed-apply-button",
            "button[data-indeed-apply-button-label]",
        ]
        
        apply_clicked = False
        for selector in apply_selectors:
            try:
                button = page.query_selector(selector)
                if button and button.is_visible():
                    print(f"✓ Found apply button: {selector}")
                    button.scroll_into_view_if_needed()
                    human_like_delay(1, 2)
                    button.click()
                    apply_clicked = True
                    human_like_delay(3, 5)
                    break
            except Exception as e:
                continue
        
        if not apply_clicked:
            print("⚠ No apply button found")
            return False
        
        # Check for external application
        if page.query_selector("text=Apply on company site"):
            print("⚠ External application required - skipping")
            return False
        
        # Handle the multi-page application flow
        success = handle_indeed_application_flow(page)
        
        if success:
            print("✅ Application process completed successfully!")
            added = db.add_job(link, job.get("company"), job.get("role"))
            return added
        else:
            print("❌ Application process failed")
            return False
        
    except Exception as e:
        print(f"\n❌ Error during application: {e}")
        import traceback
        traceback.print_exc()
        return False