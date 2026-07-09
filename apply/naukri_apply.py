from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from typing import Dict
from datetime import datetime
import os
import time

from .utils.human_behavior import human_like_delay
from .utils.job_filtering import is_job_already_applied
from ai_form_filler import ai_filler
from database import db


class NaukriApply:
    """Main Naukri application orchestrator."""

    APPLY_BUTTON_SELECTORS = [
        "button:has-text('Apply')",
        "button:has-text('Apply Now')",
        "button.apply-button",
        ".apply-button",
        "#apply-button",
        "[data-ga-track*='apply']",
        "a:has-text('Apply')",
    ]

    LOGIN_INDICATORS = [
        "a:has-text('Logout')",
        "a:has-text('My Naukri')",
        "div.nI-gNb-drawer__bars",
        "img[alt*='profile']",
        "a[href*='mnjuser/profile']",
        "a[href*='mnjuser/homepage']",
    ]

    SUCCESS_INDICATORS = [
        "successfully applied",
        "application sent",
        "applied successfully",
        "you have applied",
        "already applied",
        "application submitted",
    ]

    QUESTION_FLOW_SELECTORS = [
        "div.chatbot",
        "div.botMsg",
        "div[class*='question']",
        "form",
        "div[role='dialog']",
        ".applyForm",
    ]

    ACTION_BUTTON_TEXT = [
        "Submit",
        "Save",
        "Save and continue",
        "Continue",
        "Next",
        "Apply",
        "Send",
        "Done",
    ]

    def __init__(self, config):
        self.config = config
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.external_links_file = os.path.join(
            "list",
            f"naukri_external_apply_links_{timestamp}.txt",
        )

    def attempt_apply(self, page: Page, job: Dict) -> bool:
        link = job.get("link")
        if not link:
            print("No Naukri job link provided")
            return False

        print(f"\n{'=' * 70}")
        print(f"Applying on Naukri: {job.get('role', 'N/A')}")
        print(f"Company: {job.get('company', 'N/A')}")
        print(f"Link: {link}")
        print(f"{'=' * 70}")

        if is_job_already_applied(link):
            print(f"Job already recorded: {link}")
            return False

        try:
            if not self._navigate_to_job_page(page, link):
                return False

            if not self.is_logged_in(page):
                print("Not logged in to Naukri")
                return False

            if self._is_success(page):
                return self._record_success(job, status="already_applied")

            apply_button = self._find_apply_button(page)
            if not apply_button:
                print("No Naukri Apply button found")
                self._save_external_apply_links(page, job, "no_naukri_apply_button")
                return False

            if not self._click_apply_button(apply_button):
                return False

            success = self._handle_application_flow(page)
            if success:
                return self._record_success(job)

            print("Naukri application flow did not complete")
            return False

        except PlaywrightTimeout as e:
            print(f"Naukri timeout: {e}")
            return False
        except Exception as e:
            print(f"Error during Naukri application: {e}")
            import traceback
            traceback.print_exc()
            return False

    def is_logged_in(self, page: Page) -> bool:
        try:
            for selector in self.LOGIN_INDICATORS:
                try:
                    element = page.query_selector(selector)
                    if element and element.is_visible():
                        return True
                except Exception:
                    continue

            current_url = page.url.lower()
            if "login" in current_url:
                return False

            page_text = page.content().lower()
            return "logout" in page_text or "my naukri" in page_text
        except Exception:
            return False

    def _navigate_to_job_page(self, page: Page, link: str) -> bool:
        try:
            print("Loading Naukri job page...")
            page.goto(link, wait_until="domcontentloaded", timeout=45000)
            human_like_delay(3, 5)
            self._close_popups(page)
            return True
        except Exception as e:
            print(f"Failed to load Naukri job page: {e}")
            return False

    def _close_popups(self, page: Page):
        selectors = [
            "button[aria-label='close']",
            "button[aria-label='Close']",
            ".crossIcon",
            ".close",
        ]
        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    element.click(timeout=1500)
                    time.sleep(0.5)
            except Exception:
                continue

    def _find_apply_button(self, page: Page):
        for selector in self.APPLY_BUTTON_SELECTORS:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if not element.is_visible() or not element.is_enabled():
                        continue
                    text = (element.inner_text() or "").strip().lower()
                    if "applied" in text:
                        return None
                    if "apply" in text:
                        return element
            except Exception:
                continue
        return None

    def _click_apply_button(self, button) -> bool:
        try:
            print("Found Naukri Apply button, clicking...")
            button.scroll_into_view_if_needed()
            human_like_delay(1, 2)
            button.click(timeout=5000)
            human_like_delay(3, 5)
            return True
        except Exception as e:
            print(f"Failed to click Naukri Apply button: {e}")
            return False

    def _handle_application_flow(self, page: Page) -> bool:
        for step in range(8):
            print(f"Naukri application step {step + 1}/8")
            self._close_popups(page)

            if self._is_success(page):
                print("Naukri application success detected")
                return True

            if self._is_external_redirect(page):
                print("Naukri redirected to an external employer site; skipping automation")
                self._save_external_apply_links(page, {}, "external_redirect")
                return False

            chat_filled = self._fill_chat_question(page)
            if chat_filled:
                print("Filled Naukri chat question")
                human_like_delay(1, 2)
            elif self._has_question_flow(page):
                filled = self._fill_visible_fields(page)
                print(f"Filled {filled} Naukri fields")
                human_like_delay(1, 2)

            button = self._find_action_button(page)
            if not button:
                if step == 0 and self._is_success(page):
                    return True
                print("No next/submit button found in Naukri flow")
                return False

            if not self._click_flow_button(page, button):
                return False

            human_like_delay(2, 4)

        print("Reached maximum Naukri application steps")
        return self._is_success(page)

    def _has_question_flow(self, page: Page) -> bool:
        try:
            for selector in self.QUESTION_FLOW_SELECTORS:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    return True
            return False
        except Exception:
            return False

    def _fill_chat_question(self, page: Page) -> bool:
        try:
            input_box = self._find_chat_input(page)
            if not input_box:
                return False

            if self._is_field_filled(input_box, "text"):
                return False

            question = self._get_latest_chat_question(page)
            if not question:
                question = self._get_field_context(page, input_box)

            if not question:
                return False

            answer = ai_filler.generate_answer(question, "text")
            if not answer:
                return False

            input_box.fill(str(answer))
            return True
        except Exception as e:
            print(f"Could not fill Naukri chat question: {e}")
            return False

    def _find_chat_input(self, page: Page):
        selectors = [
            "input[placeholder*='Type message']",
            "textarea[placeholder*='Type message']",
            "input[placeholder*='message']",
            "textarea[placeholder*='message']",
            "div[role='dialog'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
            "div[role='dialog'] textarea",
        ]
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible() and element.is_enabled():
                        return element
            except Exception:
                continue
        return None

    def _get_latest_chat_question(self, page: Page) -> str:
        try:
            questions = page.evaluate(
                """
                () => {
                    const selectors = [
                        '.botMsg',
                        '[class*="bot"]',
                        '[class*="chat"]',
                        '[class*="question"]',
                        'div[role="dialog"] div'
                    ];
                    const texts = [];
                    const seen = new Set();

                    for (const selector of selectors) {
                        for (const el of document.querySelectorAll(selector)) {
                            const style = window.getComputedStyle(el);
                            const rect = el.getBoundingClientRect();
                            if (style.display === 'none' || style.visibility === 'hidden') continue;
                            if (rect.width === 0 || rect.height === 0) continue;

                            const text = (el.innerText || '').trim();
                            if (!text || seen.has(text)) continue;
                            seen.add(text);

                            if (text.includes('?') || /how many|years|experience|ctc|notice|salary|available|relocat/i.test(text)) {
                                texts.push(text);
                            }
                        }
                    }

                    return texts.slice(-1)[0] || '';
                }
                """
            )
            return (questions or "").strip()
        except Exception:
            return ""

    def _fill_visible_fields(self, page: Page) -> int:
        fields = page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='button']), "
            "select, textarea"
        )
        filled_count = 0
        processed_radio_groups = set()

        for field in fields:
            try:
                if not field.is_visible() or not field.is_enabled():
                    continue

                tag_name = field.evaluate("el => el.tagName.toLowerCase()")
                field_type = (field.get_attribute("type") or tag_name).lower()

                if field_type == "radio":
                    group_name = field.get_attribute("name")
                    if not group_name or group_name in processed_radio_groups:
                        continue
                    processed_radio_groups.add(group_name)
                    if self._fill_radio_group(page, group_name):
                        filled_count += 1
                    continue

                if self._is_field_filled(field, field_type):
                    continue

                context = self._get_field_context(page, field)
                options = self._get_select_options(field) if tag_name == "select" else None
                answer = ai_filler.generate_answer(context, field_type, options)
                if not answer:
                    continue

                if tag_name == "select":
                    success = self._fill_select(field, answer, options or [])
                elif field_type == "checkbox":
                    success = self._fill_checkbox(field, answer)
                else:
                    success = self._fill_text(field, answer)

                if success:
                    filled_count += 1
                    time.sleep(0.3)
            except Exception as e:
                print(f"Skipping Naukri field due to error: {e}")

        return filled_count

    def _get_field_context(self, page: Page, field) -> str:
        try:
            return field.evaluate(
                """
                el => {
                    const parts = [];
                    const id = el.id;
                    const name = el.getAttribute('name');
                    const placeholder = el.getAttribute('placeholder');
                    const aria = el.getAttribute('aria-label');
                    const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                    const parentLabel = el.closest('label');
                    const container = el.closest('div, li, section, form');

                    if (label?.innerText) parts.push(label.innerText);
                    if (parentLabel?.innerText) parts.push(parentLabel.innerText);
                    if (aria) parts.push(aria);
                    if (placeholder) parts.push(placeholder);
                    if (name) parts.push(name);
                    if (container?.innerText) parts.push(container.innerText.slice(0, 500));

                    return [...new Set(parts.map(p => p.trim()).filter(Boolean))].join(' | ');
                }
                """
            )
        except Exception:
            return ""

    def _is_field_filled(self, field, field_type: str) -> bool:
        try:
            if field_type in ["checkbox", "radio"]:
                return field.is_checked()
            value = field.input_value()
            return bool(value and value.strip())
        except Exception:
            return False

    def _get_select_options(self, field):
        try:
            options = []
            for option in field.query_selector_all("option"):
                text = option.inner_text().strip()
                value = option.get_attribute("value") or ""
                if text and value:
                    options.append(text)
            return options
        except Exception:
            return []

    def _fill_text(self, field, answer: str) -> bool:
        try:
            field.fill(str(answer))
            return True
        except Exception:
            return False

    def _fill_checkbox(self, field, answer: str) -> bool:
        try:
            should_check = str(answer).strip().lower() in ["yes", "true", "1", "on"]
            field.set_checked(should_check)
            return True
        except Exception:
            return False

    def _fill_select(self, field, answer: str, options) -> bool:
        try:
            field.select_option(label=answer, timeout=2000)
            return True
        except Exception:
            pass

        answer_lower = str(answer).lower().strip()
        for option in options:
            option_lower = option.lower().strip()
            if answer_lower in option_lower or option_lower in answer_lower:
                try:
                    field.select_option(label=option, timeout=2000)
                    return True
                except Exception:
                    continue
        return False

    def _fill_radio_group(self, page: Page, group_name: str) -> bool:
        try:
            options = page.evaluate(
                """
                name => Array.from(document.querySelectorAll(`input[type="radio"][name="${name}"]`))
                    .map(radio => {
                        const id = radio.id;
                        const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                        const parentLabel = radio.closest('label');
                        return (label?.innerText || parentLabel?.innerText || radio.value || '').trim();
                    })
                    .filter(Boolean)
                """,
                group_name,
            )
            context = f"Radio question {group_name}. Options: {', '.join(options)}"
            answer = ai_filler.generate_answer(context, "radio", options)
            if not answer:
                return False

            return page.evaluate(
                """
                ({ name, answer }) => {
                    const radios = Array.from(document.querySelectorAll(`input[type="radio"][name="${name}"]`));
                    const target = answer.toLowerCase().trim();
                    let best = null;
                    let bestScore = 0;

                    for (const radio of radios) {
                        const id = radio.id;
                        const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                        const parentLabel = radio.closest('label');
                        const text = (label?.innerText || parentLabel?.innerText || radio.value || '').trim();
                        const normalized = text.toLowerCase();
                        let score = 0;

                        if (normalized === target) score = 1;
                        else if (normalized.includes(target) || target.includes(normalized)) score = 0.8;

                        if (score > bestScore) {
                            best = radio;
                            bestScore = score;
                        }
                    }

                    if (!best && radios.length) best = radios[0];
                    if (!best) return false;

                    best.checked = true;
                    best.dispatchEvent(new Event('input', { bubbles: true }));
                    best.dispatchEvent(new Event('change', { bubbles: true }));
                    best.click();
                    return true;
                }
                """,
                {"name": group_name, "answer": answer},
            )
        except Exception:
            return False

    def _find_action_button(self, page: Page):
        for text in self.ACTION_BUTTON_TEXT:
            selectors = [
                f"button:has-text('{text}')",
                f"input[type='button'][value*='{text}']",
                f"input[type='submit'][value*='{text}']",
                f"a:has-text('{text}')",
            ]
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible() and element.is_enabled():
                            return element
                except Exception:
                    continue
        return None

    def _click_flow_button(self, page: Page, button) -> bool:
        try:
            text = (button.inner_text() or button.get_attribute("value") or "button").strip()
            print(f"Clicking Naukri flow button: {text}")
            button.scroll_into_view_if_needed()
            button.click(timeout=5000)
            return True
        except Exception as e:
            print(f"Failed to click Naukri flow button: {e}")
            try:
                page.keyboard.press("Enter")
                return True
            except Exception:
                return False

    def _is_success(self, page: Page) -> bool:
        try:
            text = page.content().lower()
            return any(indicator in text for indicator in self.SUCCESS_INDICATORS)
        except Exception:
            return False

    def _is_external_redirect(self, page: Page) -> bool:
        try:
            url = page.url.lower()
            return "naukri.com" not in url and "ambitionbox.com" not in url
        except Exception:
            return False

    def _save_external_apply_links(self, page: Page, job: Dict, reason: str):
        links = self._extract_external_apply_links(page)
        if not links:
            fallback_link = page.url if self._is_external_redirect(page) else job.get("link")
            links = [fallback_link] if fallback_link else []

        if not links:
            print("No external apply links found to save")
            return

        os.makedirs("list", exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.external_links_file, "a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {reason}\n")
            file.write(f"Role: {job.get('role', 'Unknown')}\n")
            file.write(f"Company: {job.get('company', 'Unknown')}\n")
            file.write(f"Naukri URL: {job.get('link', page.url)}\n")
            file.write("External apply links:\n")
            for link in links:
                file.write(f"- {link}\n")
            file.write("\n")

        print(f"Saved external apply link(s) to {self.external_links_file}")

    def _extract_external_apply_links(self, page: Page):
        try:
            links = page.evaluate(
                """
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(anchor => ({
                        href: anchor.href,
                        text: (anchor.innerText || anchor.getAttribute('aria-label') || '').trim()
                    }))
                """
            )
        except Exception:
            return []

        external_links = []
        fallback_external_links = []
        priority_terms = ["apply", "career", "job", "opening"]

        for item in links:
            href = (item.get("href") or "").strip()
            text = (item.get("text") or "").lower()
            href_lower = href.lower()

            if not href_lower.startswith(("http://", "https://")):
                continue
            if any(domain in href_lower for domain in ["naukri.com", "ambitionbox.com"]):
                continue
            if any(skip in href_lower for skip in ["mailto:", "tel:", "javascript:"]):
                continue

            if href not in fallback_external_links:
                fallback_external_links.append(href)

            looks_relevant = any(term in text or term in href_lower for term in priority_terms)
            if looks_relevant and href not in external_links:
                external_links.append(href)

        return external_links or fallback_external_links

    def _record_success(self, job: Dict, status: str = "applied") -> bool:
        db.add_job(
            job.get("link"),
            job.get("company", "Unknown"),
            job.get("role", "Unknown"),
            status=status,
        )
        print(f"Naukri application recorded as {status}")
        return True
