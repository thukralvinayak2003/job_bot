import time
import random

def human_like_delay(min_seconds=1, max_seconds=3):
    """Add random delay to mimic human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def scroll_slowly(page, scroll_count=3, min_scroll=100, max_scroll=400):
    """Scroll page slowly like a human"""
    try:
        for _ in range(scroll_count):
            page.evaluate(f"window.scrollBy(0, Math.random() * {max_scroll - min_scroll} + {min_scroll})")
            time.sleep(random.uniform(0.3, 0.8))
    except:
        pass

def scroll_element_into_view(element):
    """Scroll element into view if needed"""
    try:
        element.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.3, 0.8))
    except:
        pass