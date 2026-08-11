"""
ai_form_filler.py
AI-powered form filling with ANTI-HALLUCINATION safeguards
"""

import requests
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import config

class AIFormFiller:
    def __init__(self, model_name: str = "phi4-mini"):
        """Initialize AI Form Filler with Ollama"""
        self.model_name = model_name
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.user_profile = self._build_user_profile()
        self.answer_cache = {}

    def _build_user_profile(self) -> str:
        """Build comprehensive user profile context from config & resume"""
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

PROFESSIONAL SUMMARY:
TITLE: Senior Software Developer · Backend & Full Stack Engineering
TARGET_ROLE: {getattr(config, 'TARGET_ROLE', 'Senior Software Developer / Backend & Full Stack Engineering')}
TOTAL_EXPERIENCE_YEARS: {config.YEARS_EXPERIENCE}
CURRENT_COMPANY: {getattr(config, 'CURRENT_COMPANY', 'Sisgain')} (Jan 2026 – Present)
PREVIOUS_COMPANIES: {getattr(config, 'PREVIOUS_COMPANIES', 'Virtueaze (Oct 2024 – Dec 2025), IIT Ropar (Feb 2024 – Sept 2024)')}

SALARY & NOTICE:
CURRENT_CTC_INR: {config.ANSWERS.get('current_ctc', '470000')}
CURRENT_CTC_LPA: {config.CURRENT_SALARY}
EXPECTED_CTC_INR: {config.ANSWERS.get('expected_ctc', '700000')}
EXPECTED_CTC_LPA: {config.EXPECTED_SALARY}
NOTICE_PERIOD_DAYS: {config.NOTICE_PERIOD}

EDUCATION:
DEGREE: B.Tech, Computer Science Engineering (2025)
INSTITUTION: Amritsar Group of Colleges, Punjab, India
GRADUATION_CGPA: 7.8
12TH_PERCENTAGE: {config.ANSWERS.get('12th_percentage', '82%')}
10TH_PERCENTAGE: {config.ANSWERS.get('10th_percentage', '85%')}

PROJECTS:
- FarmFlow (farmflow.ca): Smart Farming & IoT Platform (Node.js, React.js, AWS IoT Core, Firebase Functions, Microservices, Predictive AI)
- WebbWe (webbwe.com): Custom CMS for Creative Agencies (React.js, Node.js, Express.js, MongoDB, GraphQL, Microservices, Docker, DigitalOcean, NGINX)
- MaxHealth (portal.maxhealth.ae): Healthcare & FinTech Patient Portal (Node.js, React.js, RabbitMQ, AWS Lambda, S3, Docker, PostgreSQL, JWT, REST APIs)

CERTIFICATIONS:
- AWS Certified Cloud Practitioner (CLF-C02) — Amazon Web Services

SKILLS:
{config.SKILLS}

EXPERIENCE GUIDANCE:
- Total professional experience: {config.YEARS_EXPERIENCE} years.
- Use skill-specific experience from COMMON_ANSWERS when available.
- For resume skills without a specific override, use {config.YEARS_EXPERIENCE} years.
- For unrelated technologies not present in the resume, use 0.
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
        
        # Date of Birth / DOB (DD/MM/YYYY)
        if any(kw in field_lower for kw in ['date of birth', 'dob', 'birth date', 'birthdate']):
            dob = getattr(config, 'DOB', '20/09/2003')
            print(f"Direct match Date of birth: '{dob}'")
            return str(dob)

        # Current / Last drawn salary
        if any(kw in field_lower for kw in ['current', 'present', 'drawn', 'last drawn']) and any(kw in field_lower for kw in ['salary', 'ctc', 'package', 'compensation', 'pay']):
            if any(kw in field_lower for kw in ['lpa', 'lakh']):
                sal = str(config.CURRENT_SALARY).replace(' LPA', '').replace('LPA', '').strip()
            else:
                sal = str(config.ANSWERS.get('current_ctc', '470000'))
            print(f"Direct match Current Salary: '{sal}'")
            return sal

        # Expected annual salary
        if any(kw in field_lower for kw in ['expected', 'desired', 'target']) and any(kw in field_lower for kw in ['salary', 'ctc', 'package', 'compensation', 'pay']):
            if any(kw in field_lower for kw in ['lpa', 'lakh']):
                sal = str(config.EXPECTED_SALARY).replace(' LPA', '').replace('LPA', '').strip()
            else:
                sal = str(config.ANSWERS.get('expected_ctc', '700000'))
            print(f"Direct match Expected Salary: '{sal}'")
            return sal

        # Location / Current Location / Preferred Location
        if any(kw in field_lower for kw in ['current location', 'preferred location', 'location', 'where are you located', 'city']):
            loc = str(config.CITY or config.CURRENT_LOCATION)
            print(f"Direct match Location: '{loc}'")
            return loc

        # Last working day / LWD
        if any(kw in field_lower for kw in ['expected last working day', 'last working day', 'last working date', 'lwd']):
            try:
                notice_days = int(re.sub(r'\D', '', str(config.NOTICE_PERIOD)) or '30')
            except Exception:
                notice_days = 30
            lwd_date = datetime.now() + timedelta(days=notice_days)
            lwd_str = lwd_date.strftime("%d/%m/%Y")
            print(f"Direct match Last Working Day: '{lwd_str}'")
            return lwd_str

        # Notice period
        if any(kw in field_lower for kw in ['notice period', 'notice', 'serving notice', 'availability']):
            ans = str(config.NOTICE_PERIOD)
            print(f"Direct match Notice Period: '{ans}'")
            return ans

        # Academic scores / Marks / Percentage / CGPA
        if any(kw in field_lower for kw in ['12th', 'hsc', 'class 12', 'inter', 'higher secondary']):
            if 'cgpa' in field_lower or 'gpa' in field_lower:
                ans = str(config.ANSWERS.get('12th_cgpa', '8.2'))
                print(f"Direct match 12th CGPA: '{ans}'")
                return ans
            ans = str(config.ANSWERS.get('12th_percentage', '82%'))
            print(f"Direct match 12th Percentage: '{ans}'")
            return ans

        if any(kw in field_lower for kw in ['10th', 'ssc', 'class 10', 'matric']):
            if 'cgpa' in field_lower or 'gpa' in field_lower:
                ans = str(config.ANSWERS.get('10th_cgpa', '8.5'))
                print(f"Direct match 10th CGPA: '{ans}'")
                return ans
            ans = str(config.ANSWERS.get('10th_percentage', '85%'))
            print(f"Direct match 10th Percentage: '{ans}'")
            return ans

        if any(kw in field_lower for kw in ['graduation', 'b.tech', 'college', 'university']):
            if 'cgpa' in field_lower or 'gpa' in field_lower:
                ans = str(config.ANSWERS.get('graduation_cgpa', '7.8'))
                print(f"Direct match Graduation CGPA: '{ans}'")
                return ans
            ans = str(config.ANSWERS.get('graduation_percentage', '78%'))
            print(f"Direct match Graduation Percentage: '{ans}'")
            return ans

        if any(kw in field_lower for kw in ['percentage', 'cgpa', 'marks']):
            if 'cgpa' in field_lower or 'gpa' in field_lower:
                ans = str(config.ANSWERS.get('cgpa', '7.8'))
                print(f"Direct match CGPA: '{ans}'")
                return ans
            ans = str(config.ANSWERS.get('percentage', '80%'))
            print(f"Direct match Percentage: '{ans}'")
            return ans

        # Check for exact match in direct_mappings
        for key, value in direct_mappings.items():
            if key in field_lower:
                print(f"Direct match: '{value}'")
                return str(value)
            
        # Gender / Sex
        if any(kw in field_lower for kw in ['gender', 'sex']):
            g = getattr(config, 'GENDER', 'Male')
            print(f"Direct match Gender: '{g}'")
            return str(g)

        # Work Authorization (ALWAYS YES)
        if any(kw in field_lower for kw in ['authorized to work', 'authorization', 'legally authorized', 'work in the job', 'right to work', 'eligible to work']):
            print("Direct match Work Authorization: 'Yes'")
            return 'Yes'

        # Sponsorship (ALWAYS NO - we don't need it)
        if any(kw in field_lower for kw in ['require sponsorship', 'need sponsorship', 'visa sponsorship']):
            print("Direct match Sponsorship: 'No'")
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
            'available immediately', 'career break', 'career gap', 'gap in employment',
            'employment gap'
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

    def _score_option_for_profile(self, option_text: str, question_text: str = "") -> float:
        """
        Score an option string against user profile, target role, and skills.
        Higher score = better fit for user profile.
        """
        if not option_text:
            return 0.0
            
        opt_lower = option_text.lower()
        score = 1.0
        
        # User skills & role keywords
        user_skills = [
            'mern', 'mern stack', 'react', 'reactjs', 'node', 'nodejs', 'express',
            'expressjs', 'mongodb', 'mongo', 'typescript', 'javascript', 'nextjs',
            'next.js', 'sql', 'postgresql', 'postgres', 'full stack', 'fullstack',
            'frontend', 'backend', 'web development', 'software development',
            'software engineer', 'ai', 'llm', 'rag', 'python', 'rest api'
        ]
        
        # Non-matching / distinct tech domains
        other_domains = [
            'data science', 'machine learning', 'devops', 'salesforce', 'sap',
            'android java', 'ios swift', 'flutter', 'qa automation', 'testing',
            'embedded', 'cybersecurity', 'blockchain', 'mainframe'
        ]
        
        # Check skill matches
        for skill in user_skills:
            if skill in opt_lower:
                score += 2.5
                
        # Check domain penalty
        for domain in other_domains:
            if domain in opt_lower and not any(s in opt_lower for s in ['mern', 'react', 'node', 'full stack', 'web']):
                score -= 2.0
                
        # Experience year match
        years_str = str(config.YEARS_EXPERIENCE)
        if years_str in opt_lower or f"{years_str} year" in opt_lower or f"more than {years_str}" in opt_lower or f">{years_str}" in opt_lower:
            score += 1.5
            
        # Avoid "none of the above" if other positive options exist
        if "none of the above" in opt_lower or "none" in opt_lower:
            score -= 1.0
            
        return score
    
    def _match_option(self, answer: str, options: List[str]) -> str:
        """Match answer to option with strict validation and profile scoring"""
        
        if not options:
            return ""
        
        clean_options = [opt.strip() for opt in options if opt and opt.strip()]
        if not clean_options:
            return ""

        answer = (answer or "").strip()
        answer_lower = answer.lower()
        
        # Rank all options by profile relevance + answer match
        best_option = None
        best_score = -999.0
        
        for option in clean_options:
            profile_score = self._score_option_for_profile(option)
            option_lower = option.lower()
            
            match_boost = 0.0
            if answer_lower and answer_lower == option_lower:
                match_boost = 10.0
            elif answer_lower and (answer_lower in option_lower or option_lower in answer_lower):
                match_boost = 5.0
            elif answer_lower and any(num in re.findall(r'\d+', option) for num in re.findall(r'\d+', answer_lower)):
                match_boost = 3.0

            total_score = profile_score + match_boost
            if total_score > best_score:
                best_score = total_score
                best_option = option

        if best_option:
            print(f"Matched option '{best_option}' (Score: {best_score:.1f}) for answer '{answer}'")
            return best_option

        return clean_options[0]
    
    def is_ollama_available(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get(f"{self.ollama_url}/tags", timeout=5)
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
