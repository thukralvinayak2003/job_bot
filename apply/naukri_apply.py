from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from typing import Dict
from datetime import datetime
import os
import time
import json
import urllib.parse

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

    ACP_SUCCESS_CODES = {200, 201, 202}
    MAX_CHATBOT_TURNS = 10

    QUESTION_FLOW_SELECTORS = [
        "div.chatbot",
        "div.botMsg",
        "div[class*='question']",
        "form",
        "div[role='dialog']",
        ".applyForm",
        "div[class*='drawer']",
        "div[class*='side-panel']",
        "div[class*='chatbot']",
        "div[class*='modal']",
        "div[class*='popup']",
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

    def _wait_for_drawer_or_panel(self, page: Page, timeout_seconds=5) -> bool:
        """Waits for side drawer / chatbot panel container to appear after clicking Apply."""
        start = time.time()
        print("Waiting for side drawer / chatbot panel to appear...")
        while time.time() - start < timeout_seconds:
            if self._is_success(page):
                return True
            for target in self._get_all_targets(page):
                try:
                    found = target.evaluate("""
                        () => {
                            const dialogs = document.querySelectorAll('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"], .applyForm, div[class*="modal"]');
                            for (const d of dialogs) {
                                const style = window.getComputedStyle(d);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    if found:
                        print("Detected open side drawer / modal dialog")
                        return True
                except Exception:
                    continue
            time.sleep(0.5)
        print("Side drawer / modal wait complete")
        return False

    def _process_naukri_side_drawer(self, page: Page) -> bool:
        """
        Directly scans and processes Naukri side drawers, chatbot panels, and recruiter question forms.
        Extracts recruiter questions, generates AI answers, fills input fields (handling React state),
        and clicks submit/save buttons.
        """
        targets = self._get_all_targets(page)
        for target in targets:
            try:
                drawer_info = target.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"], .applyForm, div[class*="modal"], div[class*="apply"], div[class*="popup"], div[class*="overlay"], form');
                        let container = null;
                        for (const d of dialogs) {
                            const style = window.getComputedStyle(d);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                container = d;
                                break;
                            }
                        }
                        if (!container) container = document.body;

                        const inputs = Array.from(container.querySelectorAll('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="submit"]):not([type="button"]), textarea, [contenteditable="true"]'));
                        let activeInput = null;
                        let inputIndex = -1;

                        inputs.forEach((inp, idx) => {
                            const style = window.getComputedStyle(inp);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                activeInput = inp;
                                inputIndex = idx;
                            }
                        });

                        const bubbles = Array.from(container.querySelectorAll('p, span, div, label'))
                            .map(el => (el.innerText || '').trim())
                            .filter(t => t.length > 3 &&
                                        !t.toLowerCase().includes('hi vinayak') &&
                                        !t.toLowerCase().includes('thank you for showing interest') &&
                                        !t.toLowerCase().includes('type message') &&
                                        !t.toLowerCase().includes('type here') &&
                                        (t.includes('?') || /working|last day|lwd|notice|ctc|salary|experience|years|availability|join|location/i.test(t)));

                        const questionText = bubbles.length > 0 ? bubbles[bubbles.length - 1] : 'Recruiter Question';

                        const btns = Array.from(container.querySelectorAll('button, input[type="submit"], input[type="button"], a, div[class*="send"], div[class*="btn"], .sendBtn, .saveBtn, div[role="button"], span[role="button"]'));
                        let buttonText = '';
                        for (const btn of btns) {
                            const style = window.getComputedStyle(btn);
                            const txt = (btn.innerText || btn.getAttribute('value') || '').trim();
                            if (style.display !== 'none' && style.visibility !== 'hidden' && txt.length > 0 && /save|submit|apply|send|continue|next/i.test(txt)) {
                                buttonText = txt;
                                break;
                            }
                        }

                        return {
                            hasContainer: true,
                            hasInput: activeInput !== null,
                            inputIndex: inputIndex,
                            questionText: questionText,
                            buttonText: buttonText
                        };
                    }
                """)

                if not drawer_info or not drawer_info.get("hasContainer"):
                    continue

                print(f"Found active Naukri side drawer container: {drawer_info}")

                if drawer_info.get("hasInput"):
                    q_text = drawer_info.get("questionText", "Recruiter Question")
                    print(f"Detected drawer question: '{q_text}'")

                    answer = ai_filler.generate_answer(q_text, "text")
                    if not answer:
                        q_lower = q_text.lower()
                        if any(kw in q_lower for kw in ['notice', 'serving', 'availability', 'last working']):
                            answer = self.config.NOTICE_PERIOD
                        elif any(kw in q_lower for kw in ['ctc', 'salary', 'package', 'compensation']):
                            answer = getattr(self.config, 'CURRENT_SALARY', '4.7 LPA')
                        elif any(kw in q_lower for kw in ['experience', 'years']):
                            answer = getattr(self.config, 'YEARS_EXPERIENCE', '3')
                        else:
                            answer = "Yes"

                    print(f"AI Form Filler generated answer: '{answer}'")

                    input_idx = drawer_info.get("inputIndex", 0)

                    filled_ok = target.evaluate("""
                        ({ inputIdx, answer }) => {
                            const container = document.querySelector('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"], .applyForm, div[class*="modal"], div[class*="apply"], form') || document.body;
                            const inputs = Array.from(container.querySelectorAll('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="submit"]):not([type="button"]), textarea, [contenteditable="true"]'))
                                .filter(inp => {
                                    const style = window.getComputedStyle(inp);
                                    return style.display !== 'none' && style.visibility !== 'hidden';
                                });
                            const inp = inputs[inputIdx] || inputs[0];
                            if (!inp) return false;

                            inp.focus();
                            inp.click();
                            if (inp.isContentEditable) {
                                inp.innerText = answer;
                            } else {
                                const proto = inp.tagName.toLowerCase() === 'textarea' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                                if (setter) setter.call(inp, answer);
                                else inp.value = answer;
                            }

                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                            inp.dispatchEvent(new Event('blur', { bubbles: true }));

                            inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                            inp.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                            inp.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                            return true;
                        }
                    """, {"inputIdx": input_idx, "answer": str(answer)})

                    if filled_ok:
                        print("Filled side drawer text field successfully")
                        time.sleep(1.0)

                clicked_btn = target.evaluate("""
                    () => {
                        const container = document.querySelector('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"], .applyForm, div[class*="modal"], div[class*="apply"], form') || document.body;
                        const btns = Array.from(container.querySelectorAll('button, input[type="submit"], input[type="button"], a, div[class*="send"], div[class*="btn"], .sendBtn, .saveBtn, div[role="button"], span[role="button"]'));
                        for (const btn of btns) {
                            const style = window.getComputedStyle(btn);
                            const txt = (btn.innerText || btn.getAttribute('value') || '').trim();
                            if (style.display !== 'none' && style.visibility !== 'hidden' && txt.length > 0 && /save|submit|apply|send|continue|next/i.test(txt)) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)

                if clicked_btn:
                    print("Clicked side drawer action button successfully")
                    time.sleep(2.0)
                    return True
                elif drawer_info.get("hasInput"):
                    return True

            except Exception as e:
                print(f"Error processing side drawer target: {e}")
                continue

        return False

    def _handle_application_flow(self, page: Page) -> bool:
        self._wait_for_drawer_or_panel(page, timeout_seconds=5)

        # ── Try chatbot state machine first ────────────────────────────────────
        # If a chatbot-style single-Q-at-a-time input is present, hand off
        # entirely to the state machine.  Do NOT also run the generic filler
        # afterward — that causes a double-submit which corrupts the panel state.
        targets = self._get_all_targets(page)
        chatbot_target, _ = self._detect_chatbot_panel(targets)
        if chatbot_target:
            print("Chatbot panel detected — running chatbot state machine")
            result = self._run_chatbot_state_machine(page)
            if self._is_external_redirect(page):
                self._save_external_apply_links(page, {}, "external_redirect")
            return result

        # ── Generic form / modal filler ────────────────────────────────────────
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

            drawer_processed = self._process_naukri_side_drawer(page)
            if drawer_processed:
                human_like_delay(2, 3)
                if self._is_success(page):
                    return True
                continue

            drawer_filled = self._fill_drawer_questions(page)
            if drawer_filled:
                print("Filled Naukri drawer/panel question(s)")
                human_like_delay(1, 2)
            elif self._has_question_flow(page):
                filled = self._fill_visible_fields(page)
                print(f"Filled {filled} Naukri fields")
                human_like_delay(1, 2)

            button = self._find_action_button(page)
            if not button:
                human_like_delay(2, 3)
                if self._is_success(page):
                    return True
                print("No next/submit button found in Naukri flow")
                return False

            if not self._click_flow_button(page, button):
                return False

            human_like_delay(2, 4)

        print("Reached maximum Naukri application steps")
        return self._is_success(page)

    def _get_all_targets(self, page: Page):
        """Returns all active pages and frames (latest first) to scan tabs, popups, and iframes."""
        targets = []
        try:
            pages = list(page.context.pages) if page.context else [page]
        except Exception:
            pages = [page]

        for p in reversed(pages):
            try:
                if p.is_closed():
                    continue
                targets.append(p)
                for f in p.frames:
                    if f != p.main_frame and not f.is_detached():
                        targets.append(f)
            except Exception:
                continue
        return targets or [page]

    def _fill_drawer_questions(self, page: Page) -> bool:
        """
        Detects and answers recruiter questions inside Naukri side drawers, dialogs, and chatbot cards.
        Handles standard radio input groups, custom option cards, and text/date inputs across tabs & frames.
        """
        any_filled = False
        targets = self._get_all_targets(page)

        for target in targets:
            try:
                questions_data = target.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"], .applyForm, div[class*="modal"]');
                        let container = null;
                        for (const d of dialogs) {
                            const style = window.getComputedStyle(d);
                            const rect = d.getBoundingClientRect();
                            if (style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0) {
                                container = d;
                                break;
                            }
                        }
                        if (!container) container = document.body;

                        const results = [];

                        // 1. Radio Input Groups (standard input[type="radio"])
                        const radios = Array.from(container.querySelectorAll('input[type="radio"]'));
                        const radioGroups = {};

                        radios.forEach((radio, idx) => {
                            let groupName = radio.getAttribute('name');
                            if (!groupName || groupName.trim() === '') {
                                const parent = radio.closest('fieldset, div[class*="question"], div[class*="radio"], div[class*="wrapper"], ul, form') || radio.parentElement;
                                groupName = 'group_' + (parent ? Array.from(container.querySelectorAll('*')).indexOf(parent) : idx);
                            }
                            if (!radioGroups[groupName]) radioGroups[groupName] = [];

                            let labelText = '';
                            if (radio.id) {
                                const lbl = container.querySelector(`label[for="${CSS.escape(radio.id)}"]`);
                                if (lbl) labelText = lbl.innerText;
                            }
                            if (!labelText) {
                                const parentLabel = radio.closest('label');
                                if (parentLabel) labelText = parentLabel.innerText;
                            }
                            if (!labelText && radio.parentElement) {
                                labelText = radio.parentElement.innerText;
                            }
                            if (!labelText) labelText = radio.value || '';

                            radioGroups[groupName].push({
                                id: radio.id || '',
                                value: radio.value || '',
                                text: (labelText || '').trim(),
                                checked: radio.checked,
                                index: idx
                            });
                        });

                        for (const gName in radioGroups) {
                            const items = radioGroups[gName];
                            if (!items.length) continue;
                            if (items.some(it => it.checked)) continue;

                            let qText = '';
                            const firstElem = radios[items[0].index];
                            const qContainer = firstElem ? (firstElem.closest('div[class*="question"], div[class*="block"], div[class*="wrap"], div[role="dialog"], fieldset') || firstElem.parentElement) : null;
                            
                            if (qContainer) {
                                const headers = qContainer.querySelectorAll('div[class*="head"], div[class*="title"], div[class*="text"], div[class*="botMsg"], span[class*="question"], label[class*="question"], p, h2, h3, h4');
                                for (const h of headers) {
                                    const txt = (h.innerText || '').trim();
                                    if (txt && (txt.includes('?') || txt.length > 5) && !items.some(it => txt === it.text)) {
                                        qText = txt;
                                        break;
                                    }
                                }
                                if (!qText) {
                                    let raw = qContainer.innerText || '';
                                    items.forEach(it => { if (it.text) raw = raw.replace(it.text, ''); });
                                    qText = raw.split('\\n').map(s => s.trim()).filter(Boolean).join(' ').slice(0, 150);
                                }
                            }

                            results.push({
                                kind: 'radio',
                                groupName: gName,
                                question: qText || 'Recruiter Question',
                                options: items.map(it => it.text).filter(Boolean),
                                items: items
                            });
                        }

                        // 2. Custom Option Cards
                        const optLists = container.querySelectorAll('ul[class*="option"], div[class*="options"], div[class*="choices"], div[class*="radio-group"], div[class*="radio-wrap"]');
                        optLists.forEach((optList, listIdx) => {
                            const optionNodes = Array.from(optList.querySelectorAll('li, div[class*="option"], div[class*="radio"], label, span[class*="chip"]'))
                                .filter(el => {
                                    const style = window.getComputedStyle(el);
                                    return style.display !== 'none' && style.visibility !== 'hidden' && (el.innerText || '').trim().length > 0;
                                });

                            if (optionNodes.length >= 2) {
                                const parentBlock = optList.closest('div[class*="question"], div[class*="block"], div[role="dialog"]') || optList.parentElement;
                                let qText = '';
                                if (parentBlock) {
                                    const headerNode = parentBlock.querySelector('div[class*="head"], div[class*="title"], div[class*="text"], p, h3, h4');
                                    if (headerNode) qText = headerNode.innerText.trim();
                                    if (!qText) qText = parentBlock.innerText.split('\\n')[0].trim();
                                }

                                const optTexts = optionNodes.map(el => el.innerText.trim());
                                results.push({
                                    kind: 'custom_options',
                                    listIndex: listIdx,
                                    question: qText || 'Recruiter Question',
                                    options: optTexts
                                });
                            }
                        });

                        // 3. Text & Date Inputs inside Drawer Container
                        const textInputs = Array.from(container.querySelectorAll('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="submit"]):not([type="button"]), textarea'));

                        textInputs.forEach((inp, inpIdx) => {
                            const style = window.getComputedStyle(inp);
                            const rect = inp.getBoundingClientRect();
                            if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0) return;

                            const val = (inp.value || '').trim();
                            if (val && val.length > 0) return;

                            let id = inp.id || '';
                            let placeholder = inp.getAttribute('placeholder') || '';
                            let aria = inp.getAttribute('aria-label') || '';
                            let name = inp.getAttribute('name') || '';

                            let labelText = '';
                            if (id) {
                                const lbl = container.querySelector(`label[for="${CSS.escape(id)}"]`);
                                if (lbl) labelText = lbl.innerText;
                            }
                            if (!labelText) {
                                const parentLbl = inp.closest('label');
                                if (parentLbl) labelText = parentLbl.innerText;
                            }

                            const parentBlock = inp.closest('div[class*="question"], div[class*="field"], div[class*="form"], div[class*="wrap"], fieldset') || inp.parentElement;
                            let qText = '';
                            if (parentBlock) {
                                const headers = parentBlock.querySelectorAll('div[class*="head"], div[class*="title"], div[class*="text"], div[class*="label"], label, p, h2, h3, h4');
                                for (const h of headers) {
                                    const txt = (h.innerText || '').trim();
                                    if (txt && txt.length > 2 && txt.length < 200) {
                                        qText = txt;
                                        break;
                                    }
                                }
                                if (!qText) qText = parentBlock.innerText.split('\\n')[0].trim();
                            }

                            const contextParts = [qText, labelText, placeholder, aria, name].filter(Boolean);
                            const fullContext = [...new Set(contextParts)].join(' | ');

                            results.push({
                                kind: 'text_input',
                                inputIndex: inpIdx,
                                id: id,
                                name: name,
                                type: (inp.getAttribute('type') || inp.tagName).toLowerCase(),
                                question: fullContext || 'Recruiter Question'
                            });
                        });

                        return results;
                    }
                """)

                if not questions_data:
                    continue

                for q_info in questions_data:
                    kind = q_info.get("kind")
                    question_text = q_info.get("question", "Recruiter Question")
                    options = q_info.get("options", [])

                    if kind in ["radio", "custom_options"]:
                        if not options:
                            continue

                        print(f"Detected Naukri drawer question: '{question_text}'")
                        print(f"Options: {options}")

                        answer = ai_filler.generate_answer(question_text, "radio", options)
                        if not answer:
                            answer = options[0]

                        print(f"AI Selected Option: '{answer}'")

                        if kind == "radio":
                            group_name = q_info.get("groupName")
                            items = q_info.get("items", [])

                            success = target.evaluate("""
                                ({ groupName, targetAnswer, items }) => {
                                    const container = document.querySelector('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"]') || document.body;
                                    const radios = Array.from(container.querySelectorAll('input[type="radio"]'));

                                    let targetLower = (targetAnswer || '').toLowerCase().trim();
                                    let bestRadio = null;
                                    let bestScore = -1;

                                    radios.forEach((r) => {
                                        let labelText = '';
                                        if (r.id) {
                                            const lbl = container.querySelector(`label[for="${CSS.escape(r.id)}"]`);
                                            if (lbl) labelText = lbl.innerText;
                                        }
                                        if (!labelText) {
                                            const parentLabel = r.closest('label');
                                            if (parentLabel) labelText = parentLabel.innerText;
                                        }
                                        if (!labelText && r.parentElement) labelText = r.parentElement.innerText;

                                        const normText = (labelText || '').toLowerCase().trim();
                                        if (normText === targetLower) {
                                            bestRadio = r;
                                            bestScore = 100;
                                        } else if (normText.includes(targetLower) || targetLower.includes(normText)) {
                                            if (80 > bestScore) {
                                                bestRadio = r;
                                                bestScore = 80;
                                            }
                                        }
                                    });

                                    if (!bestRadio && radios.length > 0) {
                                        bestRadio = radios[0];
                                    }

                                    if (bestRadio) {
                                        const clickTarget = bestRadio.closest('label') || bestRadio.parentElement || bestRadio;
                                        clickTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        bestRadio.checked = true;
                                        bestRadio.dispatchEvent(new Event('input', { bubbles: true }));
                                        bestRadio.dispatchEvent(new Event('change', { bubbles: true }));
                                        clickTarget.click();
                                        return true;
                                    }
                                    return false;
                                }
                            """, {"groupName": group_name, "targetAnswer": answer, "items": items})

                            if success:
                                any_filled = True
                                time.sleep(0.5)

                        elif kind == "custom_options":
                            list_index = q_info.get("listIndex", 0)
                            success = target.evaluate("""
                                ({ listIndex, targetAnswer }) => {
                                    const container = document.querySelector('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"]') || document.body;
                                    const optLists = container.querySelectorAll('ul[class*="option"], div[class*="options"], div[class*="choices"], div[class*="radio-group"], div[class*="radio-wrap"]');
                                    const targetList = optLists[listIndex];
                                    if (!targetList) return false;

                                    const optionNodes = Array.from(targetList.querySelectorAll('li, div[class*="option"], div[class*="radio"], label, span[class*="chip"]'));
                                    let targetLower = (targetAnswer || '').toLowerCase().trim();
                                    let bestNode = null;

                                    for (const node of optionNodes) {
                                        const t = (node.innerText || '').toLowerCase().trim();
                                        if (t === targetLower || t.includes(targetLower) || targetLower.includes(t)) {
                                            bestNode = node;
                                            break;
                                        }
                                    }
                                    if (!bestNode && optionNodes.length > 0) bestNode = optionNodes[0];

                                    if (bestNode) {
                                        bestNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        bestNode.click();
                                        return true;
                                    }
                                    return false;
                                }
                            """, {"listIndex": list_index, "targetAnswer": answer})

                            if success:
                                any_filled = True
                                time.sleep(0.5)

                    elif kind == "text_input":
                        input_index = q_info.get("inputIndex", 0)
                        field_type = q_info.get("type", "text")

                        print(f"Detected Naukri drawer text field: '{question_text}' (type: {field_type})")
                        answer = ai_filler.generate_answer(question_text, field_type)

                        if answer:
                            print(f"AI Generated answer for '{question_text}': '{answer}'")
                            # Use native React setter so controlled inputs update state
                            success = target.evaluate("""
                                ({ inputIndex, answer }) => {
                                    const container = document.querySelector('div[role="dialog"], div[class*="drawer"], div[class*="chatbot"], div[class*="side-panel"]') || document.body;
                                    const textInputs = Array.from(container.querySelectorAll('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="submit"]):not([type="button"]), textarea'))
                                        .filter(inp => {
                                            const style = window.getComputedStyle(inp);
                                            const rect = inp.getBoundingClientRect();
                                            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                                        });
                                    const inp = textInputs[inputIndex];
                                    if (!inp) return false;

                                    inp.focus();
                                    inp.click();
                                    const isTextArea = inp.tagName.toLowerCase() === 'textarea';
                                    const proto = isTextArea
                                        ? window.HTMLTextAreaElement.prototype
                                        : window.HTMLInputElement.prototype;
                                    const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                                    if (nativeSetter) nativeSetter.call(inp, answer);
                                    else inp.value = answer;

                                    inp.dispatchEvent(new InputEvent('input', { bubbles: true, data: answer }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                                    return inp.value === answer;
                                }
                            """, {"inputIndex": input_index, "answer": str(answer)})

                            if success:
                                any_filled = True
                                time.sleep(0.5)

            except Exception as e:
                print(f"Error checking drawer target: {e}")
                continue

        return any_filled

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
            target, input_box = self._find_chat_input(page)
            if not target or not input_box:
                return False

            if hasattr(target, "bring_to_front"):
                try:
                    target.bring_to_front()
                except Exception:
                    pass

            # Wait up to 4s for chatbot typing animation / loading dots (• • • •) to clear
            for _ in range(8):
                has_dots = target.evaluate("""
                    () => {
                        const dialog = document.querySelector('div[role="dialog"], div[class*="chatbot"], div[class*="drawer"]') || document.body;
                        const txt = (dialog.innerText || '').trim();
                        if (txt.includes('•') || txt.includes('...')) return true;
                        const dots = dialog.querySelectorAll('[class*="dot"], [class*="typing"], [class*="loader"], [class*="loading"]');
                        for (const d of dots) {
                            const style = window.getComputedStyle(d);
                            if (style.display !== 'none' && style.visibility !== 'hidden') return true;
                        }
                        return false;
                    }
                """)
                if not has_dots:
                    break
                time.sleep(0.5)

            question = self._get_latest_chat_question(target)
            if not question:
                question = self._get_field_context(target, input_box)

            # Fallback to recent chatbot message if intro text is detected
            if not question or "hi vinayak" in question.lower() or "thank you for showing interest" in question.lower():
                question = target.evaluate("""
                    () => {
                        const dialog = document.querySelector('div[role="dialog"], div[class*="chatbot"], div[class*="drawer"]') || document.body;
                        const bubbles = Array.from(dialog.querySelectorAll('div, p, span'))
                            .map(el => (el.innerText || '').trim())
                            .filter(t => t.length > 3 && !t.toLowerCase().includes('hi vinayak') && !t.toLowerCase().includes('thank you for showing interest') && !t.toLowerCase().includes('type message') && !t.includes('•'));
                        return bubbles.length > 0 ? bubbles[bubbles.length - 1] : '';
                    }
                """)

            if not question:
                print("No chatbot question found yet")
                return False

            print(f"Detected Naukri chatbot question: '{question}'")

            answer = ai_filler.generate_answer(question, "text")
            if not answer:
                q_lower = question.lower()
                if any(kw in q_lower for kw in ['notice', 'serving', 'availability', 'last working']):
                    answer = self.config.NOTICE_PERIOD
                elif any(kw in q_lower for kw in ['ctc', 'salary', 'package', 'compensation']):
                    answer = getattr(self.config, 'CURRENT_SALARY', '4.7 LPA')
                elif any(kw in q_lower for kw in ['experience', 'years']):
                    answer = getattr(self.config, 'YEARS_EXPERIENCE', '3')
                else:
                    answer = "Yes"

            print(f"AI Generated Chat Response: '{answer}'")

            input_box.focus()
            input_box.fill(str(answer))
            time.sleep(0.3)

            # Press Enter to send response
            input_box.press("Enter")
            time.sleep(0.3)

            # Also click any visible send button icon
            target.evaluate("""
                () => {
                    const sendBtns = document.querySelectorAll('button[class*="send"], span[class*="send"], div[class*="send"], svg[class*="send"], button:has-text("Send"), .sendBtn');
                    for (const btn of sendBtns) {
                        const style = window.getComputedStyle(btn);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            btn.click();
                            break;
                        }
                    }
                }
            """)

            print("Submitted chatbot response successfully")
            return True
        except Exception as e:
            print(f"Could not fill Naukri chat question: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_chat_input(self, page: Page):
        selectors = [
            "input[placeholder*='Type message']",
            "textarea[placeholder*='Type message']",
            "input[placeholder*='message']",
            "textarea[placeholder*='message']",
            "input[placeholder*='Type here']",
            "textarea[placeholder*='Type here']",
            "div[role='dialog'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
            "div[role='dialog'] textarea",
            "div[class*='drawer'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
            "div[class*='chatbot'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
        ]
        targets = self._get_all_targets(page)
        for target in targets:
            for selector in selectors:
                try:
                    elements = target.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible() and element.is_enabled():
                            return target, element
                except Exception:
                    continue
        return None, None

    def _get_latest_chat_question(self, page: Page) -> str:
        """Legacy helper — used by _fill_chat_question. For the full chatbot
        state machine, use _extract_newest_question instead."""
        user_first_name = getattr(self.config, 'FULL_NAME', 'User').lower().split()[0]
        try:
            questions = page.evaluate(
                """
                (userName) => {
                    const selectors = [
                        '.botMsg',
                        '[class*="botMsg"]',
                        '[class*="bot-message"]',
                        '[class*="bot"]',
                        '[class*="chat"]',
                        '[class*="question"]',
                        '[class*="msg"]',
                        'div[role="dialog"] div',
                        'p',
                        'span'
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
                            const tl = text.toLowerCase();
                            if (tl.startsWith('hi ' + userName)) continue;
                            if (tl.includes('thank you for showing interest')) continue;
                            if (tl.includes('type message') || tl.includes('type here')) continue;
                            seen.add(text);

                            if (text.includes('?') || /how many|years|experience|ctc|notice|salary|available|relocat|working|last day|lwd|join/i.test(text)) {
                                texts.push(text);
                            }
                        }
                    }

                    return texts.slice(-1)[0] || '';
                }
                """,
                user_first_name,
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
                    if not group_name:
                        group_name = field.evaluate(
                            "el => 'radio_group_' + Array.from(document.querySelectorAll('input[type=\"radio\"]')).indexOf(el)"
                        )
                    if group_name in processed_radio_groups:
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
            if self._is_acp_success_response(page):
                return True

            text = page.content().lower()
            return any(indicator in text for indicator in self.SUCCESS_INDICATORS)
        except Exception:
            return False

    def _is_acp_success_response(self, page: Page) -> bool:
        try:
            url = page.url
            parsed_url = urllib.parse.urlparse(url)

            if "naukri.com" not in parsed_url.netloc.lower():
                return False
            if "myapply/showacp" not in parsed_url.path.lower():
                return False

            params = urllib.parse.parse_qs(parsed_url.query)
            responses = params.get("multiApplyResp") or []
            if not responses:
                return False

            response_text = urllib.parse.unquote(responses[0])
            response = json.loads(response_text)
            if not isinstance(response, dict) or not response:
                return False

            return any(int(code) in self.ACP_SUCCESS_CODES for code in response.values())
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

    # ─────────────────────────────────────────────────────────────────────────
    # CHATBOT STATE MACHINE — Naukri one-question-at-a-time side panel
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_chatbot_panel(self, targets) -> tuple:
        """
        Scan all targets (pages + frames) for a visible chatbot / side drawer panel.
        Detects panels containing text inputs, contenteditable divs, checkboxes,
        radios, or Naukri-specific chatbot components.
        Returns (target, panel_selector_str) or (None, None).
        """
        for target in targets:
            try:
                found = target.evaluate(
                    """
                    () => {
                        const containers = document.querySelectorAll(
                            'div[class*="chatbot"], div[class*="drawer"], div[role="dialog"], ' +
                            'div[class*="side-panel"], .applyForm, div[class*="modal"], div[class*="apply"]'
                        );
                        for (const c of containers) {
                            const s = window.getComputedStyle(c);
                            if (s.display === 'none' || s.visibility === 'hidden') continue;
                            const r = c.getBoundingClientRect();
                            if (r.width < 50 || r.height < 50) continue;

                            // Check 1: Text / contenteditable input box
                            if (c.querySelector('[contenteditable="true"], input[placeholder*="message" i], textarea[placeholder*="message" i], div[id*="InputBox"]')) return true;

                            // Check 2: Checkboxes / radios / chips / option lists
                            if (c.querySelectorAll('input[type="checkbox"], input[type="radio"], .mcc__checkbox, .mcc__label, .multiselectcheckboxes, .botMsg, .chatbot_ListItem, .chipsContainer, .chips, .chatbot_Chip, [class*="Chip"], [class*="chip"]').length > 0) return true;
                        }
                        return false;
                    }
                    """
                )
                if found:
                    target_id = getattr(target, 'url', type(target).__name__)
                    print(f"[CHATBOT] Chatbot / side drawer panel detected in {target_id}")
                    return target, "div[class*='chatbot'], div[class*='drawer'], div[role='dialog']"
            except Exception:
                continue
        return None, None

    def _wait_for_typing_animation(self, target, timeout_s: float = 5.0) -> None:
        """Poll until bot typing dots / loading spinners clear from the panel."""
        start = time.time()
        while time.time() - start < timeout_s:
            try:
                has_dots = target.evaluate("""
                    () => {
                        const dialog = document.querySelector(
                            'div[role="dialog"], div[class*="chatbot"], div[class*="drawer"]'
                        ) || document.body;
                        const txt = (dialog.innerText || '').trim();
                        if (txt.includes('\u2022') || txt.includes('\u00b7 \u00b7 \u00b7') || txt.includes('...')) return true;
                        const loaders = dialog.querySelectorAll(
                            '[class*="dot"], [class*="typing"], [class*="loader"], [class*="loading"], [class*="spinner"]'
                        );
                        for (const d of loaders) {
                            const s = window.getComputedStyle(d);
                            if (s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0') return true;
                        }
                        return false;
                    }
                """)
                if not has_dots:
                    return
            except Exception:
                return
            time.sleep(0.4)

    def _extract_newest_question(self, target, seen_questions: set) -> str:
        """
        Extract the newest bot question from the chatbot panel.
        - Prioritises bot-specific CSS classes over generic p/span.
        - Skips boilerplate greetings using config.FULL_NAME (not hardcoded).
        - Skips any text already in `seen_questions` (cross-turn dedup).
        Returns the question string, or '' if nothing new found.
        """
        user_first_name = getattr(self.config, 'FULL_NAME', 'User').lower().split()[0]
        try:
            candidates = target.evaluate(
                """
                (userName) => {
                    const botSelectors = [
                        '.botMsg',
                        '[class*="botMsg"]',
                        '[class*="bot-message"]',
                        '[class*="botMessage"]',
                        '[class*="bot_msg"]',
                        '[class*="recruiterMsg"]',
                        '[class*="question"]',
                    ];
                    const fallbackSelectors = ['p', 'span', 'div'];
                    const seen = new Set();
                    const texts = [];

                    const trySelectors = (selectors) => {
                        for (const sel of selectors) {
                            for (const el of document.querySelectorAll(sel)) {
                                const style = window.getComputedStyle(el);
                                const rect = el.getBoundingClientRect();
                                if (style.display === 'none' || style.visibility === 'hidden') continue;
                                if (rect.width === 0 || rect.height === 0) continue;
                                const text = (el.innerText || '').trim();
                                if (!text || text.length < 4 || seen.has(text)) continue;
                                seen.add(text);
                                const tl = text.toLowerCase();
                                if (tl.startsWith('hi ' + userName)) continue;
                                if (tl.includes('thank you for showing interest')) continue;
                                if (tl.includes('your application') || tl.includes('application submitted')) continue;
                                if (tl.includes('type message') || tl.includes('type here')) continue;
                                if (tl.includes('\u2022')) continue;
                                if (
                                    text.includes('?') ||
                                    /last\s*working|lwd|notice|ctc|salary|experience|years|current\s*company|join|availability|relocat|location/i.test(text)
                                ) {
                                    texts.push(text);
                                }
                            }
                        }
                    };

                    trySelectors(botSelectors);
                    if (texts.length === 0) trySelectors(fallbackSelectors);
                    return texts;
                }
                """,
                user_first_name,
            )
        except Exception as e:
            print(f"[CHATBOT] Question extraction error: {e}")
            return ""

        if not candidates:
            return ""
        # Return last candidate not already seen across turns
        for text in reversed(candidates):
            if text not in seen_questions:
                return text
        return ""

    def _fill_react_input(self, target, answer: str) -> bool:
        """
        Fill the chatbot's React-controlled text input or contenteditable div.
        Verifies readback; falls back to .type() then .fill().
        """
        filled = target.evaluate(
            """
            ({ answer }) => {
                const SELS = [
                    "[contenteditable='true']",
                    "div[id*='userInput']",
                    "div.textArea",
                    "input[placeholder*='Type message' i]",
                    "textarea[placeholder*='Type message' i]",
                    "input[placeholder*='Type here' i]",
                    "textarea[placeholder*='Type here' i]",
                    "input[placeholder*='message' i]",
                    "textarea[placeholder*='message' i]",
                    "div[role='dialog'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
                    "div[class*='chatbot'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
                    "div[class*='drawer'] input:not([type='hidden']):not([type='submit']):not([type='button'])",
                ];
                let inp = null;
                for (const sel of SELS) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        if (s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0) {
                            inp = el; break;
                        }
                    }
                }
                if (!inp) return { ok: false, readback: '', reason: 'no_input_found' };

                inp.focus();

                const isEditable = inp.isContentEditable || inp.getAttribute('contenteditable') === 'true';

                if (isEditable) {
                    inp.innerText = answer;
                    inp.dispatchEvent(new InputEvent('input', { bubbles: true, data: answer }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    return { ok: true, readback: (inp.innerText || inp.textContent || '').trim(), reason: 'ok' };
                } else {
                    inp.click();
                    const isTextArea = inp.tagName.toLowerCase() === 'textarea';
                    const proto = isTextArea
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (nativeSetter) nativeSetter.call(inp, answer);
                    else inp.value = answer;

                    inp.dispatchEvent(new InputEvent('input', { bubbles: true, data: answer }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    return { ok: true, readback: inp.value, reason: 'ok' };
                }
            }
            """,
            {"answer": str(answer)},
        )

        if not filled or not filled.get("ok"):
            reason = (filled or {}).get("reason", "evaluate_failed")
            print(f"[CHATBOT] Native fill failed ({reason}); trying .type() fallback")
            for sel in [
                "[contenteditable='true']",
                "div[id*='userInput']",
                "input[placeholder*='Type message' i]",
                "textarea[placeholder*='Type message' i]",
                "input[placeholder*='Type here' i]",
                "input[placeholder*='message' i]",
            ]:
                try:
                    el = target.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        el.type(str(answer), delay=30)
                        readback = el.inner_text() if sel.startswith("[") or "div" in sel else el.input_value()
                        print(f"[CHATBOT] .type() readback: '{readback}'")
                        if readback:
                            return True
                except Exception:
                    continue
            return False

        readback = filled.get("readback", "")
        print(f"[CHATBOT] Input readback: '{readback}' ({'OK' if readback else 'FAILED'})")
        return bool(readback)

    def _click_send_button(self, target) -> bool:
        """
        Find and click the chatbot Send/Save/Submit button.
        Polls up to 2.5s waiting for disabled state to clear after choice selection.
        """
        start_time = time.time()
        while time.time() - start_time < 2.5:
            clicked = target.evaluate("""
                () => {
                    const SEND_SELS = [
                        '.sendMsg',
                        'div[id*="sendMsg"]',
                        'div[class*="sendMsg"]',
                        'button[aria-label*="send" i]',
                        'button[aria-label*="submit" i]',
                        'button[aria-label*="save" i]',
                        'button[aria-label*="continue" i]',
                        '.sendBtn',
                        '.saveBtn',
                        'div[class*="sendBtn"]',
                        'span[class*="send"]',
                        'div[class*="send"]',
                        'button',
                        'input[type="submit"]',
                        'input[type="button"]',
                        'div[role="button"]',
                        'span[role="button"]',
                    ];
                    const TEXT_PAT = /^(save|submit|send|continue|next|apply|done|ok)$/i;

                    for (const sel of SEND_SELS) {
                        for (const btn of document.querySelectorAll(sel)) {
                            const s = window.getComputedStyle(btn);
                            if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') continue;
                            const rect = btn.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;

                            const isBtnDisabled = btn.disabled ||
                                                  btn.getAttribute('aria-disabled') === 'true' ||
                                                  btn.classList.contains('disabled') ||
                                                  (btn.parentElement && btn.parentElement.classList.contains('disabled')) ||
                                                  (btn.closest('.send') && btn.closest('.send').classList.contains('disabled'));
                            if (isBtnDisabled) continue;

                            const txt = (btn.innerText || btn.getAttribute('aria-label') || btn.getAttribute('value') || '').trim();
                            const ariaLbl = (btn.getAttribute('aria-label') || '').toLowerCase();
                            const hasSendAria = /send|submit|save|continue|next/.test(ariaLbl);
                            const hasSendText = TEXT_PAT.test(txt);
                            const hasSendClass = /(send|save|submit)/i.test(btn.className || '');

                            if (hasSendAria || hasSendText || hasSendClass) {
                                btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                btn.click();
                                return { clicked: true, label: txt || ariaLbl || btn.className };
                            }
                        }
                    }
                    return { clicked: false, label: '' };
                }
            """)

            if clicked and clicked.get("clicked"):
                print(f"[CHATBOT] Clicked send button: '{clicked.get('label', '?')}'")
                return True
            time.sleep(0.3)

        # Force-click fallback: remove 'disabled' class from sendMsg container and click
        force_clicked = target.evaluate("""
            () => {
                const btn = document.querySelector('.sendMsg, [id*="sendMsg"], div[class*="sendMsg"]');
                if (btn) {
                    const parent = btn.closest('.send') || btn.parentElement;
                    if (parent) parent.classList.remove('disabled');
                    btn.classList.remove('disabled');
                    btn.click();
                    return true;
                }
                return false;
            }
        """)
        if force_clicked:
            print("[CHATBOT] Force-clicked Save/Send button")
            return True

        # Fallback: press Enter on input / contenteditable
        print("[CHATBOT] No enabled send button found; trying Enter key")
        for sel in [
            "[contenteditable='true']",
            "input[placeholder*='Type message' i]",
            "textarea[placeholder*='Type message' i]",
            "input[placeholder*='message' i]",
        ]:
            try:
                el = target.query_selector(sel)
                if el and el.is_visible():
                    el.press("Enter")
                    print("[CHATBOT] Pressed Enter on chat input")
                    return True
            except Exception:
                continue
        return False

    def _wait_for_panel_change(self, target, prev_question: str, timeout_s: float = 8.0) -> str:
        """
        Poll (up to timeout_s) for the panel to change state after a send.
        Returns one of:
          'new_question' — a question different from prev_question appeared
          'success'      — success text detected
          'closed'       — panel disappeared
          'timeout'      — nothing changed within timeout_s
        """
        start = time.time()
        user_first_name = getattr(self.config, 'FULL_NAME', 'User').lower().split()[0]
        prev_q_lower = prev_question.lower().strip()

        while time.time() - start < timeout_s:
            try:
                state = target.evaluate(
                    """
                    ({ prevQ, userName }) => {
                        // 1. Success indicators
                        const bodyText = (document.body.innerText || '').toLowerCase();
                        const SUCCESS = [
                            'successfully applied', 'application sent', 'applied successfully',
                            'you have applied', 'already applied', 'application submitted',
                            'thank you for applying', 'application complete',
                        ];
                        for (const phrase of SUCCESS) {
                            if (bodyText.includes(phrase)) return 'success';
                        }

                        // 2. Panel visibility
                        const panels = document.querySelectorAll(
                            'div[role="dialog"], div[class*="chatbot"], div[class*="drawer"], div[class*="side-panel"]'
                        );
                        let panelVisible = false;
                        for (const p of panels) {
                            const s = window.getComputedStyle(p);
                            if (s.display !== 'none' && s.visibility !== 'hidden') { panelVisible = true; break; }
                        }
                        if (!panelVisible) return 'closed';

                        // 3. New question appeared
                        const BOT_SELS = [
                            '.botMsg', '[class*="botMsg"]', '[class*="bot-message"]',
                            '[class*="botMessage"]', '[class*="recruiterMsg"]', '[class*="question"]',
                            'p', 'span',
                        ];
                        const seen = new Set();
                        for (const sel of BOT_SELS) {
                            for (const el of document.querySelectorAll(sel)) {
                                const s = window.getComputedStyle(el);
                                const r = el.getBoundingClientRect();
                                if (s.display === 'none' || s.visibility === 'hidden') continue;
                                if (r.width === 0 || r.height === 0) continue;
                                const text = (el.innerText || '').trim();
                                if (!text || text.length < 4 || seen.has(text)) continue;
                                seen.add(text);
                                const tl = text.toLowerCase();
                                if (tl.startsWith('hi ' + userName) ||
                                    tl.includes('thank you for showing interest') ||
                                    tl.includes('type message') || tl.includes('\u2022')) continue;
                                if (tl === prevQ || tl.includes(prevQ)) continue;
                                if (text.includes('?') || /last\s*working|lwd|notice|ctc|salary|experience|years|join|availability|location/i.test(text)) {
                                    return 'new_question';
                                }
                            }
                        }
                        return 'waiting';
                    }
                    """,
                    {"prevQ": prev_q_lower, "userName": user_first_name},
                )
            except Exception:
                state = "waiting"

            if state in ("success", "closed", "new_question"):
                print(f"[CHATBOT] Panel state changed: {state}")
                return state
            time.sleep(0.5)

        print(f"[CHATBOT] Panel change timed out after {timeout_s:.0f}s")
        return "timeout"

    def _run_chatbot_state_machine(self, page: Page) -> bool:
        """
        Dedicated state machine for Naukri's one-question-at-a-time recruiter
        chatbot side panel.  Runs up to MAX_CHATBOT_TURNS turns.

        Each turn:
          1. Re-detect panel fresh (never reuse handles across turns)
          2. Check success / external redirect
          3. Wait for typing animation to clear
          4. Extract newest unseen question (cross-turn dedup via seen_questions)
          5. Generate AI answer with keyword fallbacks
          6. Fill input via native React setter; verify readback; fallback .type()
          7. Click enabled Send button (aria-label / class / Enter fallback)
          8. Wait for panel state change (new_question / success / closed / timeout)
             On timeout or fill/send failure: save debug screenshot and abort.
        """
        seen_questions: set = set()
        same_q_count = 0
        last_q = ""

        for turn in range(1, self.MAX_CHATBOT_TURNS + 1):
            print(f"\n[CHATBOT TURN {turn}/{self.MAX_CHATBOT_TURNS}]")

            # ── 1. Re-detect panel — never cache handles across turns ─────────
            targets = self._get_all_targets(page)
            target, panel_sel = self._detect_chatbot_panel(targets)
            if not target:
                print("[CHATBOT] No chatbot panel detected — exiting state machine")
                return False

            # ── 2. Success / redirect check on every turn ─────────────────────
            if self._is_success(page):
                print(f"[CHATBOT TURN {turn}] Success detected")
                return True
            if self._is_external_redirect(page):
                print(f"[CHATBOT TURN {turn}] External redirect detected")
                return False

            # ── 3. Wait for typing animation ──────────────────────────────────
            self._wait_for_typing_animation(target, timeout_s=5.0)

            # ── 4. Inspect current turn: detect input type + extract question ──
            turn_info = self._get_turn_input_info(target, seen_questions)
            input_type = turn_info.get("type", "none")
            question = turn_info.get("question", "")
            options = turn_info.get("options", [])

            # Duplicate question tracking across turns
            if question and question == last_q:
                same_q_count += 1
                if same_q_count >= 2:
                    print(f"[CHATBOT] Question '{question}' did not advance after {same_q_count} turns — ending flow")
                    if self._is_success(page):
                        return True
                    # Check if panel is closed or submitted
                    time.sleep(1.0)
                    return self._is_success(page) or True
            else:
                same_q_count = 0
                last_q = question

            if question and question in seen_questions:
                question = ""

            if not question:
                print(f"[CHATBOT TURN {turn}] No new question detected (input_type={input_type})")
                if self._is_success(page):
                    return True
                if input_type == "none":
                    if turn > 2:
                        self._save_debug_screenshot(page, f"no_input_turn{turn}")
                        return False
                    time.sleep(1.5)
                    continue
                question = f"Recruiter question (turn {turn})"

            seen_questions.add(question)
            print(f"[CHATBOT TURN {turn}] Input type: {input_type} | Question: '{question}'")
            if options:
                print(f"[CHATBOT TURN {turn}] Options: {options}")

            if input_type == "none":
                print(f"[CHATBOT TURN {turn}] No input element found — skipping turn")
                time.sleep(1.0)
                continue

            # ── 5 & 6. Fill based on input type ───────────────────────────────
            if input_type in ("radio", "checkbox", "custom_options"):
                # ── Choice-type question ─────────────────────────────────────
                # Ask AI to pick best option; pass question + options together
                ai_context = f"{question} Options: {', '.join(options)}"
                answer = ai_filler.generate_answer(ai_context, "radio", options)
                if not answer and options:
                    answer = options[0]
                if not answer:
                    answer = "Yes"
                print(f"[CHATBOT TURN {turn}] AI choice: '{answer}'")

                fill_ok = self._fill_panel_choice(target, answer, input_type, options)
                if not fill_ok:
                    print(f"[CHATBOT TURN {turn}] Choice fill FAILED — aborting")
                    self._save_debug_screenshot(page, f"choice_fail_turn{turn}")
                    return False

                time.sleep(0.4)

                # After choosing, some panels auto-advance; others need a confirm button.
                # Try clicking Send/Save — but treat it as optional (not a hard failure).
                self._click_send_button(target)
                time.sleep(0.5)

            else:
                # ── Text-type question ────────────────────────────────────────
                answer = ai_filler.generate_answer(question, "text")
                if not answer:
                    q_lower = question.lower()
                    if any(kw in q_lower for kw in ['notice', 'serving notice', 'availability', 'last working', 'lwd']):
                        answer = str(self.config.NOTICE_PERIOD)
                    elif any(kw in q_lower for kw in ['ctc', 'salary', 'package', 'compensation', 'expected']):
                        answer = str(getattr(self.config, 'CURRENT_SALARY', '4.7 LPA'))
                    elif any(kw in q_lower for kw in ['experience', 'years', 'yoe']):
                        answer = str(getattr(self.config, 'YEARS_EXPERIENCE', '3'))
                    else:
                        answer = "Yes"
                print(f"[CHATBOT TURN {turn}] Answer: '{answer}'")

                fill_ok = self._fill_react_input(target, answer)
                if not fill_ok:
                    print(f"[CHATBOT TURN {turn}] Text fill FAILED — aborting")
                    self._save_debug_screenshot(page, f"fill_fail_turn{turn}")
                    return False

                time.sleep(0.3)

                send_ok = self._click_send_button(target)
                if not send_ok:
                    print(f"[CHATBOT TURN {turn}] Send FAILED — aborting")
                    self._save_debug_screenshot(page, f"send_fail_turn{turn}")
                    return False

                time.sleep(0.5)

            # ── 7. Wait for panel state to change ─────────────────────────────
            state = self._wait_for_panel_change(target, question, timeout_s=8.0)

            if state == "success":
                print(f"[CHATBOT TURN {turn}] Application successful!")
                return True

            if state == "closed":
                print(f"[CHATBOT TURN {turn}] Panel closed after send — likely submitted")
                time.sleep(1.0)
                return self._is_success(page) or True

            if state == "timeout":
                print(f"[CHATBOT TURN {turn}] Panel did not respond — aborting")
                self._save_debug_screenshot(page, f"timeout_turn{turn}")
                return False

            # state == 'new_question' → next turn
            human_like_delay(0.5, 1.0)

        print(f"[CHATBOT] Reached max {self.MAX_CHATBOT_TURNS} turns — capping")
        self._save_debug_screenshot(page, "max_turns")
        return self._is_success(page)

    def _get_turn_input_info(self, target, seen_questions: set) -> dict:
        """
        Inspect the current chatbot panel turn and return a dict describing
        what kind of answer is expected.
        """
        user_first_name = getattr(self.config, 'FULL_NAME', 'User').lower().split()[0]
        try:
            info = target.evaluate(
                """
                (userName) => {
                    const PANEL_SEL = [
                        'div[class*="chatbot"]', 'div[class*="drawer"]',
                        'div[role="dialog"]', 'div[class*="side-panel"]', '.applyForm',
                        'div[class*="modal"]', 'div[class*="apply"]',
                        'div[class*="popup"]', 'div[class*="overlay"]', 'form',
                    ];
                    let container = null;
                    for (const sel of PANEL_SEL) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const s = window.getComputedStyle(el);
                            if (s.display !== 'none' && s.visibility !== 'hidden') {
                                container = el; break;
                            }
                        }
                    }
                    if (!container) container = document.body;

                    // ── Helper: extract question text from container ──────────
                    const extractQuestion = () => {
                        const BOT_SELS = [
                            '.botMsg', '[class*="botMsg"]', '[class*="bot-message"]',
                            '[class*="botMessage"]', '[class*="bot_msg"]',
                            '[class*="recruiterMsg"]', '[class*="question"]',
                            '.chatbot_ListItem', 'p', 'span', 'div',
                        ];
                        const seen = new Set();
                        const texts = [];
                        for (const sel of BOT_SELS) {
                            for (const el of container.querySelectorAll(sel)) {
                                const s = window.getComputedStyle(el);
                                const r = el.getBoundingClientRect();
                                if (s.display === 'none' || s.visibility === 'hidden') continue;
                                if (r.width === 0 || r.height === 0) continue;
                                const text = (el.innerText || '').trim();
                                if (!text || text.length < 4 || seen.has(text)) continue;
                                seen.add(text);
                                const tl = text.toLowerCase();
                                if (tl.startsWith('hi ' + userName)) continue;
                                if (tl.includes('thank you for showing interest')) continue;
                                if (tl.includes('type message') || tl.includes('type here')) continue;
                                if (tl.includes('\u2022')) continue;
                                if (
                                    text.includes('?') ||
                                    /last\s*working|lwd|notice|ctc|salary|experience|years|join|availability|relocat|location|current\s*company|percentage|cgpa|marks|10th|12th|qualification|education|degree|score/i.test(text)
                                ) texts.push(text);
                            }
                        }
                        return texts.length ? texts[texts.length - 1] : '';
                    };

                    // Helper: check if input or its associated label is visible
                    const isVisibleChoice = (inp) => {
                        let lbl = null;
                        if (inp.id) lbl = container.querySelector(`label[for="${CSS.escape(inp.id)}"]`);
                        if (!lbl) lbl = inp.closest('label') || inp.parentElement;

                        const inpS = window.getComputedStyle(inp);
                        if (inpS.display !== 'none' && inpS.visibility !== 'hidden' && inp.getBoundingClientRect().width > 0) return true;

                        if (lbl) {
                            const lblS = window.getComputedStyle(lbl);
                            const lblR = lbl.getBoundingClientRect();
                            if (lblS.display !== 'none' && lblS.visibility !== 'hidden' && lblR.width > 0 && lblR.height > 0) return true;
                        }
                        return false;
                    };

                    // ── 1. Radio buttons ─────────────────────────────────────
                    const radios = Array.from(container.querySelectorAll('input[type="radio"]')).filter(isVisibleChoice);
                    if (radios.length > 0) {
                        const opts = [];
                        const seen = new Set();
                        radios.forEach(r => {
                            let lbl = '';
                            if (r.id) {
                                const l = container.querySelector(`label[for="${CSS.escape(r.id)}"]`);
                                if (l) lbl = l.innerText;
                            }
                            if (!lbl) { const pl = r.closest('label'); if (pl) lbl = pl.innerText; }
                            if (!lbl && r.parentElement) lbl = r.parentElement.innerText;
                            if (!lbl) lbl = r.value || r.name || r.id || '';
                            lbl = lbl.trim();
                            if (lbl && !seen.has(lbl)) { seen.add(lbl); opts.push(lbl); }
                        });
                        return { type: 'radio', question: extractQuestion(), options: opts };
                    }

                    // ── 2. Checkboxes ─────────────────────────────────────────
                    const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"], input.mcc__checkbox')).filter(isVisibleChoice);
                    if (checkboxes.length > 0) {
                        const opts = [];
                        const seen = new Set();
                        checkboxes.forEach(c => {
                            let lbl = '';
                            if (c.id) {
                                const l = container.querySelector(`label[for="${CSS.escape(c.id)}"]`);
                                if (l) lbl = l.innerText;
                            }
                            if (!lbl) { const pl = c.closest('label'); if (pl) lbl = pl.innerText; }
                            if (!lbl && c.parentElement) lbl = c.parentElement.innerText;
                            if (!lbl) lbl = c.value || c.name || c.id || '';
                            lbl = lbl.trim();
                            if (lbl && !seen.has(lbl)) { seen.add(lbl); opts.push(lbl); }
                        });
                        return { type: 'checkbox', question: extractQuestion(), options: opts };
                    }

                    // ── 3. Custom option-card lists / Chips ────────────────────
                    const optLists = container.querySelectorAll(
                        'ul[class*="option"], div[class*="options"], div[class*="choices"],'
                        + 'div[class*="radio-group"], div[class*="radio-wrap"], div.multicheckboxes-container, div.multiselectcheckboxes,'
                        + 'div.chipsContainer, div.chips, div[class*="Chips"], div[class*="chips"]'
                    );
                    for (const list of optLists) {
                        const nodes = Array.from(list.querySelectorAll(
                            'li, div[class*="option"], div[class*="radio"], label, span[class*="chip"], div[class*="Chip"], div[class*="chip"], div.chipItem'
                        )).filter(el => {
                            const s = window.getComputedStyle(el);
                            const r = el.getBoundingClientRect();
                            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && (el.innerText || '').trim().length > 0;
                        });
                        if (nodes.length >= 2) {
                            const opts = nodes.map(n => (n.innerText || '').trim()).filter(Boolean);
                            return { type: 'custom_options', question: extractQuestion(), options: opts };
                        }
                    }

                    // ── 4. Text input (classic chatbot / contenteditable) ──────
                    const TEXT_SELS = [
                        "[contenteditable='true']",
                        "input[placeholder*='Type message' i]",
                        "textarea[placeholder*='Type message' i]",
                        "input[placeholder*='Type here' i]",
                        "textarea[placeholder*='Type here' i]",
                        "input[placeholder*='message' i]",
                        "textarea[placeholder*='message' i]",
                    ];
                    for (const sel of TEXT_SELS) {
                        const el = container.querySelector(sel) || document.querySelector(sel);
                        if (el) {
                            const s = window.getComputedStyle(el);
                            const r = el.getBoundingClientRect();
                            if (s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0) {
                                return { type: 'text', question: extractQuestion(), options: [] };
                            }
                        }
                    }

                    return { type: 'none', question: extractQuestion(), options: [] };
                }
                """,
                user_first_name,
            )
        except Exception as e:
            print(f"[CHATBOT] _get_turn_input_info error: {e}")
            return {"type": "none", "question": "", "options": []}

        return info or {"type": "none", "question": "", "options": []}

    def _fill_panel_choice(self, target, answer: str, choice_type: str, options: list) -> bool:
        """
        Select a radio button, checkbox, or custom option card in the chatbot
        panel that best matches `answer`.
        """
        best = ai_filler.generate_answer(answer, "radio", options) if options else None
        if not best and options:
            best = options[0]
        best = (best or "").strip()
        print(f"[CHATBOT] Choice type={choice_type} | AI picked: '{best}' from {options}")

        if choice_type in ("radio", "checkbox"):
            clicked = target.evaluate(
                """
                ({ targetLabel, choiceType }) => {
                    const PANEL_SEL = [
                        'div[class*="chatbot"]', 'div[class*="drawer"]',
                        'div[role="dialog"]', 'div[class*="side-panel"]', '.applyForm',
                        'div[class*="modal"]', 'div[class*="apply"]',
                        'div[class*="popup"]', 'div[class*="overlay"]', 'form',
                    ];
                    let container = null;
                    for (const sel of PANEL_SEL) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const s = window.getComputedStyle(el);
                            if (s.display !== 'none' && s.visibility !== 'hidden') { container = el; break; }
                        }
                    }
                    if (!container) container = document.body;

                    const inputType = choiceType === 'checkbox' ? 'checkbox' : 'radio';
                    const inputs = Array.from(container.querySelectorAll(`input[type="${inputType}"], input.mcc__checkbox`));

                    const targetLower = (targetLabel || '').toLowerCase().trim();
                    let bestInp = null;
                    let bestScore = -1;
                    let selectedLabel = '';

                    inputs.forEach(inp => {
                        let lbl = '';
                        if (inp.id) {
                            const l = container.querySelector(`label[for="${CSS.escape(inp.id)}"]`);
                            if (l) lbl = l.innerText;
                        }
                        if (!lbl) { const pl = inp.closest('label'); if (pl) lbl = pl.innerText; }
                        if (!lbl && inp.parentElement) lbl = inp.parentElement.innerText;
                        if (!lbl) lbl = inp.value || inp.name || inp.id || '';
                        const norm = (lbl || '').toLowerCase().trim();

                        if (norm === targetLower && 100 > bestScore) { bestInp = inp; selectedLabel = (lbl || '').trim(); bestScore = 100; }
                        else if ((norm.includes(targetLower) || targetLower.includes(norm)) && 80 > bestScore) { bestInp = inp; selectedLabel = (lbl || '').trim(); bestScore = 80; }
                    });

                    if (!bestInp && inputs.length > 0) {
                        bestInp = inputs[0];
                        selectedLabel = bestInp.value || bestInp.id || '';
                    }
                    if (!bestInp) return { success: false };

                    const labelEl = (bestInp.id ? container.querySelector(`label[for="${CSS.escape(bestInp.id)}"]`) : null) || bestInp.closest('label') || bestInp.parentElement || bestInp;
                    labelEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    
                    // 1. Click the label (triggers native browser / React click handler)
                    labelEl.click();

                    // 2. Ensure React state recognizes the checked value using native setter
                    if (!bestInp.checked) {
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked')?.set;
                        if (nativeSetter) {
                            nativeSetter.call(bestInp, true);
                        } else {
                            bestInp.checked = true;
                        }
                        bestInp.dispatchEvent(new InputEvent('input', { bubbles: true }));
                        bestInp.dispatchEvent(new Event('change', { bubbles: true }));
                        bestInp.dispatchEvent(new Event('click', { bubbles: true }));
                    }

                    // 3. Remove 'disabled' class from send/save button if React was slow
                    const sendWrapper = container.querySelector('.send, [id*="sendMsg"]');
                    if (sendWrapper) {
                        sendWrapper.classList.remove('disabled');
                    }

                    return { success: true, isChecked: bestInp.checked, label: selectedLabel };
                }
                """,
                {"targetLabel": best, "choiceType": choice_type},
            )
            if clicked and clicked.get("success"):
                print(f"[CHATBOT] {choice_type} option '{clicked.get('label')}' selected (checked={clicked.get('isChecked')})")
                time.sleep(0.5)
                return True
            print(f"[CHATBOT] {choice_type} click failed in JS")
            return False

        elif choice_type == "custom_options":
            clicked = target.evaluate(
                """
                ({ targetLabel }) => {
                    const PANEL_SEL = [
                        'div[class*="chatbot"]', 'div[class*="drawer"]',
                        'div[role="dialog"]', 'div[class*="side-panel"]', '.applyForm',
                        'div[class*="modal"]', 'div[class*="apply"]',
                        'div[class*="popup"]', 'div[class*="overlay"]', 'form',
                    ];
                    let container = null;
                    for (const sel of PANEL_SEL) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const s = window.getComputedStyle(el);
                            if (s.display !== 'none' && s.visibility !== 'hidden') { container = el; break; }
                        }
                    }
                    if (!container) container = document.body;

                    const optLists = container.querySelectorAll(
                        'ul[class*="option"], div[class*="options"], div[class*="choices"],'
                        + 'div[class*="radio-group"], div[class*="radio-wrap"], div.chipsContainer, div.chips, div[class*="Chips"]'
                    );
                    const targetLower = (targetLabel || '').toLowerCase().trim();

                    for (const list of optLists) {
                        const nodes = Array.from(list.querySelectorAll(
                            'li, div[class*="option"], div[class*="radio"], label, span[class*="chip"], div[class*="Chip"], div[class*="chip"], div.chipItem'
                        )).filter(el => {
                            const s = window.getComputedStyle(el);
                            return s.display !== 'none' && s.visibility !== 'hidden' && (el.innerText || '').trim().length > 0;
                        });
                        if (nodes.length < 2) continue;

                        let bestNode = null;
                        for (const node of nodes) {
                            const t = (node.innerText || '').toLowerCase().trim();
                            if (t === targetLower || t.includes(targetLower) || targetLower.includes(t)) {
                                bestNode = node; break;
                            }
                        }
                        if (!bestNode) bestNode = nodes[0];
                        bestNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        bestNode.click();
                        return true;
                    }
                    return false;
                }
                """,
                {"targetLabel": best},
            )
            if clicked:
                print("[CHATBOT] Custom option card selected")
                time.sleep(0.4)
                return True
            print("[CHATBOT] Custom option card click failed")
            return False

        return False

    def _save_debug_screenshot(self, page: Page, tag: str) -> None:
        """Save a timestamped PNG for post-failure diagnosis (silent on error)."""
        try:
            os.makedirs("debug_screenshots", exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join("debug_screenshots", f"naukri_chatbot_{tag}_{ts}.png")
            page.screenshot(path=path)
            print(f"[DEBUG] Screenshot saved: {path}")
        except Exception as e:
            print(f"[DEBUG] Screenshot failed: {e}")

    def _record_success(self, job: Dict, status: str = "applied") -> bool:
        db.add_job(
            job.get("link"),
            job.get("company", "Unknown"),
            job.get("role", "Unknown"),
            status=status,
        )
        print(f"Naukri application recorded as {status}")
        return True
