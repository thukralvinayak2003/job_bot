"""
apply_common.py
Enhanced version with better LinkedIn Easy Apply support for CTC fields and experience questions.
"""
from playwright.sync_api import Page
import time
import re

def autofill_standard_form(page: Page):
    """
    Enhanced autofill for LinkedIn Easy Apply with specific handling for CTC and experience fields.
    Works within the LinkedIn modal dialog.
    """
    try:
        print("Starting form autofill...")
        
        # First, handle LinkedIn-specific fields that need special attention
        fill_linkedin_specific_fields(page)
        
        # Then handle standard fields
        fill_standard_form_fields(page)
        
        # Handle email and phone
        fill_contact_fields(page)
        
        # Handle all types of dropdowns
        fill_all_dropdowns(page)
        
        # Handle radio buttons and checkboxes
        fill_radio_and_checkbox_fields(page)
        
        # Handle number inputs specifically for CTC and experience
        fill_number_input_fields(page)
        
        # Handle text areas
        fill_textarea_fields(page)
        
        # Small delay for validation
        time.sleep(0.5)
        
        print("Form autofill completed")
        
    except Exception as e:
        print(f"Error in autofill: {e}")

def get_field_context(page: Page, field) -> str:
    """
    Get surrounding context text for a field (label, placeholder, aria-label, etc.)
    """
    try:
        context_parts = []
        
        # Get placeholder
        placeholder = field.get_attribute('placeholder')
        if placeholder:
            context_parts.append(placeholder)
        
        # Get aria-label
        aria_label = field.get_attribute('aria-label')
        if aria_label:
            context_parts.append(aria_label)
        
        # Get associated label
        field_id = field.get_attribute('id')
        if field_id:
            label = page.query_selector(f"label[for='{field_id}']")
            if label:
                label_text = label.inner_text()
                if label_text:
                    context_parts.append(label_text)
        
        # Get parent label (if field is inside label)
        try:
            parent_label = field.evaluate("""
                el => {
                    let parent = el.closest('label');
                    return parent ? parent.innerText : '';
                }
            """)
            if parent_label:
                context_parts.append(parent_label)
        except:
            pass
        
        # Get nearby text (previous sibling or parent text)
        try:
            nearby_text = field.evaluate("""
                el => {
                    let text = '';
                    // Check previous sibling
                    if (el.previousElementSibling) {
                        text += el.previousElementSibling.innerText || '';
                    }
                    // Check parent's text
                    if (el.parentElement) {
                        text += ' ' + el.parentElement.innerText || '';
                    }
                    return text;
                }
            """)
            if nearby_text:
                context_parts.append(nearby_text)
        except:
            pass
        
        return ' '.join(context_parts).strip()
    except:
        return ""

def fill_linkedin_specific_fields(page: Page):
    """Handle LinkedIn-specific field patterns"""
    try:
        # Scope to modal only
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        # Get all form fields within modal
        all_inputs = page.query_selector_all(f"{modal_selector} input, {modal_selector} textarea, {modal_selector} select")
        
        for field in all_inputs:
            if not field.is_visible():
                continue
                
            try:
                field_type = field.get_attribute('type') or ''
                tag_name = field.evaluate("el => el.tagName.toLowerCase()")
                
                # Get context from surrounding elements
                context_text = get_field_context(page, field).lower()
                
                # Skip if already filled (except for checkboxes and radios)
                if tag_name == 'input' and field_type not in ['checkbox', 'radio']:
                    current_value = field.input_value()
                    if current_value and current_value.strip():
                        continue
                elif tag_name == 'select':
                    current_value = field.evaluate("el => el.value")
                    if current_value and current_value != "":
                        continue
                
                # Handle CTC fields specifically
                if any(keyword in context_text for keyword in ['current ctc', 'current compensation', 'current salary', 'current annual']):
                    handle_ctc_field(page, field, context_text, is_current=True)
                
                # Handle expected salary
                elif any(keyword in context_text for keyword in ['expected ctc', 'expected salary', 'desired compensation', 'expected annual']):
                    handle_ctc_field(page, field, context_text, is_current=False)
                
                # Handle experience years
                elif any(keyword in context_text for keyword in ['years of experience', 'total experience', 'professional experience', 'work experience']):
                    handle_experience_field(page, field, context_text)
                
                # Handle technology-specific experience
                elif any(tech in context_text for tech in ['python', 'javascript', 'react', 'node', 'sql', 'mongodb', '.net', 'java', 'aws']):
                    handle_tech_experience_field(page, field, context_text)
                
                # Handle notice period
                elif any(keyword in context_text for keyword in ['notice period', 'availability', 'joining']):
                    handle_notice_period_field(page, field)
                    
            except Exception as e:
                print(f"Error processing field: {e}")
                continue
                
    except Exception as e:
        print(f"Error in LinkedIn specific fields: {e}")

def handle_ctc_field(page: Page, field, context_text: str, is_current: bool = True):
    """Handle CTC/Salary fields"""
    try:
        from config import config
        
        # Determine the value to use
        if is_current:
            # Check if it's in lakhs or absolute value
            if 'lakh' in context_text or 'lpa' in context_text:
                value = config.ANSWERS.get("current_ctc", "6.0")
            else:
                value = config.ANSWERS.get("current_salary", "470000")
        else:
            if 'lakh' in context_text or 'lpa' in context_text:
                value = config.ANSWERS.get("expected_ctc", "7.0")
            else:
                value = config.ANSWERS.get("expected_salary", "700000")
        
        field.fill(str(value))
        time.sleep(0.3)
        print(f"✓ Filled {'current' if is_current else 'expected'} CTC: {value}")
    except Exception as e:
        print(f"Error filling CTC field: {e}")

def handle_experience_field(page: Page, field, context_text: str):
    """Handle experience years fields"""
    try:
        from config import config
        
        # Check for specific technology mentions
        for tech, answer_key in [
            ('python', 'experience_python'),
            ('javascript', 'experience_javascript'),
            ('react', 'experience_react'),
            ('node', 'experience_nodejs'),
            ('sql', 'experience_sql'),
            ('mongodb', 'experience_mongodb'),
            ('.net', 'experience_dotnet'),
        ]:
            if tech in context_text:
                value = config.ANSWERS.get(answer_key, "2")
                field.fill(str(value))
                time.sleep(0.3)
                print(f"✓ Filled {tech} experience: {value}")
                return
        
        # Default to total experience
        value = config.ANSWERS.get("total_experience_years", "2")
        field.fill(str(value))
        time.sleep(0.3)
        print(f"✓ Filled experience: {value}")
    except Exception as e:
        print(f"Error filling experience field: {e}")

def handle_tech_experience_field(page: Page, field, context_text: str):
    """Handle technology-specific experience fields"""
    try:
        from config import config
        
        # Map common technologies to config keys
        tech_mappings = {
            'python': 'experience_python',
            'javascript': 'experience_javascript',
            'react': 'experience_react',
            'reactjs': 'experience_react',
            'node': 'experience_nodejs',
            'nodejs': 'experience_nodejs',
            'express': 'experience_express',
            'mongodb': 'experience_mongodb',
            'sql': 'experience_sql',
            'postgresql': 'experience_postgresql',
            'aws': 'experience_aws',
            'docker': 'experience_docker',
            'typescript': 'experience_typescript',
            '.net': 'experience_dotnet',
        }
        
        for tech, answer_key in tech_mappings.items():
            if tech in context_text:
                value = config.ANSWERS.get(answer_key, "2")
                field.fill(str(value))
                time.sleep(0.3)
                print(f"✓ Filled {tech} experience: {value}")
                return
        
        # Default to 2 years if no specific match
        field.fill("2")
        time.sleep(0.3)
        print(f"✓ Filled tech experience: 2")
    except Exception as e:
        print(f"Error filling tech experience field: {e}")

def handle_notice_period_field(page: Page, field):
    """Handle notice period fields"""
    try:
        from config import config
        value = config.ANSWERS.get("notice_period", "30 days")
        
        tag_name = field.evaluate("el => el.tagName.toLowerCase()")
        if tag_name == 'select':
            # Try to select option with "30" or "1 month"
            try:
                field.select_option(label="30 days")
            except:
                try:
                    field.select_option(label="1 month")
                except:
                    field.select_option(index=1)  # Select first option if exact match fails
        else:
            field.fill(value)
        
        time.sleep(0.3)
        print(f"✓ Filled notice period: {value}")
    except Exception as e:
        print(f"Error filling notice period: {e}")

def fill_standard_form_fields(page: Page):
    """Fill standard form fields (name, location, etc.)"""
    try:
        from config import config
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        # Name fields
        name_selectors = [
            f"{modal_selector} input[name*='name' i]",
            f"{modal_selector} input[id*='name' i]",
            f"{modal_selector} input[placeholder*='name' i]",
        ]
        
        for selector in name_selectors:
            try:
                fields = page.query_selector_all(selector)
                for field in fields:
                    if field.is_visible() and not field.input_value():
                        context = get_field_context(page, field).lower()
                        # Avoid filling company name or other name fields
                        if 'company' not in context and 'organization' not in context:
                            field.fill(config.FULL_NAME)
                            time.sleep(0.3)
                            print("✓ Filled name")
                            break
            except Exception:
                continue
        
        # Location fields
        location_selectors = [
            f"{modal_selector} input[name*='location' i]",
            f"{modal_selector} input[id*='location' i]",
            f"{modal_selector} input[placeholder*='location' i]",
            f"{modal_selector} input[name*='city' i]",
        ]
        
        for selector in location_selectors:
            try:
                fields = page.query_selector_all(selector)
                for field in fields:
                    if field.is_visible() and not field.input_value():
                        field.fill(config.LOCATION)
                        time.sleep(0.3)
                        print("✓ Filled location")
                        break
            except Exception:
                continue
                
    except Exception as e:
        print(f"Error filling standard fields: {e}")

def fill_contact_fields(page: Page):
    """Fill email and phone fields"""
    try:
        from config import config
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        # Email fields
        email_selectors = [
            f"{modal_selector} input[type='email']",
            f"{modal_selector} input[name*='email' i]",
            f"{modal_selector} input[id*='email' i]",
        ]
        
        for selector in email_selectors:
            try:
                fields = page.query_selector_all(selector)
                for field in fields:
                    if field.is_visible() and not field.input_value():
                        field.fill(config.EMAIL)
                        time.sleep(0.3)
                        print("✓ Filled email")
                        break
            except Exception:
                continue

        # Phone fields
        phone_selectors = [
            f"{modal_selector} input[type='tel']",
            f"{modal_selector} input[name*='phone' i]",
            f"{modal_selector} input[id*='phone' i]",
        ]
        
        for selector in phone_selectors:
            try:
                fields = page.query_selector_all(selector)
                for field in fields:
                    if field.is_visible() and not field.input_value():
                        field.fill(config.PHONE)
                        time.sleep(0.3)
                        print("✓ Filled phone")
                        break
            except Exception:
                continue
                
    except Exception as e:
        print(f"Error filling contact fields: {e}")

def fill_all_dropdowns(page: Page):
    """
    Fill all dropdown/select fields inside the LinkedIn Easy Apply modal.
    Improvements:
    - Auto-select based on field context
    - If dropdown contains Yes/No → ALWAYS choose Yes
    - Default behavior picks first valid option
    """
    try:
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        selects = page.query_selector_all(f"{modal_selector} select")

        for select in selects:
            if not select.is_visible():
                continue

            try:
                # Skip already-filled selects
                current_value = select.evaluate("el => el.value")
                if current_value and current_value != "":
                    continue

                # Get dropdown options
                options = select.query_selector_all("option")
                option_texts = [o.inner_text().strip().lower() for o in options]

                # 1. YES/NO HANDLING (highest priority)
                if any(opt in option_texts for opt in ["yes", "no"]):
                    try:
                        select.select_option(label="Yes")
                        print("✓ Selected 'Yes' for Yes/No dropdown")
                        continue
                    except:
                        pass

                # Extract field context
                try:
                    context = get_field_context(page, select).lower()
                except:
                    context = ""

                # 2. NOTICE PERIOD
                if any(k in context for k in ["notice", "availability"]):
                    try:
                        select.select_option(label="30 days")
                        print("✓ Selected notice period = 30 days")
                    except:
                        select.select_option(index=1)
                    continue

                # 3. EXPERIENCE
                if any(k in context for k in ["experience", "years"]):
                    try:
                        select.select_option(label="2")
                        print("✓ Selected experience = 2 years")
                    except:
                        select.select_option(index=1)
                    continue

                # 4. WORK AUTHORIZATION / VISA
                if any(k in context for k in ["authorization", "work permit", "visa"]):
                    try:
                        select.select_option(label="Yes")
                        print("✓ Selected work authorization = Yes")
                    except:
                        select.select_option(index=1)
                    continue

                # 5. DEFAULT → pick first non-empty
                if len(options) > 1:
                    try:
                        select.select_option(index=1)
                        print("✓ Selected default dropdown option")
                    except:
                        pass

                time.sleep(0.3)

            except Exception as e:
                print(f"Error filling dropdown: {e}")
                continue

    except Exception as e:
        print(f"Error filling dropdowns: {e}")

def fill_radio_and_checkbox_fields(page: Page):
    """Fill radio buttons and checkboxes"""
    try:
        from config import config
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        # Handle radio buttons
        radio_groups = {}
        radios = page.query_selector_all(f"{modal_selector} input[type='radio']")
        
        for radio in radios:
            if not radio.is_visible():
                continue
            
            name = radio.get_attribute('name')
            if not name:
                continue
            
            # Store first radio of each group
            if name not in radio_groups:
                radio_groups[name] = []
            radio_groups[name].append(radio)
        
        # Select appropriate radio button for each group
        for group_name, radios in radio_groups.items():
            try:
                # Check if any is already selected
                is_selected = any(radio.is_checked() for radio in radios)
                if is_selected:
                    continue
                
                # Get context for the group
                context = get_field_context(page, radios[0]).lower()
                
                # Try to find "Yes" option
                for radio in radios:
                    radio_context = get_field_context(page, radio).lower()
                    if 'yes' in radio_context:
                        radio.check()
                        time.sleep(0.2)
                        print(f"✓ Selected Yes radio button")
                        break
                else:
                    # Default: select first option
                    radios[0].check()
                    time.sleep(0.2)
                    print(f"✓ Selected radio button")
                    
            except Exception as e:
                print(f"Error with radio group: {e}")
                continue
        
        # Handle checkboxes (usually consent/agreement checkboxes)
        checkboxes = page.query_selector_all(f"{modal_selector} input[type='checkbox']")
        
        for checkbox in checkboxes:
            if not checkbox.is_visible():
                continue
            
            try:
                context = get_field_context(page, checkbox).lower()
                
                # Check boxes that are about consent, terms, etc.
                if any(keyword in context for keyword in ['agree', 'consent', 'terms', 'privacy', 'understand']):
                    if not checkbox.is_checked():
                        checkbox.check()
                        time.sleep(0.2)
                        print(f"✓ Checked agreement checkbox")
                
            except Exception as e:
                print(f"Error with checkbox: {e}")
                continue
                
    except Exception as e:
        print(f"Error filling radio/checkbox fields: {e}")

def fill_number_input_fields(page: Page):
    """Fill number input fields (for CTC, experience, etc.)"""
    try:
        from config import config
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        number_inputs = page.query_selector_all(f"{modal_selector} input[type='number']")
        
        for field in number_inputs:
            if not field.is_visible():
                continue
            
            try:
                # Skip if already filled
                current_value = field.input_value()
                if current_value and current_value.strip():
                    continue
                
                context = get_field_context(page, field).lower()
                
                # Determine what to fill based on context
                if any(keyword in context for keyword in ['ctc', 'salary', 'compensation']):
                    if 'current' in context:
                        value = config.ANSWERS.get("current_ctc", "6.0")
                    else:
                        value = config.ANSWERS.get("expected_ctc", "7.0")
                elif any(keyword in context for keyword in ['experience', 'years']):
                    value = config.ANSWERS.get("total_experience_years", "2")
                elif 'notice' in context:
                    value = "30"
                else:
                    value = "2"  # Default
                
                field.fill(str(value))
                time.sleep(0.3)
                print(f"✓ Filled number input: {value}")
                
            except Exception as e:
                print(f"Error filling number input: {e}")
                continue
                
    except Exception as e:
        print(f"Error filling number inputs: {e}")

def fill_textarea_fields(page: Page):
    """Fill textarea fields"""
    try:
        from config import config
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        textareas = page.query_selector_all(f"{modal_selector} textarea")
        
        for textarea in textareas:
            if not textarea.is_visible():
                continue
            
            try:
                # Skip if already filled
                current_value = textarea.input_value()
                if current_value and current_value.strip():
                    continue
                
                context = get_field_context(page, textarea).lower()
                
                # Provide appropriate text based on context
                if any(keyword in context for keyword in ['cover letter', 'introduction', 'why you']):
                    text = "I am interested in this position and believe my skills and experience make me a strong candidate."
                elif 'additional' in context or 'comments' in context:
                    text = "Thank you for considering my application."
                else:
                    text = "N/A"
                
                textarea.fill(text)
                time.sleep(0.3)
                print(f"✓ Filled textarea")
                
            except Exception as e:
                print(f"Error filling textarea: {e}")
                continue
                
    except Exception as e:
        print(f"Error filling textareas: {e}")
        
def fill_contact_fields(page: Page):
    """Fill email and phone fields"""
    # Email fields
    email_selectors = [
        "input[type='email']",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[placeholder*='email' i]",
        "input[aria-label*='email' i]",
    ]
    
    for selector in email_selectors:
        try:
            fields = page.query_selector_all(selector)
            for field in fields:
                if field.is_visible() and not field.input_value():
                    field.fill(config.EMAIL)
                    print("✓ Filled email")
                    break
        except Exception:
            continue

    # Phone fields
    phone_selectors = [
        "input[type='tel']",
        "input[name*='phone' i]",
        "input[id*='phone' i]",
        "input[placeholder*='phone' i]",
        "input[aria-label*='phone' i]",
    ]
    
    for selector in phone_selectors:
        try:
            fields = page.query_selector_all(selector)
            for field in fields:
                if field.is_visible() and not field.input_value():
                    field.fill(config.PHONE)
                    print("✓ Filled phone")
                    break
        except Exception:
            continue

def fill_standard_form_fields(page: Page):
    """Fill standard form fields"""
    # Name field
    name_selectors = [
        "input[name*='name' i]",
        "input[id*='name' i]",
        "input[placeholder*='name' i]",
        "input[name='firstName']",
        "input[name='lastName']",
    ]
    
    for selector in name_selectors:
        try:
            fields = page.query_selector_all(selector)
            for field in fields:
                if field.is_visible() and not field.input_value():
                    name = getattr(config, 'FULL_NAME', 'Your Name')
                    field.fill(name)
                    print("✓ Filled name")
                    break
        except Exception:
            continue
