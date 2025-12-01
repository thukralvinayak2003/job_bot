"""
config.py
Loads environment variables from .env and provides a config object.
"""

import os
from dotenv import load_dotenv
from common_answer import COMMON_ANSWERS

load_dotenv()  # load .env in project root

class Config:
    EMAIL = os.getenv("EMAIL", "")
    PHONE = os.getenv("PHONE", "")
    RESUME_PATH = os.getenv("RESUME_PATH", "")
    JOB_KEYWORDS = os.getenv("JOB_KEYWORDS", "")  # comma separated
    LOCATION = os.getenv("LOCATION", "")
    USER_DATA_DIR = os.getenv("USER_DATA_DIR", "data/playwright_profiles")
    FULL_NAME = "Your Full Name"
    LOCATION = "Amritsar, Punjab, India"
    # Optional proxy (e.g. "http://1.2.3.4:3128") to route traffic through
    PROXY = os.getenv("PROXY", "")
    # Optional User-Agent string to present to sites
    USER_AGENT = os.getenv("USER_AGENT", "")
    # Randomized delay between job operations (seconds)
    DELAY_MIN = float(os.getenv("DELAY_MIN", "1.0"))
    DELAY_MAX = float(os.getenv("DELAY_MAX", "3.0"))
    # playwight headless default, can be changed when launching browser
    HEADLESS = os.getenv("HEADLESS", "true").lower() in ("1", "true", "yes")
    ANSWERS = COMMON_ANSWERS
config = Config()
