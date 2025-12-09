import time
from .field_detection import FieldDetector
from .field_handlers import FieldHandler
from .form_fillers import FormFiller

class BaseAutofill:
    """Base autofill class for LinkedIn Easy Apply"""
    
    def __init__(self, config):
        self.config = config
        self.field_detector = FieldDetector()
        self.field_handler = FieldHandler(config)
        self.form_filler = FormFiller(config, self.field_handler)
    
    def autofill_standard_form(self, page):
        """Enhanced autofill for LinkedIn Easy Apply"""
        try:
            print("Starting form autofill...")
            
            # Handle LinkedIn-specific fields
            self._fill_linkedin_specific_fields(page)
            
            # Handle standard form fields
            self._fill_standard_fields(page)
            
            # Small delay for validation
            time.sleep(0.5)
            
            print("Form autofill completed")
            
        except Exception as e:
            print(f"Error in autofill: {e}")
    
    def _fill_linkedin_specific_fields(self, page):
        """Handle LinkedIn-specific field patterns"""
        try:
            modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
            all_inputs = page.query_selector_all(
                f"{modal_selector} input, {modal_selector} textarea, {modal_selector} select"
            )
            
            for field in all_inputs:
                if not field.is_visible():
                    continue
                
                try:
                    # Analyze field
                    tag_name, field_type = self.field_detector.analyze_field_type(field)
                    
                    # Skip if already filled
                    if self._is_field_already_filled(field, tag_name, field_type):
                        continue
                    
                    # Get context and handle field
                    context_text = self.field_detector.get_field_context(page, field).lower()
                    self._handle_field_by_context(field, context_text, tag_name)
                    
                except Exception as e:
                    print(f"Error processing field: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in LinkedIn specific fields: {e}")
    
    def _fill_standard_fields(self, page):
        """Fill standard form fields"""
        modal_selector = "div.jobs-easy-apply-modal, div[role='dialog']"
        
        # Fill text fields
        self.form_filler.fill_text_fields(page, modal_selector)
        
        # Fill dropdowns
        self.form_filler.fill_dropdowns(page, modal_selector, self.field_detector)
        
        # Fill radio buttons and checkboxes
        self.form_filler.fill_radio_checkboxes(page, modal_selector, self.field_detector)
        
        # Fill number inputs and textareas
        self._fill_number_inputs(page, modal_selector)
        self._fill_textareas(page, modal_selector)
    
    def _is_field_already_filled(self, field, tag_name: str, field_type: str) -> bool:
        """Check if field is already filled"""
        try:
            if tag_name == 'input' and field_type not in ['checkbox', 'radio']:
                current_value = field.input_value()
                return bool(current_value and current_value.strip())
            elif tag_name == 'select':
                current_value = field.evaluate("el => el.value")
                return bool(current_value and current_value != "")
            return False
        except:
            return False
    
    def _handle_field_by_context(self, field, context_text: str, tag_name: str):
        """Handle field based on its context"""
        # CTC fields
        ctc_keywords = {
            'current': ['current ctc', 'current compensation', 'current salary', 'current annual'],
            'expected': ['expected ctc', 'expected salary', 'desired compensation', 'expected annual']
        }
        
        for ctc_type, keywords in ctc_keywords.items():
            if any(keyword in context_text for keyword in keywords):
                self.field_handler.handle_ctc_field(field, context_text, ctc_type == 'current')
                return
        
        # Experience fields
        experience_keywords = ['years of experience', 'total experience', 
                              'professional experience', 'work experience']
        
        if any(keyword in context_text for keyword in experience_keywords):
            self.field_handler.handle_experience_field(field, context_text)
            return
        
        # Technology experience
        tech_keywords = ['python', 'javascript', 'react', 'node', 'sql', 
                        'mongodb', '.net', 'java', 'aws', 'docker', 'typescript']
        
        if any(tech in context_text for tech in tech_keywords):
            self.field_handler.handle_experience_field(field, context_text)
            return
        
        # Notice period
        if any(keyword in context_text for keyword in ['notice period', 'availability', 'joining']):
            self.field_handler.handle_notice_period_field(field)
            return
    
    def _fill_number_inputs(self, page, modal_selector: str):
        """Fill number input fields"""
        number_inputs = page.query_selector_all(f"{modal_selector} input[type='number']")
        
        for field in number_inputs:
            if not field.is_visible():
                continue
            
            try:
                if field.input_value() and field.input_value().strip():
                    continue
                
                context = self.field_detector.get_field_context(page, field).lower()
                
                # Determine value based on context
                if any(keyword in context for keyword in ['ctc', 'salary', 'compensation']):
                    if 'current' in context:
                        value = self.config.ANSWERS.get("current_ctc", "6.0")
                    else:
                        value = self.config.ANSWERS.get("expected_ctc", "7.0")
                elif any(keyword in context for keyword in ['experience', 'years']):
                    value = self.config.ANSWERS.get("total_experience_years", "2")
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
    
    def _fill_textareas(self, page, modal_selector: str):
        """Fill textarea fields"""
        textareas = page.query_selector_all(f"{modal_selector} textarea")
        
        for textarea in textareas:
            if not textarea.is_visible():
                continue
            
            try:
                if textarea.input_value() and textarea.input_value().strip():
                    continue
                
                context = self.field_detector.get_field_context(page, textarea).lower()
                
                # Provide appropriate text
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