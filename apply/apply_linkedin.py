from playwright.sync_api import Page
from apply.apply_common import autofill_standard_form
from database import db
from typing import List, Dict 
import time
import random

def human_like_delay(min_seconds=1, max_seconds=3):
    """Add random delay to mimic human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def scroll_slowly(page: Page):
    """Scroll page slowly like a human"""
    try:
        for _ in range(3):
            page.evaluate("window.scrollBy(0, Math.random() * 300 + 100)")
            time.sleep(random.uniform(0.3, 0.8))
    except:
        pass

def get_new_jobs_only(jobs: List[Dict]) -> List[Dict]:
    """Filter out jobs that are already in the database"""
    applied_links = db.get_applied_job_links()
    new_jobs = []
    
    for job in jobs:
        if job.get("link") not in applied_links:
            new_jobs.append(job)
        else:
            print(f"⏭️  Skipping already applied job: {job.get('role')} @ {job.get('company')}")
    
    print(f"Filtered {len(jobs) - len(new_jobs)} already applied jobs, {len(new_jobs)} new jobs remaining")
    return new_jobs

def attempt_apply(page: Page, job: dict):
    """
    Try to apply to a LinkedIn job with multi-step form support.
    Returns True if recorded/applied, False if skipped.
    """
    link = job.get("link")
    if not link:
        return False
    
    # Double-check if job is already applied (just in case)
    if db.is_job_applied(link):
        print(f"⏭️  Job already applied: {link}")
        return False
    
    try:
        print(f"Navigating to job page...")
        
        # Try multiple times with different strategies if timeout occurs
        page_loaded = False
        for attempt in range(3):
            try:
                if attempt == 0:
                    # First attempt: normal navigation
                    page.goto(link, timeout=45000, wait_until="domcontentloaded")
                elif attempt == 1:
                    # Second attempt: wait for networkidle
                    page.goto(link, timeout=45000, wait_until="networkidle")
                else:
                    # Third attempt: just load without waiting
                    page.goto(link, timeout=45000, wait_until="commit")
                
                page_loaded = True
                break
            except Exception as e:
                print(f"Navigation attempt {attempt + 1} failed: {str(e)[:50]}")
                if attempt < 2:
                    time.sleep(3)
                    continue
                else:
                    print("All navigation attempts failed")
                    return False
        
        if not page_loaded:
            return False
        
        # Human-like behavior: scroll and wait
        human_like_delay(2, 4)
        scroll_slowly(page)
        
        # Wait for page to stabilize
        time.sleep(2)
        
        # Look for Easy Apply button with multiple strategies
        print("Looking for Easy Apply button...")
        
        # Strategy 1: Direct selector with wait
        ea = None
        try:
            ea = page.wait_for_selector(
                "button:has-text('Easy Apply')",
                timeout=10000,
                state="visible"
            )
        except:
            pass
        
        # Strategy 2: Try alternative selectors
        if not ea:
            selectors = [
                "button.jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                "button.jobs-apply-button--top-card",
                "button:has-text('Apply')",
                "div.jobs-apply-button--top-card button"
            ]
            
            for selector in selectors:
                try:
                    ea = page.query_selector(selector)
                    if ea and ea.is_visible():
                        # Check if it's actually "Easy Apply" not "Applied"
                        text = ea.inner_text().lower()
                        if "easy" in text or "apply" in text:
                            if "applied" not in text:
                                break
                    ea = None
                except:
                    continue
        
        if not ea or not ea.is_visible():
            print("No Easy Apply button found")
            # Check if already applied on this page
            page_text = page.content().lower()
            if "applied" in page_text or "already applied" in page_text:
                print("Already applied to this job")
                db.add_job(link, job.get("company"), job.get("role"), status="already_applied")
                return True
            
            # Take screenshot for debugging
            try:
                page.screenshot(path=f"debug_no_button_{int(time.time())}.png")
            except:
                pass
            return False
        
        print("Found Easy Apply button, clicking...")
        
        # Human-like click with slight delay
        human_like_delay(0.5, 1.5)
        
        # Scroll button into view
        try:
            ea.scroll_into_view_if_needed()
            time.sleep(0.5)
        except:
            pass
        
        # Click with retry
        clicked = False
        for click_attempt in range(3):
            try:
                ea.click(timeout=5000)
                clicked = True
                print("Clicked Easy Apply button")
                break
            except Exception as e:
                print(f"Click attempt {click_attempt + 1} failed: {str(e)[:50]}")
                if click_attempt < 2:
                    time.sleep(1)
                    # Try force click
                    try:
                        ea.click(force=True)
                        clicked = True
                        break
                    except:
                        continue
        
        if not clicked:
            print("Failed to click Easy Apply button")
            return False
        
        # Wait for modal to appear with multiple checks
        human_like_delay(2, 4)
        
        modal = None
        modal_selectors = [
            "div.jobs-easy-apply-modal",
            "div[role='dialog']",
            "div.artdeco-modal",
            "div[data-test='modal']"
        ]
        
        for selector in modal_selectors:
            try:
                modal = page.wait_for_selector(
                    selector,
                    timeout=10000,
                    state="visible"
                )
                if modal:
                    print(f"Modal appeared: {selector}")
                    break
            except:
                continue
        
        if not modal:
            print("Easy Apply modal did not appear")
            # Maybe it's already applied or external application
            page_text = page.content().lower()
            if "application sent" in page_text or "already applied" in page_text:
                print("Already applied to this job")
                db.add_job(link, job.get("company"), job.get("role"), status="already_applied")
                return True
            return False
        
        print("Easy Apply modal detected, filling form...")
        
        # Handle multi-step form (up to 10 steps)
        max_steps = 10
        for step in range(max_steps):
            print(f"\n--- Step {step + 1} ---")
            human_like_delay(1.5, 2.5)
            
            # Scroll within modal if needed
            try:
                page.evaluate("""
                    const modal = document.querySelector('.jobs-easy-apply-modal, [role="dialog"]');
                    if (modal) modal.scrollTop = 0;
                """)
            except:
                pass
            
            # Fill out any visible forms
            print("Filling form fields...")
            autofill_standard_form(page)
            
            human_like_delay(1, 2)
            
            # # Try to upload resume
            # print("Checking for resume upload...")
            # upload_resume_if_possible(page)
            
            human_like_delay(1, 2)
            
            # Look for action buttons
            print("Looking for Next/Review/Submit buttons...")
            
            # Submit button (highest priority - final step)
            submit_btn = None
            submit_selectors = [
                "button[aria-label='Submit application']",
                "button:has-text('Submit application')",
                "button:has-text('Submit')",
                "footer button[aria-label*='Submit']"
            ]
            
            for selector in submit_selectors:
                try:
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible() and not btn.is_disabled():
                        submit_btn = btn
                        break
                except:
                    continue
            
            # Review button
            review_btn = None
            if not submit_btn:
                review_selectors = [
                    "button:has-text('Review')",
                    "button[aria-label*='Review']"
                ]
                for selector in review_selectors:
                    try:
                        btn = page.query_selector(selector)
                        if btn and btn.is_visible() and not btn.is_disabled():
                            review_btn = btn
                            break
                    except:
                        continue
            
            # Next button
            next_btn = None
            if not submit_btn and not review_btn:
                next_selectors = [
                    "button:has-text('Next')",
                    "button[aria-label='Continue to next step']",
                    "button[aria-label='Next']",
                    "footer button.artdeco-button--primary"
                ]
                for selector in next_selectors:
                    try:
                        btn = page.query_selector(selector)
                        if btn and btn.is_visible() and not btn.is_disabled():
                            next_btn = btn
                            break
                    except:
                        continue
            
            # Take action based on button found
            if submit_btn:
                print("Found Submit button - submitting application...")
                human_like_delay(1, 2)
                
                try:
                    submit_btn.click(timeout=5000)
                    print("Clicked Submit button")
                except:
                    try:
                        submit_btn.click(force=True)
                    except Exception as e:
                        print(f"Failed to click submit: {e}")
                        return False
                
                # Wait for confirmation
                human_like_delay(3, 5)
                
                # Check for success
                success_indicators = [
                    "application sent",
                    "application submitted",
                    "your application was sent",
                    "successfully submitted",
                    "application complete"
                ]
                
                page_text = page.content().lower()
                is_success = any(indicator in page_text for indicator in success_indicators)
                
                # Also check if modal closed
                try:
                    modal_still_visible = page.is_visible("div.jobs-easy-apply-modal")
                    if not modal_still_visible:
                        is_success = True
                except:
                    pass
                
                if is_success:
                    print("✓ Application submitted successfully!")
                    added = db.add_job(
                        job.get("link"),
                        job.get("company"),
                        job.get("role"),
                        status="applied"
                    )
                    
                    # Try to close modal
                    try:
                        close_btn = page.query_selector("button[aria-label='Dismiss']")
                        if close_btn:
                            close_btn.click()
                    except:
                        pass
                    
                    return added
                else:
                    print("⚠ Submit clicked but couldn't confirm success")
                    # Take screenshot for debugging
                    try:
                        page.screenshot(path=f"debug_submit_{int(time.time())}.png")
                    except:
                        pass
                    return False
            
            elif review_btn:
                print("Clicking Review button...")
                human_like_delay(0.5, 1)
                try:
                    review_btn.click(timeout=5000)
                except:
                    review_btn.click(force=True)
                continue
            
            elif next_btn:
                print("Clicking Next button...")
                human_like_delay(0.5, 1)
                try:
                    next_btn.click(timeout=5000)
                except:
                    next_btn.click(force=True)
                continue
            
            else:
                # No button found - check for errors
                print("⚠ No action button found")
                
                # Check for error messages
                try:
                    errors = page.query_selector_all("div.artdeco-inline-feedback--error")
                    if errors:
                        for err in errors:
                            if err.is_visible():
                                print(f"Error: {err.inner_text()}")
                except:
                    pass
                
                # Check for required fields
                try:
                    required = page.query_selector_all("input[required], select[required], textarea[required]")
                    empty_required = []
                    for field in required:
                        if field.is_visible():
                            val = field.input_value() if hasattr(field, 'input_value') else None
                            if not val:
                                empty_required.append(field)
                    
                    if empty_required:
                        print(f"⚠ {len(empty_required)} required fields still empty")
                        # Try to fill again
                        autofill_standard_form(page)
                        time.sleep(2)
                        continue
                except:
                    pass
                
                print("⚠ Cannot proceed with application")
                break
        
        print("⚠ Reached max steps or couldn't complete application")
        return False
        
    except Exception as e:
        print(f"Error in LinkedIn apply: {e}")
        import traceback
        traceback.print_exc()
    
    return False