# BaseAutofill.py - FIXED RADIO BUTTON HANDLING
import time
import random
from .field_detection import FieldDetector
from playwright.sync_api import Page
from ai_form_filler import ai_filler
from typing import List, Optional

class BaseAutofill:
    """Enhanced autofill with better LinkedIn dropdown support"""
    
    def __init__(self, config):
        self.config = config
        self.field_detector = FieldDetector()
    
    def autofill_standard_form(self, page):
        """Enhanced autofill for LinkedIn Easy Apply using AI"""
        try:
            print("Starting AI-driven form autofill...")
            
            # Handle all fields using AI
            self._fill_all_fields_with_ai(page)
            
            # Small delay for validation
            time.sleep(0.5)
            
            print("AI-driven form autofill completed")
            
        except Exception as e:
            print(f"Error in AI autofill: {e}")
            import traceback
            traceback.print_exc()
    
    def _fill_all_fields_with_ai(self, page):
        """Fill all form fields using the AIFormFiller"""
        filled_count = 0
        try:
            print("📝 Analyzing and filling form fields with AI...")
            
            # IMPORTANT: Also look for custom dropdowns (LinkedIn uses these)
            form_elements = page.query_selector_all("""
                div.jobs-easy-apply-modal input:not([type='hidden']):not([type='submit']),
                div.jobs-easy-apply-modal select,
                div.jobs-easy-apply-modal textarea,
                div[role='dialog'] input:not([type='hidden']):not([type='submit']),
                div[role='dialog'] select,
                div[role='dialog'] textarea
            """)
            
            print(f"Found {len(form_elements)} form elements to process")
            
            processed_radio_groups = set()
            
            for i, field in enumerate(form_elements):
                try:
                    if not field.is_visible():
                        continue
                    
                    # Detect field type
                    field_type_info = self._detect_field_type(page, field)
                    field_type = field_type_info['type']
                    
                    print(f"\n📋 Processing field #{i+1}:")
                    print(f"  Type: {field_type}")
                    
                    # For radio buttons, process only once per group
                    if field_type == 'radio':
                        field_name = field.get_attribute('name')
                        if not field_name:
                            print(f"  ⚠ Radio button has no name, skipping")
                            continue
                        if field_name in processed_radio_groups:
                            print(f"  ⏭ Radio group '{field_name}' already processed")
                            continue
                        processed_radio_groups.add(field_name)
                        print(f"  🔘 Processing radio group: '{field_name}'")
                    
                    # Skip if already filled (except custom dropdowns which we can't easily check)
                    if field_type not in ['custom-dropdown', 'select']:
                        if self._is_field_already_filled(field, field_type_info):
                            print(f"  ⏭ Field already filled, skipping")
                            continue
                    
                    # Get comprehensive context
                    context = self.field_detector.get_field_context(page, field)
                    
                    if not context:
                        print(f"  ⚠ Field has no context, skipping")
                        continue
                    
                    print(f"  Context: {context[:100]}...")
                    
                    # Determine options for dropdowns and radio buttons
                    options = None
                    if field_type in ['select', 'custom-dropdown']:
                        options = self._get_dropdown_options(page, field, field_type_info)
                    elif field_type == 'radio':
                        field_name = field.get_attribute('name')
                        if field_name:
                            options = self._get_radio_options(page, field_name)
                    
                    if options:
                        print(f"  Options ({len(options)}): {options}")
                    
                    # Use AIFormFiller to generate the answer
                    ai_answer = ai_filler.generate_answer(
                        field_context=context,
                        field_type=field_type if field_type != 'custom-dropdown' else 'select',
                        options=options
                    )

                    if not ai_answer:
                        print(f"  ⚠ AI returned no answer, skipping")
                        continue

                    print(f"  🤖 AI Answer: '{ai_answer}'")

                    # Fill the field based on its type
                    success = False
                    
                    if field_type == 'select':
                        success = self._fill_standard_select(field, ai_answer, options)
                    
                    elif field_type == 'custom-dropdown':
                        success = self._fill_linkedin_custom_dropdown(page, field, ai_answer, options, context)
                        
                    elif field_type == 'checkbox':
                        success = self._fill_checkbox(field, ai_answer)
                        
                    elif field_type == 'radio':
                        field_name = field.get_attribute('name')
                        if field_name:
                            success = self._fill_radio_group(page, field_name, ai_answer, options)
                        
                    elif field_type == 'number':
                        success = self._fill_number(field, ai_answer)
                        
                    else:  # Text inputs, textareas
                        success = self._fill_text(field, ai_answer)
                    
                    if success:
                        filled_count += 1
                        print(f"  ✅ Successfully filled field #{i+1}")
                        time.sleep(random.uniform(0.3, 0.8))
                    else:
                        print(f"  ❌ Failed to fill field #{i+1}")

                except Exception as e:
                    print(f"  ⚠ Error processing field #{i+1}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"\n✅ Successfully filled {filled_count} fields using AI")
            return filled_count

        except Exception as e:
            print(f"⚠ Error in AI-driven form filling: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _detect_field_type(self, page: Page, field) -> dict:
        """Detect if field is standard input or custom dropdown"""
        try:
            tag_name = field.evaluate("el => el.tagName.toLowerCase()")
            
            if tag_name == 'input':
                input_type = field.get_attribute('type') or 'text'
                return {'type': input_type, 'tag': tag_name}
            
            if tag_name == 'select':
                return {'type': 'select', 'tag': tag_name}
            
            if tag_name == 'textarea':
                return {'type': 'textarea', 'tag': tag_name}
            
            # Check for custom dropdown indicators
            role = field.get_attribute('role')
            aria_expanded = field.get_attribute('aria-expanded')
            classes = field.get_attribute('class') or ''
            
            # LinkedIn custom dropdown patterns
            custom_dropdown_indicators = [
                'data-test-text-selectable-option' in field.evaluate("el => el.outerHTML"),
                'fb-dash-form-element__dropdown' in classes,
                'artdeco-dropdown' in classes,
                role == 'button' and aria_expanded is not None,
                'jobs-easy-apply' in classes and ('select' in classes.lower() or 'dropdown' in classes.lower())
            ]
            
            if any(custom_dropdown_indicators):
                return {'type': 'custom-dropdown', 'tag': tag_name}
            
            return {'type': 'unknown', 'tag': tag_name}
            
        except Exception as e:
            print(f"    ⚠ Error detecting field type: {e}")
            return {'type': 'unknown', 'tag': 'unknown'}
    
    def _get_dropdown_options(self, page: Page, field, field_type_info: dict) -> List[str]:
        """Get options from standard or custom dropdown"""
        if field_type_info['type'] == 'select':
            return self._get_select_options(field)
        elif field_type_info['type'] == 'custom-dropdown':
            return self._get_custom_dropdown_options(page, field)
        return []
    
    def _get_select_options(self, field) -> List[str]:
        """Extract options from standard select dropdown"""
        try:
            option_elements = field.query_selector_all('option')
            options = []
            
            for opt in option_elements:
                text = opt.inner_text().strip()
                value = opt.get_attribute('value') or ''
                
                # Skip placeholder/empty options
                if not text or text.lower() in ['select', 'choose', 'select one', '--', 'please select', '']:
                    continue
                
                if not value or value == '':
                    continue
                
                options.append(text)
            
            return options
        except Exception as e:
            print(f"    ⚠ Error getting select options: {e}")
            return []
    
    def _get_custom_dropdown_options(self, page: Page, field) -> List[str]:
        """Extract options from LinkedIn custom dropdown by opening it"""
        try:
            print(f"    🔍 Opening custom dropdown to get options...")
            
            # Click to open dropdown
            field.click(timeout=2000)
            time.sleep(0.5)
            
            # Look for options with multiple selectors
            option_selectors = [
                "[role='option']",
                "[role='listbox'] li",
                "div.artdeco-dropdown__item",
                "li.artdeco-dropdown__item",
                "div[data-test-text-selectable-option__option]",
                "button[role='option']",
                "div.fb-dash-form-element__dropdown-option",
                "ul.artdeco-dropdown__content-list li",
            ]
            
            options = []
            for selector in option_selectors:
                try:
                    option_elements = page.query_selector_all(selector)
                    if option_elements:
                        for opt in option_elements:
                            if opt.is_visible():
                                text = opt.inner_text().strip()
                                if text and text not in options:
                                    options.append(text)
                        
                        if options:
                            print(f"    ✓ Found {len(options)} options")
                            # Close dropdown by clicking outside or pressing Escape
                            page.keyboard.press('Escape')
                            time.sleep(0.3)
                            return options
                except:
                    continue
            
            # Close dropdown even if no options found
            page.keyboard.press('Escape')
            time.sleep(0.3)
            
            return options
            
        except Exception as e:
            print(f"    ⚠ Error getting custom dropdown options: {e}")
            return []
    
    def _fill_standard_select(self, field, value: str, options: List[str]) -> bool:
        """Fill standard HTML select element"""
        try:
            if not value:
                return False
            
            print(f"    🎯 Filling standard select: '{value}'")
            
            # Try label match
            try:
                field.select_option(label=value, timeout=2000)
                time.sleep(0.2)
                if self._verify_select_value(field, value):
                    print(f"    ✅ Selected by label")
                    return True
            except:
                pass
            
            # Try value match
            try:
                field.select_option(value=value, timeout=2000)
                time.sleep(0.2)
                if self._verify_select_value(field, value):
                    print(f"    ✅ Selected by value")
                    return True
            except:
                pass
            
            # JavaScript fallback
            try:
                result = field.evaluate(f"""
                    (select, targetValue) => {{
                        const targetLower = targetValue.toLowerCase().trim();
                        
                        for (let i = 0; i < select.options.length; i++) {{
                            const opt = select.options[i];
                            const text = (opt.text || '').toLowerCase().trim();
                            const value = (opt.value || '').toLowerCase().trim();
                            
                            if (text === targetLower || value === targetLower || 
                                text.includes(targetLower) || targetLower.includes(text)) {{
                                select.selectedIndex = i;
                                select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                select.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """, value)
                
                if result:
                    print(f"    ✅ Selected via JavaScript")
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"    ❌ Error filling select: {e}")
            return False
    
    def _fill_linkedin_custom_dropdown(self, page: Page, field, value: str, options: List[str], context: str) -> bool:
        """
        Fill LinkedIn custom dropdown (React-based)
        IMPROVED with better option matching
        """
        try:
            if not value:
                return False
            
            print(f"    🎨 Filling LinkedIn custom dropdown: '{value}'")
            
            # Step 1: Click to open dropdown
            try:
                field.click(timeout=2000)
                print(f"    → Opened dropdown")
                time.sleep(0.7)  # Longer wait for animation
            except Exception as e:
                print(f"    ⚠ Failed to open dropdown: {e}")
                return False
            
            # Step 2: Try to find and click the matching option
            value_lower = value.lower().strip()
            
            # Multiple selector strategies for LinkedIn
            option_selector_sets = [
                # Set 1: ARIA roles (most common)
                ["[role='option']"],
                
                # Set 2: LinkedIn specific
                ["div.artdeco-dropdown__item", "li.artdeco-dropdown__item"],
                
                # Set 3: Data attributes
                ["[data-test-text-selectable-option__option]", "button[role='option']"],
                
                # Set 4: Class-based
                ["div[class*='dropdown-option']", "li[class*='dropdown-option']"],
                
                # Set 5: Generic list items
                ["ul.artdeco-dropdown__content-list li", "div[role='listbox'] > div"]
            ]
            
            for selector_set in option_selector_sets:
                for selector in selector_set:
                    try:
                        # Wait for options to be visible
                        page.wait_for_selector(selector, timeout=2000, state='visible')
                        option_elements = page.query_selector_all(selector)
                        
                        if not option_elements:
                            continue
                        
                        print(f"    → Found {len(option_elements)} options with: {selector}")
                        
                        # Try to match and click
                        best_match = None
                        best_score = 0
                        
                        for opt in option_elements:
                            try:
                                if not opt.is_visible():
                                    continue
                                
                                opt_text = opt.inner_text().strip()
                                if not opt_text:
                                    continue
                                
                                opt_lower = opt_text.lower()
                                
                                # Exact match (best)
                                if opt_lower == value_lower:
                                    opt.click()
                                    time.sleep(0.3)
                                    print(f"    ✅ Clicked exact match: '{opt_text}'")
                                    return True
                                
                                # Calculate match score
                                score = 0
                                if value_lower in opt_lower:
                                    score = len(value_lower) / len(opt_lower)
                                elif opt_lower in value_lower:
                                    score = len(opt_lower) / len(value_lower)
                                else:
                                    # Word overlap
                                    value_words = set(value_lower.split())
                                    opt_words = set(opt_lower.split())
                                    if opt_words:
                                        overlap = len(value_words & opt_words)
                                        score = overlap / len(opt_words)
                                
                                if score > best_score:
                                    best_score = score
                                    best_match = (opt, opt_text)
                                
                            except:
                                continue
                        
                        # Click best match if good enough
                        if best_match and best_score >= 0.5:
                            opt, opt_text = best_match
                            opt.click()
                            time.sleep(0.3)
                            print(f"    ✅ Clicked best match ({best_score:.0%}): '{opt_text}'")
                            return True
                        
                    except Exception as e:
                        continue
            
            # Step 3: If clicking didn't work, try typing (for searchable dropdowns)
            try:
                print(f"    → Trying type approach")
                
                # Find input within dropdown or use the field itself
                dropdown_input = page.query_selector("input[role='combobox']") or field
                
                dropdown_input.fill('')
                time.sleep(0.2)
                dropdown_input.type(value, delay=50)
                time.sleep(0.5)
                
                # Press Enter to select
                page.keyboard.press('Enter')
                time.sleep(0.3)
                
                print(f"    ✅ Typed and confirmed")
                return True
                
            except Exception as e:
                print(f"    ⚠ Type approach failed: {e}")
            
            # Step 4: Close dropdown
            try:
                page.keyboard.press('Escape')
                time.sleep(0.2)
            except:
                pass
            
            print(f"    ❌ All strategies failed")
            return False
            
        except Exception as e:
            print(f"    ❌ Fatal error in custom dropdown: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _verify_select_value(self, field, expected_value: str) -> bool:
        """Verify that a select field has the expected value"""
        try:
            selected_text = field.evaluate("el => el.options[el.selectedIndex]?.text || ''")
            return selected_text.lower().strip() == expected_value.lower().strip()
        except:
            return False
    
    def _get_radio_options(self, page: Page, field_name: str) -> List[str]:
        """Extract options from radio button group - IMPROVED"""
        try:
            print(f"    🔍 Getting radio options for group: '{field_name}'")
            
            # Use JavaScript to get all radio labels properly - FIXED
            options = page.evaluate(f"""
                (fieldName) => {{
                    const radios = document.querySelectorAll('input[type="radio"][name="' + fieldName + '"]');
                    const options = [];
                    
                    radios.forEach(radio => {{
                        let labelText = '';
                        
                        // Strategy 1: Associated label via 'for' attribute
                        const radioId = radio.id;
                        if (radioId) {{
                            const label = document.querySelector('label[for="' + radioId + '"]');
                            if (label) {{
                                labelText = label.innerText.trim();
                            }}
                        }}
                        
                        // Strategy 2: Parent label
                        if (!labelText) {{
                            const parentLabel = radio.closest('label');
                            if (parentLabel) {{
                                // Clone and remove the input to get just label text
                                const clone = parentLabel.cloneNode(true);
                                const inputClone = clone.querySelector('input[type="radio"]');
                                if (inputClone) inputClone.remove();
                                labelText = clone.innerText.trim();
                            }}
                        }}
                        
                        // Strategy 3: Next sibling text
                        if (!labelText && radio.nextSibling) {{
                            labelText = radio.nextSibling.textContent?.trim() || '';
                        }}
                        
                        // Strategy 4: Parent container text
                        if (!labelText && radio.parentElement) {{
                            const parent = radio.parentElement;
                            const clone = parent.cloneNode(true);
                            const inputClone = clone.querySelector('input[type="radio"]');
                            if (inputClone) inputClone.remove();
                            labelText = clone.innerText.trim();
                        }}
                        
                        // Strategy 5: Use value as fallback
                        if (!labelText) {{
                            labelText = radio.value || '';
                        }}
                        
                        if (labelText && !options.includes(labelText)) {{
                            options.push(labelText);
                        }}
                    }});
                    
                    return options;
                }}
            """, field_name)
            
            print(f"    ✓ Found {len(options)} radio options: {options}")
            return options
            
        except Exception as e:
            print(f"    ⚠ Error getting radio options: {e}")
            return []
    
    def _fill_checkbox(self, field, value: str) -> bool:
        """Fill checkbox"""
        try:
            should_check = value.lower() in ['yes', 'true', 'on', '1']
            is_checked = field.is_checked()
            
            if should_check != is_checked:
                field.set_checked(should_check)
                print(f"    ✓ Set checkbox to {should_check}")
            return True
        except Exception as e:
            print(f"    ✗ Checkbox error: {e}")
            return False
    
    def _fill_radio_group(self, page: Page, field_name: str, value: str, options: List[str]) -> bool:
        """Fill radio button group - COMPLETELY REWRITTEN - FIXED MODAL CLOSE ISSUE"""
        try:
            print(f"    🔘 Filling radio group '{field_name}' with value: '{value}'")
            
            if not value:
                print(f"    ⚠ No value provided for radio group")
                return False
            
            value_lower = value.lower().strip()
            
            # Use JavaScript to find and click the matching radio - FIXED
            result = page.evaluate(f"""
                (fieldName, targetValue) => {{
                    const radios = document.querySelectorAll('input[type="radio"][name="' + fieldName + '"]');
                    const targetLower = targetValue.toLowerCase().trim();
                    
                    let bestMatch = null;
                    let bestScore = 0;
                    const results = [];
                    
                    radios.forEach(radio => {{
                        let labelText = '';
                        
                        // Get label text using multiple strategies
                        const radioId = radio.id;
                        if (radioId) {{
                            const label = document.querySelector('label[for="' + radioId + '"]');
                            if (label) labelText = label.innerText.trim();
                        }}
                        
                        if (!labelText) {{
                            const parentLabel = radio.closest('label');
                            if (parentLabel) {{
                                const clone = parentLabel.cloneNode(true);
                                const inputClone = clone.querySelector('input[type="radio"]');
                                if (inputClone) inputClone.remove();
                                labelText = clone.innerText.trim();
                            }}
                        }}
                        
                        if (!labelText && radio.parentElement) {{
                            const parent = radio.parentElement;
                            const clone = parent.cloneNode(true);
                            const inputClone = clone.querySelector('input[type="radio"]');
                            if (inputClone) inputClone.remove();
                            labelText = clone.innerText.trim();
                        }}
                        
                        if (!labelText) {{
                            labelText = radio.value || '';
                        }}
                        
                        const labelLower = labelText.toLowerCase().trim();
                        
                        results.push({{ radio: radio, labelText: labelText, labelLower: labelLower }});
                        
                        // Calculate match score
                        let score = 0;
                        
                        // Exact match (best)
                        if (labelLower === targetLower) {{
                            score = 1.0;
                        }}
                        // Contains match
                        else if (labelLower.includes(targetLower)) {{
                            score = 0.8;
                        }}
                        else if (targetLower.includes(labelLower)) {{
                            score = 0.7;
                        }}
                        // Word overlap
                        else {{
                            const labelWords = labelLower.split(/\s+/);
                            const targetWords = targetLower.split(/\s+/);
                            const overlap = labelWords.filter(w => targetWords.includes(w)).length;
                            if (targetWords.length > 0) {{
                                score = overlap / targetWords.length * 0.6;
                            }}
                        }}
                        
                        if (score > bestScore) {{
                            bestScore = score;
                            bestMatch = {{ radio: radio, labelText: labelText, score: score }};
                        }}
                    }});
                    
                    // If we have a good match, click it
                    if (bestMatch && bestMatch.score >= 0.5) {{
                        bestMatch.radio.checked = true;
                        bestMatch.radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        bestMatch.radio.dispatchEvent(new Event('click', {{ bubbles: true }}));
                        bestMatch.radio.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return {{
                            success: true,
                            matched: bestMatch.labelText,
                            score: bestMatch.score,
                            allOptions: results.map(r => r.labelText)
                        }};
                    }}
                    
                    return {{
                        success: false,
                        matched: null,
                        score: bestScore,
                        allOptions: results.map(r => r.labelText)
                    }};
                }}
            """, field_name, value)
            
            if result['success']:
                print(f"    ✅ Selected radio: '{result['matched']}' (score: {result['score']:.0%})")
                time.sleep(0.2)
                return True
            else:
                print(f"    ❌ No good match found")
                print(f"       AI wanted: '{value}'")
                print(f"       Available options: {result['allOptions']}")
                print(f"       Best score: {result['score']:.0%}")
                
                # Fallback: select first option
                if result['allOptions']:
                    print(f"    ⚠ Selecting first option as fallback: '{result['allOptions'][0]}'")
                    # Use Playwright's built-in method to avoid JS issues
                    first_radio = page.query_selector(f"input[type='radio'][name='{field_name}']:first-of-type")
                    if first_radio:
                        first_radio.click()
                        time.sleep(0.2)
                        return True
                return False
                
        except Exception as e:
            print(f"    ❌ Radio group error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _fill_number(self, field, value: str) -> bool:
        """Fill number field"""
        try:
            # Validate number
            float(value)
            field.fill(value)
            time.sleep(0.1)
            print(f"    ✓ Filled number: {value}")
            return True
        except Exception as e:
            print(f"    ✗ Number error: {e}")
            return False
    
    def _fill_text(self, field, value: str) -> bool:
        """Fill text field"""
        try:
            field.fill(value)
            print(f"    ✓ Filled text: {value[:50]}")
            return True
        except Exception as e:
            print(f"    ✗ Text error: {e}")
            return False
    
    def _is_field_already_filled(self, field, field_type_info: dict) -> bool:
        """Check if field is already filled"""
        try:
            field_type = field_type_info['type']
            
            if field_type in ['text', 'email', 'tel', 'number', 'textarea']:
                current = field.input_value()
                return bool(current and current.strip())
            elif field_type == 'select':
                current = field.evaluate("el => el.value")
                return bool(current and current != '')
            elif field_type in ['checkbox', 'radio']:
                return field.is_checked()
            
            return False
        except:
            return False