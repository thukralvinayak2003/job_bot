import time
from typing import Dict

class FieldHandler:
    """Handles different types of form fields"""
    
    def __init__(self, config):
        self.config = config
    
    def handle_ctc_field(self, field, context_text: str, is_current: bool = True):
        """Handle CTC/Salary fields"""
        try:
            if is_current:
                value = self._get_current_ctc_value(context_text)
            else:
                value = self._get_expected_ctc_value(context_text)
            
            field.fill(str(value))
            time.sleep(0.3)
            print(f"✓ Filled {'current' if is_current else 'expected'} CTC: {value}")
        except Exception as e:
            print(f"Error filling CTC field: {e}")
    
    def handle_experience_field(self, field, context_text: str):
        """Handle experience years fields"""
        try:
            # Technology-specific experience
            tech_mappings = {
                'python': 'experience_python',
                'javascript': 'experience_javascript',
                'react': 'experience_react',
                'node': 'experience_nodejs',
                'sql': 'experience_sql',
                'mongodb': 'experience_mongodb',
                '.net': 'experience_dotnet',
                'aws': 'experience_aws',
                'docker': 'experience_docker',
                'typescript': 'experience_typescript',
            }
            
            for tech, answer_key in tech_mappings.items():
                if tech in context_text:
                    value = self.config.ANSWERS.get(answer_key, "2")
                    field.fill(str(value))
                    time.sleep(0.3)
                    print(f"✓ Filled {tech} experience: {value}")
                    return
            
            # Default to total experience
            value = self.config.ANSWERS.get("total_experience_years", "2")
            field.fill(str(value))
            time.sleep(0.3)
            print(f"✓ Filled experience: {value}")
        except Exception as e:
            print(f"Error filling experience field: {e}")
    
    def handle_notice_period_field(self, field):
        """Handle notice period fields"""
        try:
            value = self.config.ANSWERS.get("notice_period", "30 days")
            tag_name = field.evaluate("el => el.tagName.toLowerCase()")
            
            if tag_name == 'select':
                self._select_notice_period_option(field, value)
            else:
                field.fill(value)
            
            time.sleep(0.3)
            print(f"✓ Filled notice period: {value}")
        except Exception as e:
            print(f"Error filling notice period: {e}")
    
    def _get_current_ctc_value(self, context_text: str) -> str:
        """Get current CTC value based on context"""
        if 'lakh' in context_text or 'lpa' in context_text:
            return self.config.ANSWERS.get("current_ctc", "6.0")
        return self.config.ANSWERS.get("current_salary", "470000")
    
    def _get_expected_ctc_value(self, context_text: str) -> str:
        """Get expected CTC value based on context"""
        if 'lakh' in context_text or 'lpa' in context_text:
            return self.config.ANSWERS.get("expected_ctc", "7.0")
        return self.config.ANSWERS.get("expected_salary", "700000")
    
    def _select_notice_period_option(self, select_field, value: str):
        """Select notice period in dropdown"""
        options = ["30 days", "1 month", "Immediate", "15 days"]
        
        for option in options:
            try:
                select_field.select_option(label=option)
                return
            except:
                continue
        
        # Fallback to first available option
        try:
            select_field.select_option(index=1)
        except:
            pass