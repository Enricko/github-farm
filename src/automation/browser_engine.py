"""
Browser Engine — Camoufox-based stealth browser automation with Playwright fallback.
Uses Camoufox (stealth Firefox fork) to bypass DataDome, Cloudflare, and bot detection.
"""
import asyncio
import random
import os
import sys
from typing import Optional, Dict, Any


class BrowserEngine:
    def __init__(self, headless: bool = True, proxy: str = None, user_agent: str = None):
        self.headless = headless
        self.proxy = proxy
        self.user_agent = user_agent
        self.browser = None
        self.context = None
        self.page = None
        self._camoufox = None
        self._pw = None

    async def launch(self):
        # 1. Try Camoufox (Stealth Firefox)
        try:
            from camoufox.async_api import AsyncCamoufox

            launch_args = {
                "headless": self.headless,
            }

            # Only add sandbox flags on Linux when running as root
            if sys.platform != "win32":
                try:
                    if os.geteuid() == 0:
                        launch_args["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]
                except AttributeError:
                    pass

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

            if self.browser.contexts:
                self.context = self.browser.contexts[0]
            else:
                self.context = await self.browser.new_context()

            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()

            return self.page

        except Exception as e:
            print(f"  [WARN] Camoufox launch failed ({e}). Falling back to Playwright Chromium...")

        # 2. Fallback to Playwright with real Chrome / Edge / Chromium + stealth
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()

        pw_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ]
        pw_proxy = None
        if self.proxy:
            pw_proxy = {"server": self.proxy}

        # Auto-detect installed browser: Chrome -> Edge -> Bundled Chromium
        self.browser = None
        for channel in ["chrome", "msedge", None]:
            try:
                launch_opts = {
                    "headless": self.headless,
                    "args": pw_args,
                    "proxy": pw_proxy,
                }
                if channel:
                    launch_opts["channel"] = channel
                self.browser = await self._pw.chromium.launch(**launch_opts)
                channel_name = channel or "bundled chromium"
                print(f"  [INFO] Launched browser using: {channel_name}")
                break
            except Exception:
                continue

        if not self.browser:
            raise RuntimeError(
                "No browser found! Please run: playwright install chromium"
            )

        self.context = await self.browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            user_agent=self.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(self.context)
        except Exception:
            pass

        self.page = await self.context.new_page()
        return self.page

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self._camoufox:
                await self._camoufox.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
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
        path = path or os.path.join(os.getcwd(), "data", "debug.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await self.page.screenshot(path=path, full_page=True)
        return path
