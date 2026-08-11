import time
import re
from typing import List, Optional
from playwright.sync_api import Page
# --- Import the AIFormFiller instance ---
from ai_form_filler import ai_filler


class IndeedAutofill:
    """Indeed-specific autofill logic"""
    
    def __init__(self, config):
        self.config = config
    
    def get_field_label_and_context(self, page: Page, field) -> str:
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
    
    def analyze_field_type(self, context: str, field_name: str) -> str:
        """Determine what type of information a field is asking for"""
        # This function can remain for potential logging or fallback purposes,
        # but the AI will handle the logic internally.
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
    
    def fill_field_intelligently(self, page: Page, field, field_type: str, context: str) -> bool:
        """
        Fill a field using the AIFormFiller.
        The previous manual logic is replaced by the AI.
        """
        try:
            tag_name = field.evaluate("el => el.tagName.toLowerCase()")
            input_type = field.get_attribute('type') or ''

            # Skip if already filled
            if self._is_field_already_filled(field, tag_name, input_type):
                return False

            # Determine options for dropdowns and radio buttons
            options = None
            if tag_name == 'select':
                options = [opt.get_attribute('value') or opt.inner_text() for opt in field.query_selector_all('option')]
            elif input_type == 'radio':
                 field_name = field.get_attribute('name')
                 if field_name:
                     radio_group = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
                     options = []
                     for radio in radio_group:
                         radio_id = radio.get_attribute('id') or ''
                         if radio_id:
                             label = page.query_selector(f"label[for='{radio_id}']")
                             if label:
                                 options.append(label.inner_text().strip())
                         else:
                             # Fallback to value attribute if no label
                             options.append(radio.get_attribute('value') or '')


            # Use AIFormFiller to generate the answer
            ai_answer = ai_filler.generate_answer(
                field_context=context,
                field_type=tag_name, # Pass the HTML tag name (e.g., input, select, textarea)
                options=options
            )

            if ai_answer is None:
                print(f" ⚠  AI failed to generate an answer for field: {context[:50]}...") # Log short context
                return False

            print(f" 🤖  Filling field with AI answer: '{ai_answer}'")

            # Fill the field based on its tag/type
            if tag_name == 'select':
                try:
                    field.select_option(label=ai_answer)
                    print(f"   Selected option by label: {ai_answer}")
                    return True
                except Exception:
                    try:
                        field.select_option(value=ai_answer)
                        print(f"   Selected option by value: {ai_answer}")
                        return True
                    except Exception:
                        print(f"   ⚠ Could not select option directly for '{ai_answer}'. Trying helper fallback...")
                        selected = self._select_dropdown_option(
                            field,
                            [ai_answer, str(self.config.NOTICE_PERIOD), getattr(self.config, 'CITY', 'Amritsar'), "30", "1 Month", "15 Days", "Yes", "No"]
                        )
                        return selected

            elif input_type in ['checkbox', 'radio']:
                 if input_type == 'checkbox':
                      ans_lower = (ai_answer or '').lower()
                      context_lower = (context or '').lower()
                      should_check = any(w in ans_lower for w in ['yes', 'true', 'on', '1', 'agree', 'accept'])
                      if any(kw in context_lower for kw in ['privacy', 'terms', 'declare', 'understand', 'consent', 'agree', 'policy', 'notice']):
                          should_check = True

                      is_checked = field.is_checked()
                      if should_check and not is_checked:
                          field_id = field.get_attribute('id')
                          clicked = False
                          if field_id:
                              lbl = page.query_selector(f"label[for='{field_id}']")
                              if lbl:
                                  try:
                                      lbl.click()
                                      clicked = True
                                      print(f"   Clicked checkbox label: {field_id}")
                                  except Exception:
                                      pass
                          if not clicked:
                              try:
                                  field.click(force=True)
                              except Exception:
                                  field.check(force=True)
                              print(f"   Checked checkbox via click.")
                          time.sleep(0.3)
                          return True
                      elif not should_check and is_checked:
                          field.uncheck(force=True)
                          print(f"   Unchecked checkbox.")
                          return True
                      else:
                          print(f"   Checkbox already in desired state.")
                          return True
                 elif input_type == 'radio':
                     # Find the radio button matching the AI answer and select it
                     field_name = field.get_attribute('name')
                     if field_name:
                         success = self._select_radio_in_group(page, field, [ai_answer]) # Reuse helper if it works for partial matches
                         if not success:
                              print(f"   ⚠  AI suggested '{ai_answer}', but no matching radio button found in group '{field_name}'. Options were likely: {options}")
                         else:
                             print(f"   Selected radio option: {ai_answer}")
                         return success
                     else:
                         print("   ⚠  Radio button has no name, cannot determine group.")
                         return False
            else: # Text inputs, textareas
                field.fill(ai_answer)
                print(f"   Filled text field with: {ai_answer}")
                return True

        except Exception as e:
            print(f"⚠ Error filling field using AI: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            return False

    # Keep the helper methods as they might be useful for radio buttons or other edge cases
    def _is_field_already_filled(self, field, tag_name: str, input_type: str) -> bool:
        """Check if field is already filled"""
        try:
            if tag_name in ['input', 'textarea'] and input_type not in ['checkbox', 'radio']:
                current_value = field.input_value()
                return bool(current_value and current_value.strip())
            elif tag_name == 'select':
                current_value = field.evaluate("el => el.value")
                return bool(current_value)
            elif input_type == 'checkbox':
                return field.is_checked()
            elif input_type == 'radio':
                field_name = field.get_attribute('name')
                if field_name:
                    radios = field.page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
                    for r in radios:
                        if r.is_checked():
                            return True
                    return False
                return field.is_checked()
            return False
        except Exception:
            return False

    def _select_dropdown_option(self, field, preferred_values: List[str]) -> bool:
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
                        print(f"   Selected dropdown option via helper: {option.inner_text()}")
                        return True

            # Second pass: partial matches
            for option in options:
                value = (option.get_attribute('value') or '').lower()
                text = option.inner_text().lower()

                for pref in preferred_values:
                    pref_lower = str(pref).lower()
                    if pref_lower in value or pref_lower in text:
                        field.select_option(value=option.get_attribute('value'))
                        print(f"   Selected dropdown option via helper (partial match): {option.inner_text()}")
                        return True

            print(f"   Dropdown helper could not find match for: {preferred_values}")
            return False
        except Exception as e:
            print(f"⚠ Error selecting dropdown: {e}")
            return False

    def _select_radio_in_group(self, page: Page, field, preferred_values: List[str]) -> bool:
        """Select radio button in group matching preferred values"""
        try:
            field_name = field.get_attribute('name')
            if not field_name:
                return False

            radio_buttons = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')

            # First pass: exact label / value matches
            for radio in radio_buttons:
                value = (radio.get_attribute('value') or '').lower()
                radio_id = radio.get_attribute('id') or ''

                label_element = None
                label_text = ''
                if radio_id:
                    label_element = page.query_selector(f"label[for='{radio_id}']")
                    if label_element:
                        label_text = label_element.inner_text().strip().lower()

                for pref in preferred_values:
                    pref_lower = str(pref).lower().strip()
                    if pref_lower == value or pref_lower == label_text:
                        if label_element:
                            label_element.click()
                        else:
                            radio.click()
                        print(f"   Clicked radio option: {label_text or value}")
                        time.sleep(0.3)
                        return True

            # Second pass: partial matches
            for radio in radio_buttons:
                value = (radio.get_attribute('value') or '').lower()
                radio_id = radio.get_attribute('id') or ''

                label_element = None
                label_text = ''
                if radio_id:
                    label_element = page.query_selector(f"label[for='{radio_id}']")
                    if label_element:
                        label_text = label_element.inner_text().strip().lower()

                for pref in preferred_values:
                    pref_lower = str(pref).lower().strip()
                    if pref_lower in value or pref_lower in label_text or label_text in pref_lower:
                        if label_element:
                            label_element.click()
                        else:
                            radio.click()
                        print(f"   Clicked radio option (partial match): {label_text or value}")
                        time.sleep(0.3)
                        return True

            # Fallback pass: if preferred value is 'Yes' or 'No', pick the first radio option if no match
            if radio_buttons:
                lbl = page.query_selector(f"label[for='{radio_buttons[0].get_attribute('id')}']")
                if lbl:
                    lbl.click()
                else:
                    radio_buttons[0].click()
                print(f"   Fallback radio option clicked for group '{field_name}'")
                time.sleep(0.3)
                return True

            return False
        except Exception as e:
            print(f"⚠ Error selecting radio: {e}")
            return False
