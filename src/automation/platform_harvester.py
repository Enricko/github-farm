"""
Platform Harvester — OAuth token extraction from target platforms.
Visits each platform, initiates GitHub OAuth login, captures token/session.
"""
import asyncio
import random
import re
import json
from typing import Dict, Any, Optional, List


PLATFORMS = {
    "codebuddy": {
        "name": "CodeBuddy Global",
        "signup_url": "https://www.codebuddy.ai/signup",
        "login_url": "https://www.codebuddy.ai/login",
        "oauth_button": "button:has-text('GitHub'), a:has-text('GitHub'), a[href*='github']",
        "token_pattern": r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
        "token_storage": "localStorage",
        "token_key": "token",
        "allowance": "250 Bonus + 100 Monthly Credits",
    },
    "gorouter": {
        "name": "GoRouter",
        "signup_url": "https://gorouter.app/signup",
        "login_url": "https://gorouter.app/login",
        "oauth_button": "button:has-text('GitHub'), a:has-text('GitHub'), a[href*='github']",
        "token_pattern": r"sk-[A-Za-z0-9_-]+",
        "token_storage": "localStorage",
        "token_key": "apiKey",
        "allowance": "$70.00 USD Welcome + $5-$10/Daily Check-in",
    },
    "tabiai": {
        "name": "Tabi AI",
        "signup_url": "https://tabitoken.com/signup",
        "login_url": "https://tabitoken.com/login",
        "oauth_button": "button:has-text('GitHub'), a:has-text('GitHub'), a[href*='github']",
        "token_pattern": r"tb-[A-Za-z0-9_-]+",
        "token_storage": "localStorage",
        "token_key": "token",
        "allowance": "$120.00 USD Developer Grant + $5-$10/Daily Check-in",
    },
}


class PlatformHarvester:
    def __init__(self, browser_engine):
        self.engine = browser_engine
        self.page = browser_engine.page

    async def harvest(self, platform_id: str, github_session: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Harvest OAuth token from a target platform.
        1. Navigate to platform login
        2. Click 'Sign in with GitHub'
        3. Authorize on GitHub (if prompted)
        4. Capture token from response/localStorage
        """
        config = PLATFORMS.get(platform_id)
        if not config:
            return {"success": False, "error": f"Unknown platform: {platform_id}"}

        try:
            # Set GitHub cookies if we have them
            if github_session:
                cookies = []
                for name, value in github_session.items():
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": ".github.com",
                        "path": "/",
                    })
                await self.engine.context.add_cookies(cookies)

            # Navigate to platform
            await self.page.goto(config["login_url"], wait_until="domcontentloaded")
            await self.engine.random_delay(2.0, 4.0)

            # Click GitHub OAuth button
            await self._click_oauth_button(config["oauth_button"])
            await self.engine.random_delay(3.0, 5.0)

            # Handle GitHub authorization if prompted
            await self._handle_github_authorize()
            await self.engine.random_delay(3.0, 5.0)

            # Capture token
            token = await self._capture_token(config)
            if token:
                return {
                    "success": True,
                    "platform": platform_id,
                    "platform_name": config["name"],
                    "token": token,
                    "allowance": config["allowance"],
                    "url": self.page.url,
                }

            # Try alternative: intercept network requests
            token = await self._capture_from_network(config)
            if token:
                return {
                    "success": True,
                    "platform": platform_id,
                    "platform_name": config["name"],
                    "token": token,
                    "allowance": config["allowance"],
                    "url": self.page.url,
                }

            screenshot = await self.engine.screenshot(f"/tmp/github-farm-harvest-{platform_id}.png")
            return {
                "success": False,
                "error": "Token not found after OAuth flow",
                "platform": platform_id,
                "url": self.page.url,
                "screenshot": screenshot,
            }

        except Exception as e:
            screenshot = await self.engine.screenshot(f"/tmp/github-farm-harvest-error-{platform_id}.png")
            return {"success": False, "error": str(e), "platform": platform_id, "screenshot": screenshot}

    async def _click_oauth_button(self, button_selector: str):
        """Click the OAuth button on the platform."""
        selectors = [s.strip() for s in button_selector.split(",")]
        for sel in selectors:
            try:
                await self.engine.safe_click(sel, timeout=10000)
                return
            except Exception:
                continue
        raise Exception(f"Could not find OAuth button: {button_selector}")

    async def _handle_github_authorize(self):
        """Handle GitHub OAuth authorization prompt."""
        current_url = self.page.url
        if "github.com" not in current_url:
            return

        # Check if we need to authorize
        authorize_selectors = [
            "button:has-text('Authorize')",
            "button:has-text('Grant')",
            "button:has-text('Allow')",
            "input[type='submit'][value='Authorize']",
            "button[data-oauth-scopes]",
        ]

        for sel in authorize_selectors:
            try:
                await self.engine.safe_click(sel, timeout=5000)
                await self.engine.random_delay(2.0, 3.0)
                return
            except Exception:
                continue

    async def _capture_token(self, config: Dict) -> Optional[str]:
        """Capture token from localStorage or page content."""
        try:
            # Try localStorage
            token = await self.page.evaluate(
                f"localStorage.getItem('{config['token_key']}')"
            )
            if token:
                return token
        except Exception:
            pass

        try:
            # Try sessionStorage
            token = await self.page.evaluate(
                f"sessionStorage.getItem('{config['token_key']}')"
            )
            if token:
                return token
        except Exception:
            pass

        try:
            # Try cookies
            cookies = await self.engine.context.cookies()
            for c in cookies:
                if config["token_key"].lower() in c["name"].lower():
                    return c["value"]
        except Exception:
            pass

        return None

    async def _capture_from_network(self, config: Dict) -> Optional[str]:
        """Capture token from network responses."""
        try:
            responses = []
            self.page.on("response", lambda r: responses.append(r))

            # Reload to trigger network calls
            await self.page.reload(wait_until="networkidle")
            await self.engine.random_delay(2.0, 3.0)

            for resp in responses:
                try:
                    body = await resp.text()
                    match = re.search(config["token_pattern"], body)
                    if match:
                        return match.group(0)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    async def harvest_all(self, github_session: Dict[str, str] = None,
                          platforms: List[str] = None) -> Dict[str, Any]:
        """Harvest tokens from multiple platforms."""
        target_platforms = platforms or list(PLATFORMS.keys())
        results = {}

        for pid in target_platforms:
            result = await self.harvest(pid, github_session)
            results[pid] = result
            await self.engine.random_delay(5.0, 10.0)  # Rate limit between platforms

        return results
