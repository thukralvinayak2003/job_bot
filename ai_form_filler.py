"""
ai_form_filler.py
AI-powered form filling using Ollama with Phi-4 Mini
"""

import requests
import json
from typing import Optional, Dict, Any
from config import config

class AIFormFiller:
    def __init__(self, model_name: str = "phi4-mini"):
        """
        Initialize AI Form Filler with Ollama
        
        Args:
            model_name: Name of the Ollama model (default: phi4)
        """
        self.model_name = model_name
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.user_profile = self._build_user_profile()
        
    def _build_user_profile(self) -> str:
        """Build user profile context from config"""
        profile = f"""
USER PROFILE:
- Name: {config.FULL_NAME}
- Email: {config.EMAIL}
- Phone: {config.PHONE}
- Location: {config.LOCATION}
- Years of Experience: {getattr(config, 'YEARS_EXPERIENCE', 'Not specified')}
- Current Salary: {getattr(config, 'CURRENT_SALARY', 'Not specified')} LPA
- Expected Salary: {getattr(config, 'EXPECTED_SALARY', 'Not specified')} LPA
- Notice Period: {getattr(config, 'NOTICE_PERIOD', 'Not specified')} days
- Work Authorization: Authorized to work in India
- Education: {getattr(config, 'EDUCATION', 'Not specified')}
- Skills: {getattr(config, 'SKILLS', 'Not specified')}

COMMON ANSWERS:
{json.dumps(config.ANSWERS, indent=2)}
"""
        return profile
    
    def generate_answer(self, field_context: str, field_type: str, options: list = None) -> Optional[str]:
        """
        Generate intelligent answer for a form field using Phi-4
        
        Args:
            field_context: Full context of the field (label, placeholder, nearby text)
            field_type: Type of field (text, number, dropdown, radio, etc.)
            options: Available options for dropdown/radio (if applicable)
            
        Returns:
            Generated answer or None if generation fails
        """
        
        prompt = self._build_prompt(field_context, field_type, options)
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3,  # Low temperature for consistent answers
                    "top_p": 0.9,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("response", "").strip()
                
                # Post-process answer
                answer = self._clean_answer(answer, field_type, options)
                
                print(f"🤖 AI Generated: '{answer}'")
                return answer
            else:
                print(f"⚠ Ollama request failed: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"⚠ Error connecting to Ollama: {e}")
            return None
        except Exception as e:
            print(f"⚠ Error generating answer: {e}")
            return None
    
    def _build_prompt(self, field_context: str, field_type: str, options: list = None) -> str:
        """Build prompt for Phi-4"""
        
        options_text = ""
        if options:
            options_text = f"\n\nAVAILABLE OPTIONS:\n" + "\n".join(f"- {opt}" for opt in options[:10])
        
        prompt = f"""{self.user_profile}

TASK: Fill a job application form field.

FIELD CONTEXT:
{field_context}

FIELD TYPE: {field_type}
{options_text}

INSTRUCTIONS:
1. Read the field context carefully
2. Provide ONLY the answer - no explanation, no extra text
3. For yes/no questions: answer only "Yes" or "No"
4. For dropdowns: choose from available options
5. For number fields: provide only the number
6. For text fields: provide concise, relevant answer
7. Be truthful based on the user profile
8. If asking about criminal record, termination, or negative things: answer "No"
9. If asking about authorization to work in India: answer "Yes"
10. If uncertain, make reasonable assumption based on profile

ANSWER (only the value, nothing else):"""
        
        return prompt
    
    def _clean_answer(self, answer: str, field_type: str, options: list = None) -> str:
        """Clean and validate AI-generated answer"""
        
        # Remove common artifacts
        answer = answer.strip()
        answer = answer.replace('"', '').replace("'", '')
        answer = answer.split('\n')[0]  # Take only first line
        
        # Remove common prefixes
        prefixes = ["Answer:", "Response:", "The answer is", "I would answer"]
        for prefix in prefixes:
            if answer.lower().startswith(prefix.lower()):
                answer = answer[len(prefix):].strip()
        
        # For yes/no questions
        if field_type in ['radio', 'checkbox']:
            answer_lower = answer.lower()
            if 'yes' in answer_lower or 'true' in answer_lower:
                return "Yes"
            elif 'no' in answer_lower or 'false' in answer_lower:
                return "No"
        
        # For dropdowns, match with available options
        if options and field_type == 'select':
            answer_lower = answer.lower()
            for option in options:
                if answer_lower in option.lower() or option.lower() in answer_lower:
                    return option
        
        # Limit length for text fields
        if len(answer) > 500:
            answer = answer[:500]
        
        return answer
    
    def is_ollama_available(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                # Check if phi4 or phi4:latest is available
                available = any(self.model_name in name for name in model_names)
                
                if available:
                    print("✓ Ollama is running and Phi-4 model is available")
                else:
                    print(f"⚠ Ollama is running but {self.model_name} model not found")
                    print(f"Available models: {', '.join(model_names)}")
                    
                return available
            return False
        except:
            print("⚠ Ollama is not running or not accessible")
            return False
    
    def test_generation(self):
        """Test AI generation with sample questions"""
        print("\n" + "="*60)
        print("Testing AI Form Filler")
        print("="*60)
        
        test_cases = [
            {
                "context": "Are you authorized to work in India without sponsorship?",
                "type": "radio",
                "options": ["Yes", "No"]
            },
            {
                "context": "How many years of experience do you have in software development?",
                "type": "text",
                "options": None
            },
            {
                "context": "What is your expected salary? (in LPA)",
                "type": "number",
                "options": None
            },
            {
                "context": "Have you ever been convicted of a felony?",
                "type": "radio",
                "options": ["Yes", "No"]
            }
        ]
        
        for i, test in enumerate(test_cases, 1):
            print(f"\nTest {i}:")
            print(f"Question: {test['context']}")
            answer = self.generate_answer(
                test['context'],
                test['type'],
                test['options']
            )
            print(f"Answer: {answer}")
            print("-" * 60)


# Global instance
ai_filler = AIFormFiller()