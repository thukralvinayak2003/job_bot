"""
form_filler.py
Simplified form filler for LinkedIn.
"""
from typing import Dict
from playwright.sync_api import Page
from apply.common.utils import human_delay


class FormFiller:
    """Handles form filling for job applications."""
    
    def __init__(self, config: Dict):
        self.config = config
    
    def fill_standard_fields(self, page: Page) -> int:
        """Fill standard form fields. Returns count of filled fields."""
        filled_count = 0
        
        # Try to fill email
        if self._fill_field_by_pattern(page, "email", self.config.get("EMAIL")):
            filled_count += 1
        
        # Try to fill phone
        if self._fill_field_by_pattern(page, "phone", self.config.get("PHONE")):
            filled_count += 1
        
        # Try to fill name
        if self._fill_field_by_pattern(page, "name", self.config.get("FULL_NAME")):
            filled_count += 1
        
        # Try to fill location
        if self._fill_field_by_pattern(page, "location", self.config.get("LOCATION")):
            filled_count += 1
        
        # Fill some dropdowns
        filled_count += self._fill_dropdowns(page)
        
        return filled_count
    
    def _fill_field_by_pattern(self, page: Page, field_name: str, value: str) -> bool:
        """Find and fill field by name pattern."""
        if not value:
            return False
        
        patterns = {
            "email": ["email", "e-mail"],
            "phone": ["phone", "mobile", "tel"],
            "name": ["name", "full name", "first name", "last name"],
            "location": ["location", "city", "address"]
        }
        
        if field_name not in patterns:
            return False
        
        for pattern in patterns[field_name]:
            selectors = [
                f"input[type='text'][placeholder*='{pattern}']",
                f"input[placeholder*='{pattern}']",
                f"input[name*='{pattern}']",
                f"input[id*='{pattern}']"
            ]
            
            for selector in selectors:
                try:
                    fields = page.locator(selector).all()
                    for field in fields:
                        if field.is_visible():
                            current_value = field.input_value()
                            if not current_value or current_value.strip() == "":
                                field.fill(value)
                                human_delay(0.2, 0.5)
                                return True
                except Exception:
                    continue
        
        return False
    
    def _fill_dropdowns(self, page: Page) -> int:
        """Fill dropdown fields with default values."""
        filled = 0
        
        try:
            # Find all select elements in modal
            selects = page.locator("div[role='dialog'] select").all()
            
            for select in selects:
                if select.is_visible():
                    try:
                        # Try to select first non-empty option
                        options = select.locator("option:not([value='']):not(:empty)").all()
                        if len(options) > 0:
                            select.select_option(index=0)
                            filled += 1
                            human_delay(0.2, 0.4)
                    except Exception:
                        continue
                        
        except Exception:
            pass
        
        return filled