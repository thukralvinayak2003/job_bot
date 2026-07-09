# FieldDetector.py
from playwright.sync_api import Page

class FieldDetector:
    """Detects and extracts context from form fields - Updated for AI context"""
    
    @staticmethod
    def get_field_context(page: Page, field) -> str:
        """Get surrounding context text for a field - Optimized for AI"""
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
                        
                        // Get grandparent text (e.g., for questions in containers)
                        const grandParent = el.parentElement?.parentElement;
                        if (grandParent) {
                            const grandParentText = grandParent.innerText || '';
                            // Only add if it's not too long and likely contains the question
                            if (grandParentText && grandParentText.length < 500) {
                                text += ' ' + grandParentText;
                            }
                        }
                        
                        return text.trim();
                    }
                """)
                if nearby_text:
                    context_parts.append(nearby_text)
            except Exception as e:
                print(f" ⚠  Error getting JavaScript context: {e}")
                pass
            
            return ' '.join(context_parts).strip()
        except Exception as e:
            print(f" ⚠  Error getting field context: {e}")
            return ""

    @staticmethod
    def analyze_field_type(field):
        """Analyze field type and tag - Kept for potential use"""
        try:
            field_type = field.get_attribute('type') or ''
            tag_name = field.evaluate("el => el.tagName.toLowerCase()")
            return tag_name, field_type.lower()
        except:
            return 'unknown', 'unknown'