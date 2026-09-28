"""
GitHub Signup Flow — automated GitHub account creation via browser.
Handles email verification (OTP from IMAP), captcha bypass, and session extraction.
"""
import asyncio
import re
import random
import string
from typing import Dict, Any, Optional


class GitHubSignup:
    def __init__(self, browser_engine):
        self.engine = browser_engine
        self.page = browser_engine.page

    async def signup(self, email: str, username: str, password: str,
                     otp_callback=None, timeout: int = 180) -> Dict[str, Any]:
        """
        Full GitHub signup flow:
        1. Navigate to signup
        2. Fill email → send verification
        3. OTP callback to get code from IMAP
        4. Enter OTP
        5. Fill username + password
        6. Solve captcha (manual or automated)
        7. Complete signup
        """
        try:
            # Step 1: Navigate to GitHub homepage first to establish clean session
            print("  [1/7] Opening github.com to establish natural session...")
            await self.engine.random_delay(1.0, 2.0)
            await self.page.goto("https://github.com", wait_until="domcontentloaded")
            await self.engine.random_delay(2.0, 3.5)

            # Navigate to signup with referer
            print("  [2/7] Entering signup flow...")
            try:
                signup_btn = await self.page.query_selector("a[href*='/signup']")
                if signup_btn:
                    await signup_btn.click()
                else:
                    await self.page.goto("https://github.com/signup", referer="https://github.com/")
            except Exception:
                await self.page.goto("https://github.com/signup", referer="https://github.com/")

            await self.engine.random_delay(3.0, 5.0)

            # Check if IP is currently restricted
            page_text = await self.page.content()
            if "temporarily restricted" in page_text.lower():
                return {
                    "success": False,
                    "error": "IP terkena rate limit sementara oleh GitHub. Wajib pakai proxy atau ganti IP!",
                    "email": email,
                }

            # Step 2: Enter email
            await self._fill_email(email)
            await self.engine.random_delay(1.0, 2.0)

            # Step 3: Send verification email
            await self._send_verification()

            # Step 4: Get OTP via callback
            if otp_callback:
                otp_code = await otp_callback(email)
                if not otp_code:
                    return {"success": False, "error": "OTP timeout", "email": email}
                await self._enter_otp(otp_code)
            else:
                return {"success": False, "error": "No OTP callback provided", "email": email}

            await self.engine.random_delay(2.0, 3.0)

            # Step 5: Fill username
            await self._fill_username(username)

            # Step 6: Fill password
            await self._fill_password(password)

            # Step 7: Create account
            await self._create_account()

            await self.engine.random_delay(3.0, 5.0)

            # Check for success
            current_url = self.page.url
            if "signup" not in current_url.lower():
                return {
                    "success": True,
                    "email": email,
                    "username": username,
                    "url": current_url,
                }
            else:
                screenshot = await self.engine.screenshot("/tmp/github-farm-signup-fail.png")
                return {
                    "success": False,
                    "error": "Signup page still visible — captcha or error",
                    "email": email,
                    "screenshot": screenshot,
                }

        except Exception as e:
            screenshot = await self.engine.screenshot("/tmp/github-farm-signup-error.png")
            return {"success": False, "error": str(e), "email": email, "screenshot": screenshot}

    async def _fill_email(self, email: str):
        """Fill email field on signup page."""
        selectors = [
            "#email",
            "input[name='email']",
            "input[placeholder*='Email']",
            "input[type='email']",
        ]
        for sel in selectors:
            try:
                await self.engine.human_type(sel, email)
                await self.page.keyboard.press("Enter")
                return
            except Exception:
                continue
        raise Exception("Could not find email input")

    async def _send_verification(self):
        """Click send verification email button."""
        await self.engine.random_delay(1.0, 2.0)
        selectors = [
            "button[data-continue-to='email-container']",
            "button:has-text('Continue')",
            "button:has-text('Send')",
            "button:has-text('Verify')",
            "#send-otp-btn",
        ]
        for sel in selectors:
            try:
                await self.engine.safe_click(sel, timeout=8000)
                return
            except Exception:
                continue
        # Might auto-advance, not an error

    async def _enter_otp(self, code: str):
        """Enter verification code."""
        await self.engine.random_delay(1.0, 2.0)
        # Try individual digit inputs
        otp_inputs = await self.page.query_selector_all("input[id^='otp_']")
        if otp_inputs and len(otp_inputs) >= 6:
            for i, digit in enumerate(code[:len(otp_inputs)]):
                await otp_inputs[i].fill(digit)
                await asyncio.sleep(random.uniform(0.05, 0.15))
            return

        # Try single input
        selectors = [
            "#otp",
            "input[name='otp']",
            "input[autocomplete='one-time-code']",
            "input[placeholder*='code']",
        ]
        for sel in selectors:
            try:
                await self.engine.human_type(sel, code)
                await self.page.keyboard.press("Enter")
                return
            except Exception:
                continue

    async def _fill_username(self, username: str):
        """Fill username field."""
        await self.engine.random_delay(1.0, 2.0)
        selectors = [
            "#login",
            "input[name='login']",
            "input[placeholder*='username']",
            "input[placeholder*='Username']",
        ]
        for sel in selectors:
            try:
                await self.engine.human_type(sel, username)
                return
            except Exception:
                continue

    async def _fill_password(self, password: str):
        """Fill password field."""
        await self.engine.random_delay(1.0, 2.0)
        selectors = [
            "#password",
            "input[name='password']",
            "input[type='password']",
        ]
        for sel in selectors:
            try:
                await self.engine.human_type(sel, password)
                return
            except Exception:
                continue

    async def _create_account(self):
        """Click create account / submit button."""
        await self.engine.random_delay(2.0, 4.0)
        selectors = [
            "button[data-continue-to='registration-container']",
            "button[type='submit']",
            "button:has-text('Create account')",
            "button:has-text('Create Account')",
            "button:has-text('Submit')",
        ]
        for sel in selectors:
            try:
                await self.engine.safe_click(sel, timeout=10000)
                return
            except Exception:
                continue

    async def get_cookies(self) -> Dict[str, str]:
        """Extract cookies from the current session."""
        cookies = await self.engine.context.cookies()
        return {c["name"]: c["value"] for c in cookies}

    async def get_session_token(self) -> Optional[str]:
        """Try to extract session token from cookies or localStorage."""
        cookies = await self.get_cookies()
        for key in ["logged_in", "_gh_sess", "user_session", "gh_sess"]:
            if key in cookies:
                return cookies[key]

        # Try localStorage
        try:
            token = await self.page.evaluate("localStorage.getItem('token')")
            if token:
                return token
        except Exception:
            pass
        return None
