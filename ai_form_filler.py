"""
ai_form_filler.py
AI-powered form filling with ANTI-HALLUCINATION safeguards
Optimized for LinkedIn and Indeed form automation
ENHANCED: Perfect handling of ALL experience questions
"""

import requests
import re
from typing import Optional, Dict, Any, List
from config import config

class AIFormFiller:
    def __init__(self, model_name: str = "phi4-mini"):
        """
        Initialize AI Form Filler with Ollama
        
        Args:
            model_name: Name of the Ollama model (default: phi4-mini)
        """
        self.model_name = model_name
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.user_profile = self._build_user_profile()
        
        # Cache for common answers to avoid repeated AI calls
        self.answer_cache = {}
        
    def _build_user_profile(self) -> str:
        """Build comprehensive user profile context from config"""
        profile = f"""
USER PROFILE DATA:
==================
NAME: {config.FULL_NAME}
EMAIL: {config.EMAIL}
PHONE: {config.PHONE}
LOCATION: {config.CURRENT_LOCATION}
ADDRESS: {config.ADDRESS}
CITY: {config.CITY}
STATE: {config.STATE}
POSTAL_CODE: {config.POSTAL_CODE}
COUNTRY: {config.COUNTRY}

PROFESSIONAL:
COMPANY: {config.ANSWERS.get('current_company', 'Virtueaze')}
TARGET_ROLE: {getattr(config, 'TARGET_ROLE', 'Senior MERN/AI Developer')}
EXPERIENCE_YEARS: {config.YEARS_EXPERIENCE}
CURRENT_CTC_INR: {config.ANSWERS.get('current_ctc', '470000')}
CURRENT_CTC_LPA: {config.CURRENT_SALARY}
EXPECTED_CTC_INR: {config.ANSWERS.get('expected_ctc', '700000')}
EXPECTED_CTC_LPA: {config.EXPECTED_SALARY}
NOTICE_PERIOD_DAYS: {config.NOTICE_PERIOD}
EDUCATION: {config.EDUCATION}

SKILLS: {config.SKILLS}

EXPERIENCE GUIDANCE:
- Total professional experience: {config.YEARS_EXPERIENCE} years.
- Use skill-specific experience from COMMON_ANSWERS when available.
- For resume skills without a specific override, use {config.YEARS_EXPERIENCE} years.
- For unrelated technologies not present in the resume, use 0.

LINKS:
GITHUB: {config.GITHUB}
LINKEDIN: {config.LINKEDIN}

PREFERENCES:
WORK_AUTH_INDIA: Yes
RELOCATE: Yes
REMOTE: Yes
TRAVEL: Yes
FULL_TIME: Yes
CONTRACT: Yes
SHIFT_WORK: Yes
BACKGROUND_CHECK: Yes
"""
        return profile
    
    def _get_direct_answer(self, field_context: str, field_type: str) -> Optional[str]:
        """
        Get direct answer from config without AI for common fields.
        This prevents hallucination for simple lookups.
        """
        field_lower = field_context.lower()

        skill_experience = self._get_skill_experience_answer(field_lower)
        if skill_experience is not None:
            print(f"Direct skill experience match: '{skill_experience}'")
            return skill_experience
        
        # Check COMMON_ANSWERS dictionary first
        for key, value in config.ANSWERS.items():
            key_normalized = key.lower().replace('_', ' ')
            if key_normalized in field_lower or key.lower() in field_lower:
                print(f"Direct match from COMMON_ANSWERS: '{value}'")
                return str(value)
        
        # Exact match dictionary for instant answers
        direct_mappings = {
            # Personal info
            'full name': config.FULL_NAME,
            'first name': config.FULL_NAME.split()[0] if config.FULL_NAME else '',
            'last name': config.FULL_NAME.split()[-1] if config.FULL_NAME and len(config.FULL_NAME.split()) > 1 else '',
            'email': config.EMAIL,
            'phone': config.PHONE,
            'mobile': config.PHONE,
            'country': config.COUNTRY,
            'city': config.CITY,
            'state': config.STATE,
            'address': config.ADDRESS,
            'postal code': str(config.POSTAL_CODE),
            'zip code': str(config.POSTAL_CODE),
            'pin code': str(config.POSTAL_CODE),
            
            # Professional
            'current company': config.ANSWERS.get('current_company', 'Virtueaze'),
            'employer': config.ANSWERS.get('current_company', 'Virtueaze'),
            'education': config.EDUCATION,
            'qualification': config.EDUCATION,
            'degree': config.EDUCATION,
            
            # Social links
            'github': config.GITHUB,
            'github profile': config.GITHUB,
            'github url': config.GITHUB,
            'linkedin': config.LINKEDIN,
            'linkedin profile': config.LINKEDIN,
            'linkedin url': config.LINKEDIN,
        }
        
        # Check for exact match
        for key, value in direct_mappings.items():
            if key in field_lower:
                print(f"Direct match: '{value}'")
                return str(value)
        
        # Number field specific patterns
        if field_type == 'number':
            # CTC patterns
            if any(kw in field_lower for kw in ['current ctc', 'current salary', 'current compensation', 'present ctc', 'current package']):
                if any(kw in field_lower for kw in ['lpa', 'lakh', 'lakhs per annum']):
                    return str(config.CURRENT_SALARY).replace(' LPA', '').replace('LPA', '').strip()
                else:  # Assume rupees
                    return config.ANSWERS.get('current_ctc', '470000')
            
            if any(kw in field_lower for kw in ['expected ctc', 'expected salary', 'desired salary', 'expected compensation', 'expected package']):
                if any(kw in field_lower for kw in ['lpa', 'lakh', 'lakhs per annum']):
                    return str(config.EXPECTED_SALARY).replace(' LPA', '').replace('LPA', '').strip()
                else:  # Assume rupees
                    return config.ANSWERS.get('expected_ctc', '700000')
            
            # ENHANCED EXPERIENCE DETECTION - This is the KEY fix
            # Check if field is asking about experience/years
            experience_keywords = [
                'experience', 'years', 'yoe', 'expertise', 'proficiency',
                'worked with', 'using', 'knowledge', 'familiar', 'skilled in'
            ]
            
            if any(kw in field_lower for kw in experience_keywords):
                print(f"Experience question detected: {config.YEARS_EXPERIENCE} years")
                return config.YEARS_EXPERIENCE
            
            # Notice period
            if any(kw in field_lower for kw in ['notice period', 'notice', 'serving notice', 'availability']):
                return config.NOTICE_PERIOD
        
        # Yes/No fields - Enhanced logic
        if field_type in ['checkbox', 'radio']:
            # Work authorization (ALWAYS YES)
            if any(kw in field_lower for kw in ['authorized to work', 'work authorization', 'legal to work', 'right to work', 'work permit']):
                return 'Yes'
            
            # Sponsorship (ALWAYS NO - we don't need it)
            if any(kw in field_lower for kw in ['require sponsorship', 'need sponsorship', 'visa sponsorship']):
                return 'No'
            
            # Relocation (ALWAYS YES)
            if any(kw in field_lower for kw in ['relocate', 'relocation', 'willing to relocate']):
                return 'Yes'
            
            # Remote (ALWAYS YES)
            if any(kw in field_lower for kw in ['remote', 'work from home', 'wfh']):
                return 'Yes'
            
            # Experience with technology (ALWAYS YES)
            if any(kw in field_lower for kw in ['experience with', 'experience in', 'familiar with', 'knowledge of', 'worked with', 'used']):
                return 'Yes'
            
            # Positive questions pattern (ALWAYS YES)
            positive_patterns = [
                'full time', 'full-time', 'willing to travel', 'background check',
                'comfortable with', 'open to', 'interested in', 'can you', 'shift work',
                'night shift', 'weekend work', 'agile', 'scrum', 'startup'
            ]
            
            if any(pattern in field_lower for pattern in positive_patterns):
                return 'Yes'
            
            # Negative questions pattern (ALWAYS NO)
            negative_patterns = [
                'worked with us before', 'previous employee', 'criminal',
                'felony', 'convicted', 'terminated', 'fired', 'immediate joiner',
                'available immediately'
            ]
            
            if any(pattern in field_lower for pattern in negative_patterns):
                return 'No'
            
            # Generic positive question detection
            if any(starter in field_lower for starter in ['do you', 'are you', 'have you', 'can you', 'will you', 'would you']):
                # Default to Yes for generic positive questions
                return 'Yes'
        
        return None

    def _get_skill_experience_answer(self, field_lower: str) -> Optional[str]:
        """Return resume-backed years for skill-specific experience questions."""
        if not any(kw in field_lower for kw in ['experience', 'years', 'yoe', 'worked with', 'using']):
            return None

        skill_aliases = {
            'experience_system_design': ['system design', 'architecture', 'scalable systems'],
            'experience_microservices': ['microservice', 'distributed service'],
            'experience_typescript': ['typescript'],
            'experience_javascript': ['javascript'],
            'experience_nodejs': ['node.js', 'nodejs', 'node js'],
            'experience_express': ['express.js', 'expressjs', 'express'],
            'experience_react': ['react.js', 'reactjs', 'react'],
            'experience_nextjs': ['next.js', 'nextjs', 'next js'],
            'experience_mongodb': ['mongodb', 'mongo'],
            'experience_postgresql': ['postgresql', 'postgres'],
            'experience_sql': [' sql', 'database', 'databases'],
            'experience_docker': ['docker', 'container'],
            'experience_aws': ['aws', 'lambda', 's3', 'ec2', 'amplify', 'iot core'],
            'experience_rest_api': ['rest api', 'rest apis'],
            'experience_graphql': ['graphql'],
            'experience_prisma': ['prisma'],
            'experience_redis': ['redis'],
            'experience_rabbitmq': ['rabbitmq'],
            'experience_langchain': ['langchain'],
            'experience_openai': ['openai'],
            'experience_anthropic': ['anthropic'],
            'experience_rag': ['rag', 'retrieval-augmented generation'],
            'experience_python': ['python'],
        }

        for answer_key, aliases in skill_aliases.items():
            if any(alias in field_lower for alias in aliases):
                return str(config.ANSWERS.get(answer_key, config.YEARS_EXPERIENCE))

        if any(kw in field_lower for kw in ['total', 'overall', 'professional']):
            return str(config.YEARS_EXPERIENCE)

        return None
    
    def generate_answer(self, field_context: str, field_type: str, options: list = None) -> Optional[str]:
        """
        Generate intelligent answer for a form field
        
        Args:
            field_context: Full context of the field
            field_type: Type of field
            options: Available options for select/radio
            
        Returns:
            Generated answer or None
        """
        
        # Create cache key
        cache_key = f"{field_context}|{field_type}|{str(options)}"
        if cache_key in self.answer_cache:
            print(f"Cache hit: '{self.answer_cache[cache_key]}'")
            return self.answer_cache[cache_key]
        
        # Try direct answer first (no AI needed)
        direct_answer = self._get_direct_answer(field_context, field_type)
        if direct_answer:
            self.answer_cache[cache_key] = direct_answer
            return direct_answer
        
        # Use AI for complex fields
        prompt = self._build_strict_prompt(field_context, field_type, options)
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.01,
                    "top_p": 0.5,
                    "max_tokens": 50,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_answer = result.get("response", "").strip()
                
                # Aggressive cleaning
                answer = self._extract_clean_answer(raw_answer, field_type, options, field_context)
                
                if answer:
                    print(f"AI Generated: '{answer}'")
                    self.answer_cache[cache_key] = answer
                    return answer
                else:
                    print("AI returned empty after cleaning")
                    return None
            else:
                print(f"Ollama error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def _build_strict_prompt(self, field_context: str, field_type: str, options: list = None) -> str:
        """Build ultra-strict prompt to prevent hallucinations"""
        
        options_section = ""
        if options:
            clean_opts = [opt.strip() for opt in options if opt and opt.strip()][:10]
            if clean_opts:
                options_section = f"\nVALID_OPTIONS: {', '.join(clean_opts)}"
        
        prompt = f"""{self.user_profile}

FIELD: {field_context}
TYPE: {field_type}{options_section}

EXPERIENCE RULE:
- For total/overall experience: answer "{config.YEARS_EXPERIENCE}"
- For skill experience: use the resume-backed skill-specific value when available
- For resume skills without a specific override: answer "{config.YEARS_EXPERIENCE}"
- For unrelated technologies not present in the resume: answer "0"

STRICT OUTPUT RULES:
1. Output ONLY the value - NO labels, NO colons, NO "Answer:", NO explanations
2. For NUMBER: Output ONLY digits (e.g., "470000" NOT "Current CTC: 470000")
3. For SELECT/RADIO: Output EXACTLY one option from VALID_OPTIONS
4. For CHECKBOX: Output "Yes" or "No"
5. For TEXT: Output ONLY the value from profile
6. For experience questions: output only the number of years
7. For positive questions (do you, are you, can you): Output "Yes"
8. For negative questions (criminal, fired, etc): Output "No"
9. Do not invent experience outside the resume

OUTPUT VALUE ONLY (nothing else):"""
        
        return prompt
    
    def _extract_clean_answer(self, raw_answer: str, field_type: str, options: list = None, field_context: str = "") -> str:
        """Extract clean answer with aggressive anti-hallucination cleaning"""
        
        if not raw_answer:
            return ""
        
        # Remove newlines and normalize whitespace
        answer = ' '.join(raw_answer.split()).strip()
        
        # Remove common hallucination patterns
        hallucination_patterns = [
            r'^(answer|response|output|result|value|field|label|the answer is|here is|it is|based on|according to)\s*[:\-]?\s*',
            r'^["\']|["\']$',
            r'^`|`$',
        ]
        
        for pattern in hallucination_patterns:
            answer = re.sub(pattern, '', answer, flags=re.IGNORECASE).strip()
        
        # Remove field label repetitions
        field_lower = field_context.lower()
        field_terms = re.findall(r'\b\w+\b', field_lower)
        
        for term in field_terms:
            if len(term) > 3:
                pattern = rf'^{re.escape(term)}\s*[:\-]\s*'
                answer = re.sub(pattern, '', answer, flags=re.IGNORECASE).strip()
        
        # Generic label removal
        answer = re.sub(r'^[\w\s]+:\s*', '', answer).strip()
        
        # ===== NUMBER FIELDS =====
        if field_type == "number":
            number_match = re.search(r'-?\d+\.?\d*', answer)
            if number_match:
                extracted_num = number_match.group(0)
                
                return extracted_num
            
            # Fallback to direct answer
            direct = self._get_direct_answer(field_context, field_type)
            return direct if direct else ""
        
        # ===== SELECT/RADIO =====
        if field_type in ["select", "radio"] and options:
            matched = self._match_option(answer, options)
            return matched if matched else ""
        
        # ===== CHECKBOX =====
        if field_type == "checkbox":
            answer_lower = answer.lower()
            
            # Check if it's an experience question that got "no" as answer
            field_lower = field_context.lower()
            if any(kw in field_lower for kw in ['experience with', 'experience in', 'familiar with', 'knowledge of']):
                print("Fixed: Changed to 'Yes' for experience checkbox")
                return "Yes"
            
            if any(w in answer_lower for w in ['yes', 'true', '1', 'check']):
                return "Yes"
            if any(w in answer_lower for w in ['no', 'false', '0', 'uncheck']):
                return "No"
            
            direct = self._get_direct_answer(field_context, field_type)
            return direct if direct else "Yes"  # Default to Yes for positive questions
        
        # ===== TEXT/TEXTAREA =====
        answer = answer.rstrip('.,;:!?')
        
        if ':' in answer or '=' in answer:
            parts = re.split(r'[:\=]', answer)
            answer = parts[-1].strip()
        
        if len(answer) > 500:
            answer = answer[:500]
        
        return answer
    
    def _match_option(self, answer: str, options: List[str]) -> str:
        """Match answer to option with strict validation"""
        
        if not options or not answer:
            return ""
        
        answer = answer.strip()
        answer_lower = answer.lower()
        clean_options = [opt.strip() for opt in options if opt and opt.strip()]
        
        if not clean_options:
            return ""
        
        # 1. Exact match
        for option in clean_options:
            if answer_lower == option.lower():
                return option
        
        # 2. Answer contained in option
        for option in clean_options:
            if answer_lower in option.lower():
                return option
        
        # 3. Option contained in answer
        for option in clean_options:
            if option.lower() in answer_lower:
                return option
        
        # 4. Normalized match
        answer_norm = re.sub(r'[^\w\s]', '', answer_lower)
        for option in clean_options:
            option_norm = re.sub(r'[^\w\s]', '', option.lower())
            if answer_norm == option_norm:
                return option
        
        # 5. Number matching (for experience dropdowns like "2 years", "3-5 years")
        answer_nums = re.findall(r'\d+', answer)
        if answer_nums:
            for option in clean_options:
                option_nums = re.findall(r'\d+', option)
                if any(num in option_nums for num in answer_nums):
                    return option
        
        # 6. Word overlap
        answer_words = set(answer_norm.split())
        best_match = None
        best_score = 0
        
        for option in clean_options:
            option_norm = re.sub(r'[^\w\s]', '', option.lower())
            option_words = set(option_norm.split())
            
            if not option_words:
                continue
            
            overlap = len(answer_words & option_words) / len(option_words)
            if overlap > best_score:
                best_score = overlap
                best_match = option
        
        if best_match and best_score >= 0.6:
            return best_match
        
        # 7. For experience dropdowns, try to find option with "2" years
        for option in clean_options:
            if config.YEARS_EXPERIENCE in option or f"{config.YEARS_EXPERIENCE} year" in option.lower():
                print(f"Selected experience option: {option}")
                return option
        
        # Default to first option
        print("No good match, using first option")
        return clean_options[0]
    
    def is_ollama_available(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                available = any(self.model_name in name for name in model_names)
                
                if available:
                    print("Ollama running with Phi-4")
                else:
                    print(f"{self.model_name} not found")
                
                return available
            return False
        except:
            print("Ollama not accessible")
            return False
    
    def clear_cache(self):
        """Clear answer cache"""
        self.answer_cache = {}
        print("Cache cleared")


# Global instance
ai_filler = AIFormFiller()

if __name__ == "__main__":
    if ai_filler.is_ollama_available():
        print("\nAI Form Filler ready!")
    else:
        print("\nPlease start Ollama and ensure phi4-mini model is installed")
