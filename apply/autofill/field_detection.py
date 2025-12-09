from playwright.sync_api import Page

class FieldDetector:
    """Detects and extracts context from form fields"""
    
    @staticmethod
    def get_field_context(page: Page, field) -> str:
        """Get surrounding context text for a field"""
        try:
            context_parts = []
            
            # Get attributes
            for attr in ['placeholder', 'aria-label', 'aria-describedby']:
                value = field.get_attribute(attr)
                if value:
                    context_parts.append(value)
            
            # Get associated label via id
            field_id = field.get_attribute('id')
            if field_id:
                label = page.query_selector(f"label[for='{field_id}']")
                if label:
                    context_parts.append(label.inner_text())
            
            # Get parent label and nearby text using JavaScript
            try:
                nearby_text = field.evaluate("""
                    el => {
                        let text = '';
                        
                        // Get parent label text
                        const parentLabel = el.closest('label');
                        if (parentLabel) text += parentLabel.innerText || '';
                        
                        // Get previous sibling text
                        if (el.previousElementSibling) {
                            text += ' ' + (el.previousElementSibling.innerText || '');
                        }
                        
                        // Get parent text excluding children
                        if (el.parentElement) {
                            const parentClone = el.parentElement.cloneNode(true);
                            const fieldClone = parentClone.querySelector(`[id="${el.id}"]`);
                            if (fieldClone) fieldClone.remove();
                            text += ' ' + (parentClone.innerText || '');
                        }
                        
                        return text.trim();
                    }
                """)
                if nearby_text:
                    context_parts.append(nearby_text)
            except:
                pass
            
            return ' '.join(context_parts).strip()
        except:
            return ""

    @staticmethod
    def analyze_field_type(field):
        """Analyze field type and tag"""
        try:
            field_type = field.get_attribute('type') or ''
            tag_name = field.evaluate("el => el.tagName.toLowerCase()")
            return tag_name, field_type.lower()
        except:
            return 'unknown', 'unknown'