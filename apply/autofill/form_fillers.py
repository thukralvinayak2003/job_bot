import time
from typing import List

class FormFiller:
    """Fills different types of form fields"""
    
    def __init__(self, config, field_handler):
        self.config = config
        self.field_handler = field_handler
    
    def fill_text_fields(self, page, modal_selector: str):
        """Fill standard text fields (name, email, phone, location)"""
        field_mappings = {
            'name': {
                'selectors': [
                    f"{modal_selector} input[name*='name' i]",
                    f"{modal_selector} input[id*='name' i]",
                    f"{modal_selector} input[placeholder*='name' i]",
                ],
                'value': self.config.FULL_NAME,
                'exclude_keywords': ['company', 'organization']
            },
            'email': {
                'selectors': [
                    f"{modal_selector} input[type='email']",
                    f"{modal_selector} input[name*='email' i]",
                    f"{modal_selector} input[id*='email' i]",
                ],
                'value': self.config.EMAIL
            },
            'phone': {
                'selectors': [
                    f"{modal_selector} input[type='tel']",
                    f"{modal_selector} input[name*='phone' i]",
                    f"{modal_selector} input[id*='phone' i]",
                ],
                'value': self.config.PHONE
            },
            'location': {
                'selectors': [
                    f"{modal_selector} input[name*='location' i]",
                    f"{modal_selector} input[id*='location' i]",
                    f"{modal_selector} input[placeholder*='location' i]",
                    f"{modal_selector} input[name*='city' i]",
                ],
                'value': self.config.LOCATION
            }
        }
        
        for field_type, mapping in field_mappings.items():
            self._fill_field_by_selectors(page, mapping['selectors'], 
                                         mapping['value'], 
                                         mapping.get('exclude_keywords', []))
    
    def fill_dropdowns(self, page, modal_selector: str, field_detector):
        """Fill all dropdown/select fields"""
        selects = page.query_selector_all(f"{modal_selector} select")
        
        for select in selects:
            if not select.is_visible():
                continue
            
            try:
                # Skip already-filled selects
                current_value = select.evaluate("el => el.value")
                if current_value and current_value != "":
                    continue
                
                # Get context and options
                context = field_detector.get_field_context(page, select).lower()
                options = select.query_selector_all("option")
                option_texts = [o.inner_text().strip().lower() for o in options]
                
                # Handle based on context
                if self._handle_special_dropdowns(select, context, option_texts):
                    continue
                
                # Default: pick first non-empty option
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
    
    def fill_radio_checkboxes(self, page, modal_selector: str, field_detector):
        """Fill radio buttons and checkboxes"""
        self._fill_radio_buttons(page, modal_selector, field_detector)
        self._fill_checkboxes(page, modal_selector, field_detector)
    
    def _fill_field_by_selectors(self, page, selectors: List[str], value: str, 
                                exclude_keywords: List[str] = []):
        """Fill field by trying multiple selectors"""
        for selector in selectors:
            try:
                fields = page.query_selector_all(selector)
                for field in fields:
                    if field.is_visible() and not field.input_value():
                        # Check if field should be excluded
                        context = field.evaluate("""
                            el => {
                                let text = '';
                                if (el.labels) {
                                    for (let label of el.labels) {
                                        text += label.textContent + ' ';
                                    }
                                }
                                return text.toLowerCase();
                            }
                        """) or ""
                        
                        should_exclude = any(keyword in context for keyword in exclude_keywords)
                        if not should_exclude:
                            field.fill(value)
                            time.sleep(0.3)
                            print(f"✓ Filled {selector.split('[')[0]}")
                            return
            except:
                continue
    
    def _handle_special_dropdowns(self, select, context: str, option_texts: List[str]) -> bool:
        """Handle special dropdown cases"""
        # Yes/No handling
        if any(opt in option_texts for opt in ["yes", "no"]):
            try:
                select.select_option(label="Yes")
                print("✓ Selected 'Yes' for Yes/No dropdown")
                return True
            except:
                pass
        
        # Notice period
        if any(k in context for k in ["notice", "availability"]):
            try:
                select.select_option(label="30 days")
                print("✓ Selected notice period = 30 days")
                return True
            except:
                pass
        
        # Experience
        if any(k in context for k in ["experience", "years"]):
            try:
                select.select_option(label="2")
                print("✓ Selected experience = 2 years")
                return True
            except:
                pass
        
        # Work authorization
        if any(k in context for k in ["authorization", "work permit", "visa"]):
            try:
                select.select_option(label="Yes")
                print("✓ Selected work authorization = Yes")
                return True
            except:
                pass
        
        return False
    
    def _fill_radio_buttons(self, page, modal_selector: str, field_detector):
        """Fill radio button groups"""
        radio_groups = {}
        radios = page.query_selector_all(f"{modal_selector} input[type='radio']")
        
        for radio in radios:
            if not radio.is_visible():
                continue
            
            name = radio.get_attribute('name')
            if not name:
                continue
            
            if name not in radio_groups:
                radio_groups[name] = []
            radio_groups[name].append(radio)
        
        # Process each radio group
        for group_name, radios in radio_groups.items():
            try:
                if any(radio.is_checked() for radio in radios):
                    continue
                
                # Try to select "Yes" if available
                for radio in radios:
                    radio_context = field_detector.get_field_context(page, radio).lower()
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
    
    def _fill_checkboxes(self, page, modal_selector: str, field_detector):
        """Fill checkboxes (consent/agreement)"""
        checkboxes = page.query_selector_all(f"{modal_selector} input[type='checkbox']")
        
        for checkbox in checkboxes:
            if not checkbox.is_visible():
                continue
            
            try:
                if checkbox.is_checked():
                    continue
                
                context = field_detector.get_field_context(page, checkbox).lower()
                consent_keywords = ['agree', 'consent', 'terms', 'privacy', 'understand']
                
                if any(keyword in context for keyword in consent_keywords):
                    checkbox.check()
                    time.sleep(0.2)
                    print(f"✓ Checked agreement checkbox")
                    
            except Exception as e:
                print(f"Error with checkbox: {e}")
                continue