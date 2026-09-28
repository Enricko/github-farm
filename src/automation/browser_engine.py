"""
Browser Engine — Camoufox-based stealth browser automation.
Uses Camoufox (stealth Firefox fork) to bypass DataDome, Cloudflare, and bot detection.
"""
import asyncio
import random
import os
import sys
from typing import Optional, Dict, Any

sys.path.insert(0, "/root/Boterdrop-Solver")


class BrowserEngine:
    def __init__(self, headless: bool = True, proxy: str = None, user_agent: str = None):
        self.headless = headless
        self.proxy = proxy
        self.user_agent = user_agent  # Ignored — Camoufox handles fingerprinting
        self.browser = None
        self.context = None
        self.page = None
        self._camoufox = None

    async def launch(self):
        from camoufox.async_api import AsyncCamoufox

        launch_args = {
            "headless": self.headless,
            "exclude_addons": [],  # Keep UBO for ad blocking
            "args": ["--no-sandbox", "--disable-setuid-sandbox"],
        }

        if self.proxy:
            from urllib.parse import urlparse
            parsed = urlparse(self.proxy)
            server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
            if parsed.username and parsed.password:
                launch_args["proxy"] = {
                    "server": server,
                    "username": parsed.username,
                    "password": parsed.password,
                }
            else:
                launch_args["proxy"] = {"server": server}

        self._camoufox = AsyncCamoufox(**launch_args)
        self.browser = await self._camoufox.start()

        # Get existing context or create new
        if self.browser.contexts:
            self.context = self.browser.contexts[0]
        else:
            self.context = await self.browser.new_context()

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        return self.page

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass

    async def random_delay(self, min_s: float = 1.0, max_s: float = 3.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def human_type(self, selector: str, text: str, delay: int = 80):
        """Type like a human — random delays between keystrokes."""
        element = await self.page.wait_for_selector(selector, timeout=15000)
        await element.click()
        for char in text:
            await self.page.keyboard.type(char, delay=random.randint(delay // 2, delay * 2))
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.3, 0.8))

    async def safe_click(self, selector: str, timeout: int = 15000):
        """Click with wait + random delay."""
        await self.page.wait_for_selector(selector, timeout=timeout)
        await self.random_delay(0.3, 0.8)
        await self.page.click(selector)

    async def wait_and_extract(self, selector: str, attribute: str = "textContent",
                                timeout: int = 15000) -> Optional[str]:
        try:
            el = await self.page.wait_for_selector(selector, timeout=timeout)
            if el:
                return await el.get_attribute(attribute) if attribute != "textContent" else await el.text_content()
        except Exception:
            return None
        return None

    async def screenshot(self, path: str = None) -> str:
        path = path or "/tmp/github-farm-debug.png"
        await self.page.screenshot(path=path, full_page=True)
        return path
