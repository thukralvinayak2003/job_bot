"""
apply_indeed.py
Enhanced Indeed auto-apply with robust form handling and error recovery.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from apply.base_apply import fill_contact_fields, fill_standard_form_fields
from database import db
import time
import random
import re

def human_like_delay(min_seconds=1, max_seconds=3):
    """Add random delays to mimic human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def get_field_label_and_context(page: Page, field) -> str:
    """Get comprehensive context for a form field"""
    try:
        context_parts = []
        
        # Get field attributes
        field_id = field.get_attribute('id') or ''
        field_name = field.get_attribute('name') or ''
        placeholder = field.get_attribute('placeholder') or ''
        aria_label = field.get_attribute('aria-label') or ''
        
        context_parts.extend([field_id, field_name, placeholder, aria_label])
        
        # Get associated label
        if field_id:
            label = page.query_selector(f"label[for='{field_id}']")
            if label:
                context_parts.append(label.inner_text())
        
        # Get parent container text
        try:
            parent = field.evaluate_handle("""
                el => {
                    let parent = el.closest('div[class*="question"], div[class*="field"], div[class*="form"], fieldset, li');
                    return parent || el.parentElement;
                }
            """)
            if parent:
                parent_text = parent.inner_text()
                # Only add if it's not too long (likely to be just the label)
                if parent_text and len(parent_text) < 200:
                    context_parts.append(parent_text)
        except:
            pass
        
        # For radio buttons, get all options in the group
        field_type = field.get_attribute('type') or ''
        if field_type == 'radio' and field_name:
            try:
                radio_group = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
                for radio in radio_group[:5]:  # Limit to first 5 to avoid too much text
                    radio_id = radio.get_attribute('id') or ''
                    if radio_id:
                        radio_label = page.query_selector(f"label[for='{radio_id}']")
                        if radio_label:
                            context_parts.append(radio_label.inner_text())
            except:
                pass
        
        return " ".join(filter(None, context_parts))
    except Exception as e:
        return ""

def analyze_field_type(context: str, field_name: str) -> str:
    """Determine what type of information a field is asking for"""
    context_lower = context.lower()
    name_lower = field_name.lower()
    combined = f"{context_lower} {name_lower}"
    
    # Work authorization
    if any(term in combined for term in [
        'authorized', 'authorization', 'eligible', 'eligibility',
        'sponsorship', 'visa', 'work permit', 'legally authorized',
        'require sponsorship', 'need sponsorship'
    ]):
        return 'work_auth'
    
    # Years of experience
    if any(term in combined for term in [
        'years of experience', 'years experience', 'how many years',
        'experience in years', 'total experience', 'relevant experience'
    ]):
        return 'experience_years'
    
    # Notice period
    if any(term in combined for term in [
        'notice period', 'notice', 'availability', 'available to start',
        'when can you start', 'start date', 'joining'
    ]):
        return 'notice_period'
    
    # Salary - current
    if any(term in combined for term in [
        'current salary', 'current ctc', 'current compensation',
        'present salary', 'existing salary'
    ]):
        return 'current_salary'
    
    # Salary - expected
    if any(term in combined for term in [
        'expected salary', 'expected ctc', 'desired salary',
        'salary expectation', 'target salary', 'compensation expectation'
    ]):
        return 'expected_salary'
    
    # Location/Address
    if any(term in combined for term in [
        'location', 'city', 'address', 'where are you based',
        'current location', 'home address'
    ]):
        return 'location'
    
    # Education level
    if any(term in combined for term in [
        'education', 'degree', 'qualification', 'highest education',
        'educational background'
    ]):
        return 'education'
    
    # Generic yes/no questions
    if any(term in combined for term in [
        'do you', 'are you', 'have you', 'can you', 'will you',
        'would you', 'did you'
    ]):
        # Check for negative questions (where "no" is appropriate)
        if any(term in combined for term in [
            'criminal', 'felony', 'convicted', 'terminated', 'fired',
            'dismissed', 'lawsuit', 'sued'
        ]):
            return 'negative_question'
        return 'positive_question'
    
    return 'unknown'

def fill_field_intelligently(page: Page, field, field_type: str, context: str) -> bool:
    """Fill a field based on its detected type"""
    from config import config
    
    try:
        tag_name = field.evaluate("el => el.tagName.toLowerCase()")
        input_type = field.get_attribute('type') or ''
        
        # Skip if already filled
        if tag_name in ['input', 'textarea'] and input_type not in ['checkbox', 'radio']:
            current_value = field.input_value()
            if current_value and current_value.strip():
                return False
        elif tag_name == 'select':
            current_value = field.evaluate("el => el.value")
            if current_value:
                return False
        elif input_type in ['checkbox', 'radio']:
            if field.is_checked():
                return False
        
        # Handle based on field type
        if field_type == 'work_auth':
            if tag_name == 'select':
                return select_dropdown_option(field, ['yes', 'authorized', 'no sponsorship required'])
            elif input_type == 'radio':
                return select_radio_in_group(page, field, ['yes', 'true', 'authorized'])
            else:
                field.fill('Yes')
                return True
        
        elif field_type == 'experience_years':
            years = getattr(config, 'YEARS_EXPERIENCE', '2')
            if tag_name == 'select':
                return select_dropdown_option(field, [years, f'{years} years', f'{years}+'])
            else:
                field.fill(str(years))
                return True
        
        elif field_type == 'notice_period':
            notice = getattr(config, 'NOTICE_PERIOD', '30')
            if tag_name == 'select':
                return select_dropdown_option(field, [notice, f'{notice} days', '1 month'])
            else:
                field.fill(str(notice))
                return True
        
        elif field_type == 'current_salary':
            salary = getattr(config, 'CURRENT_SALARY', '6')
            field.fill(str(salary))
            return True
        
        elif field_type == 'expected_salary':
            salary = getattr(config, 'EXPECTED_SALARY', '8')
            field.fill(str(salary))
            return True
        
        elif field_type == 'location':
            location = getattr(config, 'LOCATION', 'India')
            field.fill(location)
            return True
        
        elif field_type == 'education':
            if tag_name == 'select':
                return select_dropdown_option(field, ["bachelor", "bachelor's", "b.tech", "undergraduate"])
            return False
        
        elif field_type == 'positive_question':
            if input_type == 'radio':
                return select_radio_in_group(page, field, ['yes', 'true'])
            elif input_type == 'checkbox':
                if not field.is_checked():
                    field.check()
                    return True
            return False
        
        elif field_type == 'negative_question':
            if input_type == 'radio':
                return select_radio_in_group(page, field, ['no', 'false'])
            return False
        
        return False
        
    except Exception as e:
        print(f"⚠ Error filling field: {e}")
        return False

def select_dropdown_option(field, preferred_values: list) -> bool:
    """Select option from dropdown that matches preferred values"""
    try:
        options = field.query_selector_all("option")
        
        # First pass: exact matches
        for option in options:
            value = (option.get_attribute('value') or '').lower()
            text = option.inner_text().lower()
            
            for pref in preferred_values:
                pref_lower = str(pref).lower()
                if pref_lower == value or pref_lower == text:
                    field.select_option(value=option.get_attribute('value'))
                    return True
        
        # Second pass: partial matches
        for option in options:
            value = (option.get_attribute('value') or '').lower()
            text = option.inner_text().lower()
            
            for pref in preferred_values:
                pref_lower = str(pref).lower()
                if pref_lower in value or pref_lower in text:
                    field.select_option(value=option.get_attribute('value'))
                    return True
        
        return False
    except Exception as e:
        print(f"⚠ Error selecting dropdown: {e}")
        return False

def select_radio_in_group(page: Page, field, preferred_values: list) -> bool:
    """Select radio button in group matching preferred values"""
    try:
        field_name = field.get_attribute('name')
        if not field_name:
            return False
        
        radio_buttons = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
        
        # First pass: exact matches
        for radio in radio_buttons:
            value = (radio.get_attribute('value') or '').lower()
            radio_id = radio.get_attribute('id') or ''
            
            # Get label text
            label_text = ''
            if radio_id:
                label = page.query_selector(f"label[for='{radio_id}']")
                if label:
                    label_text = label.inner_text().lower()
            
            for pref in preferred_values:
                pref_lower = str(pref).lower()
                if pref_lower == value or pref_lower == label_text:
                    if not radio.is_checked():
                        radio.check()
                        return True
        
        # Second pass: partial matches
        for radio in radio_buttons:
            value = (radio.get_attribute('value') or '').lower()
            radio_id = radio.get_attribute('id') or ''
            
            label_text = ''
            if radio_id:
                label = page.query_selector(f"label[for='{radio_id}']")
                if label:
                    label_text = label.inner_text().lower()
            
            for pref in preferred_values:
                pref_lower = str(pref).lower()
                if pref_lower in value or pref_lower in label_text:
                    if not radio.is_checked():
                        radio.check()
                        return True
        
        return False
    except Exception as e:
        print(f"⚠ Error selecting radio: {e}")
        return False

def fill_indeed_form_intelligent(page: Page) -> int:
    """Intelligently fill Indeed form fields"""
    filled_count = 0
    
    try:
        print("📝 Analyzing and filling form fields...")
        
        # First fill contact fields (email, phone, name)
        fill_contact_fields(page)
        fill_standard_form_fields(page)
        
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
                context = get_field_label_and_context(page, field)
                
                # Determine field type
                field_type = analyze_field_type(context, field_name)
                
                if field_type == 'unknown':
                    continue
                
                # Try to fill the field
                was_filled = fill_field_intelligently(page, field, field_type, context)
                
                if was_filled:
                    filled_count += 1
                    print(f"✓ Filled field #{i+1} ({field_type})")
                    human_like_delay(0.3, 0.8)
                
            except Exception as e:
                continue
        
        print(f"✅ Successfully filled {filled_count} fields")
        return filled_count
        
    except Exception as e:
        print(f"⚠ Error in form filling: {e}")
        return filled_count

def find_continue_button(page: Page) -> any:
    """Find the continue/next/submit button with comprehensive selectors"""
    
    button_patterns = [
        # Primary Indeed buttons
        ("button[data-testid='continue-button']", "data-testid continue"),
        ("button[data-testid='submit-button']", "data-testid submit"),
        ("button.ia-continueButton", "ia-continueButton class"),
        ("button.ia-ContinuationButton", "ia-ContinuationButton class"),
        
        # Text-based selectors
        ("button:has-text('Continue')", "text: Continue"),
        ("button:has-text('Continue to next step')", "text: Continue to next step"),
        ("button:has-text('Next')", "text: Next"),
        ("button:has-text('Submit')", "text: Submit"),
        ("button:has-text('Submit application')", "text: Submit application"),
        
        # Generic submit buttons
        ("button[type='submit']", "type=submit"),
        ("input[type='submit']", "input type=submit"),
    ]
    
    for selector, description in button_patterns:
        try:
            buttons = page.query_selector_all(selector)
            for button in buttons:
                if button.is_visible() and button.is_enabled():
                    print(f"✓ Found button: {description}")
                    return button
        except:
            continue
    
    # Last resort: find any enabled button at the bottom of the page
    try:
        all_buttons = page.query_selector_all("button[type='submit'], button:not([type='button'])")
        visible_buttons = [b for b in all_buttons if b.is_visible() and b.is_enabled()]
        
        if visible_buttons:
            # Return the last visible button (usually the action button)
            button = visible_buttons[-1]
            button_text = button.inner_text()[:50]
            print(f"✓ Found button (fallback): '{button_text}'")
            return button
    except:
        pass
    
    return None

def click_button_with_retry(page: Page, button) -> bool:
    """Click button with multiple methods and retry logic"""
    try:
        # Scroll button into view
        button.scroll_into_view_if_needed()
        human_like_delay(0.5, 1)
        
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
                human_like_delay(2, 4)
                return True
            except Exception as e:
                print(f"⚠ {method_name} failed: {str(e)[:100]}")
                continue
        
        return False
        
    except Exception as e:
        print(f"⚠ Error clicking button: {e}")
        return False

def detect_page_type(page: Page) -> str:
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

def check_application_status(page: Page) -> str:
    """Check if application was successful, has errors, or is in progress"""
    try:
        # Success indicators
        success_selectors = [
            "text=Application submitted",
            "text=Successfully applied",
            "text=Your application has been sent",
            "text=Application complete",
            "div.ia-SuccessMessage",
            "h1:has-text('Application submitted')",
            "[data-testid='success-message']",
        ]
        
        for selector in success_selectors:
            if page.query_selector(selector):
                return 'success'
        
        # Error indicators
        error_selectors = [
            "div.icl-Alert--error",
            "div.error-message",
            "span.error",
            "[role='alert'][aria-live='assertive']",
            "div[class*='error']",
        ]
        
        for selector in error_selectors:
            elements = page.query_selector_all(selector)
            for elem in elements:
                if elem.is_visible():
                    return 'error'
        
        # Check URL for success indicators
        if any(term in page.url.lower() for term in ['success', 'confirmation', 'complete']):
            return 'success'
        
        return 'in_progress'
        
    except:
        return 'unknown'

def handle_indeed_application_flow(page: Page) -> bool:
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
                button = find_continue_button(page)
                if button and click_button_with_retry(page, button):
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
        status = check_application_status(page)
        if status == 'success':
            print("✅ APPLICATION SUCCESSFUL!")
            return True
        elif status == 'error':
            print("❌ Error detected on page")
            # Try to continue anyway
        
        # Detect page type
        page_type = detect_page_type(page)
        print(f"Page type: {page_type}")
        
        # Fill forms if needed
        if page_type in ['contact', 'questions', 'unknown']:
            filled = fill_indeed_form_intelligent(page)
            if filled > 0:
                print(f"✓ Filled {filled} fields")
                human_like_delay(1, 2)
        
        # Find and click continue button
        button = find_continue_button(page)
        if not button:
            print("❌ No continue button found")
            
            # Try to take a screenshot for debugging
            try:
                page.screenshot(path=f"indeed_stuck_page_{current_page_num}.png")
                print(f"📸 Screenshot saved: indeed_stuck_page_{current_page_num}.png")
            except:
                pass
            
            return False
        
        # Click the button
        if not click_button_with_retry(page, button):
            print("❌ Failed to click continue button")
            return False
        
        # Wait for navigation/changes
        human_like_delay(3, 5)
        
        # Check again for success after clicking
        status = check_application_status(page)
        if status == 'success':
            print("✅ APPLICATION SUCCESSFUL!")
            return True
    
    print("⚠ Reached maximum page limit without completion")
    return False

def attempt_apply(page: Page, job: dict) -> bool:
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
        # Navigate to job page
        print("📄 Loading job page...")
        page.goto(link, wait_until="domcontentloaded", timeout=30000)
        human_like_delay(3, 5)
        
        # Check if logged in
        if page.query_selector("a:has-text('Sign in')") or page.query_selector("button:has-text('Sign in')"):
            print("❌ Not logged in to Indeed")
            return False
        
        # Look for apply button
        print("🔍 Looking for apply button...")
        apply_button = None
        
        apply_selectors = [
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "button.ia-continueButton",
            "button[data-indeed-apply-button-label]",
            ".indeed-apply-button",
            "a:has-text('Apply now')",
        ]
        
        for selector in apply_selectors:
            try:
                buttons = page.query_selector_all(selector)
                for btn in buttons:
                    if btn.is_visible() and 'apply' in btn.inner_text().lower():
                        apply_button = btn
                        break
                if apply_button:
                    break
            except:
                continue
        
        if not apply_button:
            print("⚠ No apply button found (may be external application)")
            return False
        
        # Click apply button
        print("✓ Found apply button, clicking...")
        apply_button.scroll_into_view_if_needed()
        human_like_delay(1, 2)
        apply_button.click()
        human_like_delay(4, 6)
        
        # Check for external redirect
        if 'company' in page.url.lower() and 'indeed' not in page.url.lower():
            print("⚠ Redirected to external site, cannot auto-apply")
            return False
        
        # Check for "Apply on company site" message
        if page.query_selector("text=Apply on company site") or page.query_selector("text=Continue to company site"):
            print("⚠ External application required")
            return False
        
        # Start the application flow
        print("\n🚀 Starting application process...")
        success = handle_indeed_application_flow(page)
        
        if success:
            print("\n" + "="*70)
            print("✅ APPLICATION COMPLETED SUCCESSFULLY!")
            print("="*70)
            
            # Record in database
            db.add_job(link, job.get("company"), job.get("role"), status="applied")
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