"""
utils.py
Common utility functions for job applications.
"""
import time
import random
import os
from typing import Any
from playwright.sync_api import Page


def human_delay(min_seconds: float = 1, max_seconds: float = 3) -> None:
    """Add random delay to mimic human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def take_debug_screenshot(page: Page, prefix: str = "debug") -> str:
    """Take a screenshot for debugging purposes. Returns filepath."""
    try:
        # Create debug directory if it doesn't exist
        debug_dir = "debug_screenshots"
        os.makedirs(debug_dir, exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(debug_dir, filename)
        
        page.screenshot(path=filepath, full_page=True)
        print(f"📸 Screenshot saved: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"⚠ Failed to take screenshot: {e}")
        return ""


def extract_button_text(button: Any) -> str:
    """Extract text from button element."""
    try:
        return button.text_content().lower().strip()
    except Exception:
        return ""


def is_element_visible(element: Any) -> bool:
    """Check if element is visible and enabled."""
    try:
        return element.is_visible() and not element.is_disabled()
    except Exception:
        return False


def wait_for_stable_page(page: Page, timeout: float = 5) -> None:
    """Wait for page to stabilize after actions."""
    time.sleep(timeout)


def save_page_html(page: Page, prefix: str = "debug") -> str:
    """Save page HTML for debugging."""
    try:
        debug_dir = "debug_html"
        os.makedirs(debug_dir, exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.html"
        filepath = os.path.join(debug_dir, filename)
        
        html_content = page.content()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"📄 HTML saved: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"⚠ Failed to save HTML: {e}")
        return ""


def scroll_to_element(element) -> bool:
    """Scroll element into view."""
    try:
        element.scroll_into_view_if_needed()
        time.sleep(0.5)
        return True
    except Exception:
        return False