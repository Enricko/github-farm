"""
Undetected ChromeDriver (UC) Signup Flow for GitHub.
Ported and adapted from bercocok-tanam with warm cookies, human typing, and IMAP OTP support.
Bypasses DataDome and Playwright CDP detection.
"""
import os
import re
import sys
import json
import time
import random
import string
import tempfile
import asyncio
from typing import Dict, Any, Optional

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False


class UCSignupFlow:
    def __init__(self, headless: bool = False, proxy: Optional[str] = None):
        self.headless = headless
        self.proxy = proxy
        self.driver = None
        self.user_data_dir = None

    def sleep(self, min_sec: float, max_sec: Optional[float] = None):
        if max_sec is None:
            time.sleep(min_sec)
        else:
            time.sleep(min_sec + random.random() * (max_sec - min_sec))

    def human_type(self, element, text: str, min_delay: float = 0.02, max_delay: float = 0.08):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))

    def launch(self):
        if not UC_AVAILABLE:
            raise RuntimeError(
                "undetected-chromedriver is not installed!\n"
                "Please run in PowerShell: pip install undetected-chromedriver selenium"
            )

        print("  [1/6] Launching undetected Chrome browser...")
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=BlockThirdPartyCookies")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--window-size=1920,1080")

        # Linux root compatibility
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

        if self.proxy:
            proxy_clean = self.proxy.replace("http://", "").replace("https://", "")
            options.add_argument(f"--proxy-server=http://{proxy_clean}")
            print(f"  [INFO] Using proxy: {self.proxy}")

        if self.headless:
            options.add_argument("--headless=new")
            print("  [INFO] Headless mode enabled")
        else:
            print("  [INFO] Visible browser mode (headed)")

        # Unique profile dir
        self.user_data_dir = tempfile.mkdtemp(prefix="uc_chrome_farm_")
        options.add_argument(f"--user-data-dir={self.user_data_dir}")

        # Detect Chrome version if possible
        chrome_version = None
        try:
            import subprocess
            if sys.platform == "win32":
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                    ver, _ = winreg.QueryValueEx(key, "version")
                    chrome_version = int(ver.split(".")[0])
                except Exception:
                    pass
            elif os.path.exists("/usr/bin/google-chrome"):
                res = subprocess.run(["/usr/bin/google-chrome", "--version"], capture_output=True, text=True)
                m = re.search(r"(\d+)\.", res.stdout)
                if m:
                    chrome_version = int(m.group(1))
        except Exception:
            pass

        launch_kwargs = {"options": options}
        if chrome_version:
            launch_kwargs["version_main"] = chrome_version
            print(f"  [INFO] Detected Chrome major version: {chrome_version}")

        self.driver = uc.Chrome(**launch_kwargs)
        self.driver.set_page_load_timeout(60)
        print("  [OK] Undetected Chrome launched successfully!")

    def inject_warm_cookies(self):
        print("  [2/6] Warming session & injecting cookies...")
        try:
            self.driver.get("https://github.com")
            self.sleep(2, 3)

            cookies = [
                {"domain": "github.com", "name": "_octo", "path": "/", "secure": True, "value": "GH1.1.723845500.1784644460"},
                {"domain": "github.com", "name": "GHCC", "path": "/", "secure": True, "value": "Required:1-Analytics:0-SocialMedia:0-Advertising:0"},
                {"domain": "github.com", "name": "cpu_bucket", "path": "/", "secure": True, "value": "sm"},
                {"domain": "github.com", "name": "preferred_color_mode", "path": "/", "secure": True, "value": "dark"},
                {"domain": "github.com", "name": "tz", "path": "/", "secure": True, "value": "Asia%2FJakarta"},
            ]
            for c in cookies:
                try:
                    self.driver.add_cookie(c)
                except Exception:
                    pass
            self.sleep(1)
            print("  [OK] Natural cookies injected")
        except Exception as e:
            print(f"  [WARN] Cookie injection error: {e}")

    def wait_for_challenge(self, max_wait: int = 60) -> bool:
        """Wait if DataDome challenge appears; allows manual solve in headed mode."""
        start_time = time.time()
        warned = False
        while time.time() - start_time < max_wait:
            page_source = self.driver.page_source.lower()
            current_url = self.driver.current_url.lower()

            # Check if signup form email input is ready
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, "input#email, input[type='email']")
                if elem.is_displayed():
                    return True
            except NoSuchElementException:
                pass

            # Check if blocked
            if "temporarily restricted" in page_source:
                print("  [ERROR] GitHub displayed IP restriction. IP cooldown active!")
                return False

            # Check if challenge is on screen
            if "var dd=" in page_source or "verification required" in page_source or "unusual activity" in page_source:
                if not warned:
                    print("\n" + "=" * 60)
                    print("⚠️  VERIFICATION CHALLENGE TERDETEKSI!")
                    print("Silakan geser slider atau selesaikan puzzle di jendela Chrome.")
                    print("Script menunggu kamu menyelesaikan verifikasi...")
                    print("=" * 60 + "\n")
                    warned = True
                self.sleep(2)
                continue

            self.sleep(1)

        return False

    def add_human_behavior(self):
        """Add subtle human-like behavior (scroll & mouse move) like bercocok-tanam"""
        try:
            self.driver.execute_script(f"window.scrollBy(0, {random.randint(0, 100)});")
        except Exception:
            pass
        self.sleep(0.3, 0.6)
        try:
            actions = ActionChains(self.driver)
            actions.move_by_offset(random.randint(5, 30), random.randint(5, 30)).perform()
        except Exception:
            pass
        self.sleep(0.2, 0.5)

    def fill_form(self, email: str, password: str, username: str) -> bool:
        print(f"  [3/6] Navigating to https://github.com/signup...")
        self.driver.get("https://github.com/signup")
        self.sleep(2, 4)

        # Wait for form or challenge
        ready = self.wait_for_challenge(max_wait=60)
        if not ready:
            try:
                self.driver.find_element(By.CSS_SELECTOR, "input#email, input[type='email']")
            except NoSuchElementException:
                return False

        self.add_human_behavior()

        # 1. Fill Email
        print(f"  [4/6] [EMAIL] Waiting for email field...")
        email_elem = WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#email, input[type='email']"))
        )
        print("  [EMAIL] Field found, typing email...")
        email_elem.click()
        self.sleep(0.2, 0.4)
        for char in email:
            email_elem.send_keys(char)
            self.sleep(0.01, 0.03)
        print(f"  [EMAIL] ✅ Email entered: {email}")
        self.add_human_behavior()

        # 2. Fill Password
        print(f"  [PASSWORD] Waiting for password field...")
        pwd_elem = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#password, input[type='password']"))
        )
        print("  [PASSWORD] Field found, typing password...")
        pwd_elem.click()
        self.sleep(0.2, 0.4)
        for char in password:
            pwd_elem.send_keys(char)
            self.sleep(0.01, 0.03)
        print("  [PASSWORD] ✅ Password entered")
        self.add_human_behavior()

        # 3. Fill Username
        print(f"  [USERNAME] Waiting for username field...")
        user_elem = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#login, input[name='user[login]']"))
        )
        print("  [USERNAME] Field found, typing username...")
        user_elem.click()
        self.sleep(0.2, 0.4)
        for char in username:
            user_elem.send_keys(char)
            self.sleep(0.01, 0.03)
        print(f"  [USERNAME] ✅ Username entered: {username}")
        self.add_human_behavior()

        # Uncheck marketing checkboxes if present
        print("  [CHECKBOXES] Checking opt-in checkboxes...")
        for selector in ["input#user_signup\\[copilot_opt_in\\]", "input#user_signup\\[marketing_consent\\]"]:
            try:
                cb = self.driver.find_element(By.CSS_SELECTOR, selector)
                if cb.is_selected():
                    cb.click()
                    self.sleep(0.2)
                    print(f"  [CHECKBOXES] ✅ Unchecked {selector}")
            except Exception:
                pass

        self.sleep(1, 2)
        self.add_human_behavior()

        # Submit form (STRICTLY filter out third-party Google/Apple/OAuth buttons!)
        print("  [SUBMIT] Looking for Create account submit button...")
        submit_btn = None
        buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
        print(f"  [SUBMIT] Found {len(buttons)} candidate buttons")

        # Method 1: Look for button with text "Create account"
        for b in buttons:
            btn_text = b.text.strip().lower()
            if "create account" in btn_text:
                submit_btn = b
                print(f"  [SUBMIT] ✅ Found 'Create account' button")
                break

        # Method 2: Filter out Google, Apple, and OAuth buttons
        if not submit_btn:
            print("  [SUBMIT] Finding primary submit button (excluding Google/Apple)...")
            for b in reversed(buttons):
                btn_text = b.text.strip()
                btn_lower = btn_text.lower()
                # Skip any third-party auth button!
                if any(x in btn_lower for x in ["google", "apple", "passkey", "sign in", "log in"]):
                    continue
                submit_btn = b
                print(f"  [SUBMIT] ✅ Using button: '{btn_text}'")
                break

        # Method 3: Selector fallback
        if not submit_btn:
            for sel in ["form#signup-form button[type='submit']", "button.js-octocaptcha-form-submit"]:
                try:
                    submit_btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if submit_btn:
                        break
                except Exception:
                    pass

        if submit_btn:
            self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
            self.sleep(0.5)
            submit_btn.click()
            print("  [SUBMIT] ✅ Clicked Create account button")
        else:
            raise RuntimeError("Could not find Create account button")

        self.sleep(5, 7)
        return True

    def enter_otp(self, otp_code: str) -> bool:
        print(f"  [5/6] Entering 8-digit OTP launch code: {otp_code}...")
        digits = list(otp_code.strip())
        if len(digits) != 8:
            print(f"  [WARN] OTP length is {len(digits)}, expected 8")

        # Try digit inputs #launch-code-0 .. #launch-code-7
        try:
            for i in range(min(8, len(digits))):
                field = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f"input#launch-code-{i}"))
                )
                field.click()
                field.send_keys(digits[i])
                self.sleep(0.15, 0.35)
            print("  [OK] All 8 digits entered")
        except Exception:
            # Fallback single OTP input
            try:
                single_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='otp'], input#otp")
                single_field.send_keys(otp_code)
                print("  [OK] OTP entered in single field")
            except Exception as e:
                print(f"  [ERROR] Failed to enter OTP: {e}")
                return False

        # Wait for redirect to dashboard or logged-in state
        print("  [INFO] Waiting for account initialization / dashboard...")
        try:
            WebDriverWait(self.driver, 45).until(
                lambda d: "/dashboard" in d.current_url or "/join/welcome" in d.current_url or "github.com" in d.current_url and "/signup" not in d.current_url
            )
            print(f"  [SUCCESS] Account successfully created! Current URL: {self.driver.current_url}")
            return True
        except TimeoutException:
            print("  [INFO] Proceeding with current session...")
            return True

    def get_cookies_dict(self) -> Dict[str, str]:
        cookies = self.driver.get_cookies()
        return {c["name"]: c["value"] for c in cookies if "github.com" in c.get("domain", "")}

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

        if self.user_data_dir and os.path.exists(self.user_data_dir):
            try:
                import shutil
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
            except Exception:
                pass
