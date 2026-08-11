"""
config.py
Loads environment variables from .env and provides a config object.
"""

import os
from dotenv import load_dotenv
from common_answer import COMMON_ANSWERS

load_dotenv()  # load .env in project root

class Config:
    EMAIL = os.getenv("EMAIL", "vinayakthukral2003@gmail.com")
    PHONE = os.getenv("PHONE", "6284263279")
    RESUME_PATH = os.getenv("RESUME_PATH", r"c:\Users\thukr\OneDrive\Desktop\Vs code\PhaedraPlus\multi-job-autobot\multi-autoapply-lite\Vinayak_Thukral_ResumeV1.pdf")
    JOB_KEYWORDS = os.getenv("JOB_KEYWORDS", "")  # comma separated
    LOCATION = os.getenv("LOCATION", "Amritsar, Punjab, India")
    CURRENT_LOCATION = "Amritsar, Punjab, India"
    USER_DATA_DIR = os.getenv("USER_DATA_DIR", "data/playwright_profiles")
    FULL_NAME = "Vinayak Thukral"
    
    # Optional proxy (e.g. "http://1.2.3.4:3128") to route traffic through
    PROXY = os.getenv("PROXY", "")
    # Optional User-Agent string to present to sites
    USER_AGENT = os.getenv("USER_AGENT", "")
    # Randomized delay between job operations (seconds)
    DELAY_MIN = float(os.getenv("DELAY_MIN", "1.0"))
    DELAY_MAX = float(os.getenv("DELAY_MAX", "3.0"))
    # playwright headless default, can be changed when launching browser
    HEADLESS = os.getenv("HEADLESS", "true").lower() in ("1", "true", "yes")
    
    ANSWERS = COMMON_ANSWERS
    YEARS_EXPERIENCE = os.getenv("YEARS_EXPERIENCE", "3")
    CURRENT_SALARY = os.getenv("CURRENT_SALARY", "4.7 LPA")
    EXPECTED_SALARY = os.getenv("EXPECTED_SALARY", "7 LPA")
    ADDRESS = "16-B Rani Ka Bagh Amritsar Punjab India 143001"
    POSTAL_CODE = "143001"
    CITY = "Amritsar"
    STATE = "Punjab"
    COUNTRY = "India"
    NOTICE_PERIOD = os.getenv("NOTICE_PERIOD", "30")
    DOB = "21/08/2003"
    GENDER = "Male"
    EDUCATION = os.getenv("EDUCATION", "B.Tech, Computer Science Engineering, Amritsar Group of Colleges, CGPA: 7.8 (2025)")
    SKILLS = os.getenv(
        "SKILLS",
        "Node.js, TypeScript, Express.js, REST APIs, GraphQL, RabbitMQ, JWT, RBAC, "
        "React.js, Next.js, Redux, Tailwind CSS, React Native, PWA, "
        "Docker, CI/CD, AWS (Lambda, Amplify, IoT Core, EC2, S3), NGINX, DigitalOcean, Turborepo, "
        "PostgreSQL, MongoDB, Firebase, Prisma ORM, Redis, SQL, Microservices, System Design"
    )
    
    CURRENT_COMPANY = "Sisgain"
    PREVIOUS_COMPANIES = "Virtueaze, IIT Ropar"
    CERTIFICATIONS = "AWS Certified Cloud Practitioner (CLF-C02)"
    PROJECTS = "FarmFlow (Smart Farming & IoT), WebbWe (Custom CMS), MaxHealth (Healthcare & FinTech Portal)"
    
    # LinkedIn and GitHub
    LINKEDIN = "https://www.linkedin.com/in/vinayak-thukral-902174177/"
    GITHUB = "https://github.com/thukralvinayak2003"
    PORTFOLIO = ""
    TARGET_ROLE = "Senior Software Developer / Backend & Full Stack Engineering"

config = Config()
