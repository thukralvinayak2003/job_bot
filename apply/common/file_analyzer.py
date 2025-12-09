"""
field_analyzer.py
Analyzes form fields to determine their purpose.
"""
from typing import Dict, List
from playwright.sync_api import Page


class FieldAnalyzer:
    """Analyzes form fields to understand what information they're asking for."""
    
    FIELD_PATTERNS = {
        'work_auth': [
            'authorized', 'authorization', 'eligible', 'eligibility',
            'sponsorship', 'visa', 'work permit', 'legally authorized'
        ],
        'experience_years': [
            'years of experience', 'years experience', 'how many years',
            'experience in years', 'total experience'
        ],
        'salary': [
            'salary', 'compensation', 'ctc', 'annual', 'rate'
        ],
        'notice_period': [
            'notice period', 'notice', 'availability', 'available to start'
        ],
        'education': [
            'education', 'degree', 'qualification', 'highest education'
        ],
        'location': [
            'location', 'city', 'address', 'where are you based'
        ]
    }
    
    def detect_field_type(self, element, page: Page) -> str:
        """Detect what type of information a field is asking for."""
        context = self._get_field_context(element, page)
        
        for field_type, patterns in self.FIELD_PATTERNS.items():
            if any(pattern in context for pattern in patterns):
                return field_type
        
        return 'unknown'
    
    def _get_field_context(self, element, page: Page) -> str:
        """Get comprehensive context for a form field."""
        context_parts = []
        
        # Get element attributes
        attributes = ['id', 'name', 'placeholder', 'aria-label']
        for attr in attributes:
            value = element.get_attribute(attr) or ''
            if value:
                context_parts.append(value)
        
        # Get associated label
        field_id = element.get_attribute('id')
        if field_id:
            label = page.query_selector(f"label[for='{field_id}']")
            if label:
                context_parts.append(label.inner_text())
        
        # Get parent text
        parent_text = self._get_parent_text(element)
        if parent_text:
            context_parts.append(parent_text)
        
        return " ".join(context_parts).lower()
    
    def _get_parent_text(self, element) -> str:
        """Get text from parent elements."""
        try:
            return element.evaluate("""
                el => {
                    const parent = el.closest('div, fieldset, li');
                    return parent ? parent.innerText : '';
                }
            """)
        except Exception:
            return ""