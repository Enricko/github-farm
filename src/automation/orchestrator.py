"""
Orchestrator — Full automated pipeline.
Combines email generation → GitHub signup → OTP → platform harvest → 9Router inject.
"""
import asyncio
import json
import random
import string
import time
import datetime
from typing import Dict, Any, Optional, List

from src.generator.email_engine import generate_dot_trick_emails, generate_plus_address_emails
from src.imap.otp_listener import ImapOtpListener
from src.adapters.adapters import CodeBuddyAdapter, GoRouterAdapter, TabiAIAdapter
from src.injector.db_injector import DatabaseInjector
from src.automation.account_manager import AccountManager
from src.automation.browser_engine import BrowserEngine
from src.automation.github_signup import GitHubSignup
from src.automation.platform_harvester import PlatformHarvester, PLATFORMS


def _random_password(length: int = 16) -> str:
    """Generate a strong random password."""
    chars = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pw = "".join(random.choices(chars, k=length))
        if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in "!@#$%" for c in pw)):
            return pw


def _random_username(base: str = None) -> str:
    """Generate a random username."""
    if base:
        suffix = "".join(random.choices(string.digits, k=4))
        return f"{base}{suffix}"
    return "user" + "".join(random.choices(string.digits, k=8))


ADAPTERS = {
    "codebuddy": CodeBuddyAdapter,
    "gorouter": GoRouterAdapter,
    "tabiai": TabiAIAdapter,
}


class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.accounts = AccountManager(config.get("data_dir"))
        self.injector = DatabaseInjector(config.get("db_path", "~/.9router/db/data.sqlite"))

        imap_cfg = config.get("imap", {})
        self.otp_listener = ImapOtpListener(
            server=imap_cfg.get("server", "imap.gmail.com"),
            username=imap_cfg.get("username", ""),
            password=imap_cfg.get("app_password", ""),
            port=imap_cfg.get("port", 993),
        )

        self.browser = BrowserEngine(
            headless=config.get("headless", True),
            proxy=config.get("proxy"),
        )

        self.results = {
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "accounts_created": 0,
            "accounts_failed": 0,
            "tokens_harvested": 0,
            "tokens_injected": 0,
            "platforms": {},
            "log": [],
        }

    async def _otp_callback(self, email: str) -> Optional[str]:
        """IMAP OTP callback for GitHub verification."""
        timeout = self.config.get("otp_timeout", 120)
        return self.otp_listener.listen_github_otp(
            target_email=email,
            timeout_sec=timeout,
        )

    async def run_single(self, email: str = None, username: str = None,
                         password: str = None, platforms: List[str] = None,
                         inject: bool = True) -> Dict[str, Any]:
        """Run full pipeline for a single account."""
        username = username or _random_username()
        password = password or _random_password()
        target_platforms = platforms or list(PLATFORMS.keys())

        print(f"\n{'='*60}")
        print(f"[FARM] Account: {email or 'auto-generate'}")
        print(f"{'='*60}")

        # Step 1: Launch browser
        print("[1/5] Launching browser...")
        await self.browser.launch()
        github = GitHubSignup(self.browser)

        # Step 2: GitHub signup
        print("[2/5] Signing up on GitHub...")
        signup_result = await github.signup(
            email=email,
            username=username,
            password=password,
            otp_callback=self._otp_callback,
        )

        if not signup_result.get("success"):
            self.results["accounts_failed"] += 1
            self.accounts.mark_failed(email or "", signup_result.get("error", "signup failed"))
            print(f"  [FAIL] {signup_result.get('error')}")
            await self.browser.close()
            return signup_result

        self.results["accounts_created"] += 1
        self.accounts.add(
            email=signup_result["email"],
            username=signup_result["username"],
            password=password,
            status="created",
        )
        self.accounts.update_github_status(signup_result["email"], "created")
        print(f"  [OK] GitHub account created: {signup_result['username']}")

        # Step 3: Extract GitHub session
        print("[3/5] Extracting GitHub session...")
        github_session = await github.get_cookies()
        session_token = await github.get_session_token()
        if session_token:
            github_session["gh_sess"] = session_token
        print(f"  [OK] Session cookies: {len(github_session)}")

        # Step 4: Harvest platform tokens
        print(f"[4/5] Harvesting tokens from {len(target_platforms)} platforms...")
        harvester = PlatformHarvester(self.browser)
        harvest_results = await harvester.harvest_all(github_session, target_platforms)

        for pid, result in harvest_results.items():
            if result.get("success"):
                self.results["tokens_harvested"] += 1
                self.accounts.add_platform_token(
                    signup_result["email"], pid, result["token"],
                    extra={"allowance": result.get("allowance")}
                )
                print(f"  [OK] {result['platform_name']}: token captured")
            else:
                print(f"  [FAIL] {pid}: {result.get('error')}")

        # Step 5: Inject to 9Router
        if inject:
            print("[5/5] Injecting to 9Router...")
            for pid, result in harvest_results.items():
                if not result.get("success"):
                    continue
                adapter_cls = ADAPTERS.get(pid)
                if not adapter_cls:
                    continue
                adapter = adapter_cls()
                if pid == "codebuddy":
                    parsed = adapter.parse_session(result["token"])
                else:
                    parsed = adapter.parse_session(result["token"], signup_result["email"])

                inj_result = self.injector.inject_session(parsed)
                if inj_result.get("success"):
                    self.results["tokens_injected"] += 1
                    self.accounts.mark_injected(signup_result["email"], pid)
                    print(f"  [OK] {pid} → {inj_result.get('name')}")
                else:
                    print(f"  [FAIL] {pid} inject: {inj_result.get('error')}")
        else:
            print("[5/5] Skipping 9Router injection (inject=False)")

        await self.browser.close()

        # Compile result
        account_result = {
            "email": signup_result["email"],
            "username": signup_result["username"],
            "github": "created",
            "platforms": {
                pid: {"success": r.get("success"), "token": r.get("token", "")[:20] + "..." if r.get("token") else None}
                for pid, r in harvest_results.items()
            },
        }
        self.results["log"].append(account_result)
        return account_result

    async def run_batch(self, count: int = 5, base_email: str = None,
                        domain: str = "gmail.com", email_type: str = "dot",
                        platforms: List[str] = None, inject: bool = True,
                        delay_min: int = 30, delay_max: int = 90) -> Dict[str, Any]:
        """Run pipeline for multiple accounts."""
        print(f"\n{'#'*60}")
        print(f"#  GITHUB FARM — BATCH MODE")
        print(f"#  Target: {count} accounts")
        print(f"#  Email: {base_email}@{domain} ({email_type})")
        print(f"#  Platforms: {platforms or list(PLATFORMS.keys())}")
        print(f"{'#'*60}\n")

        # Generate email aliases
        if base_email:
            if email_type == "plus":
                emails = generate_plus_address_emails(base_email, domain, "gh", count)
            else:
                emails = generate_dot_trick_emails(base_email, domain, count)
        else:
            # Generate random emails
            emails = [None] * count  # Will use random generation

        batch_start = time.time()

        for i, email in enumerate(emails, 1):
            print(f"\n{'='*60}")
            print(f"[BATCH {i}/{count}] Starting...")
            print(f"{'='*60}")

            username = _random_username("ghuser")
            password = _random_password()

            try:
                result = await self.run_single(
                    email=email,
                    username=username,
                    password=password,
                    platforms=platforms,
                    inject=inject,
                )
            except Exception as e:
                print(f"  [ERROR] {e}")
                self.results["accounts_failed"] += 1
                self.results["log"].append({"error": str(e), "email": email})

            # Delay between accounts
            if i < count:
                delay = random.randint(delay_min, delay_max)
                print(f"\n[DONE] Waiting {delay}s before next account...")
                await asyncio.sleep(delay)

        # Final summary
        elapsed = time.time() - batch_start
        self.results["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.results["elapsed_seconds"] = round(elapsed, 1)
        self.results["elapsed_human"] = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

        print(f"\n{'#'*60}")
        print(f"#  BATCH COMPLETE")
        print(f"#  Created: {self.results['accounts_created']}/{count}")
        print(f"#  Failed: {self.results['accounts_failed']}")
        print(f"#  Tokens harvested: {self.results['tokens_harvested']}")
        print(f"#  Injected to 9Router: {self.results['tokens_injected']}")
        print(f"#  Elapsed: {self.results['elapsed_human']}")
        print(f"{'#'*60}\n")

        # Save batch report
        report_path = f"/root/github-farm/data/batch_{int(time.time())}.json"
        with open(report_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"[REPORT] {report_path}")

        return self.results

    async def inject_pending(self, platforms: List[str] = None) -> Dict[str, Any]:
        """Inject all pending (uninjected) tokens to 9Router."""
        pending = self.accounts.get_pending()
        results = {"injected": 0, "skipped": 0, "failed": 0}

        for account in pending:
            for pid, pdata in account.get("platforms", {}).items():
                if pdata.get("injected"):
                    continue
                if platforms and pid not in platforms:
                    continue

                adapter_cls = ADAPTERS.get(pid)
                if not adapter_cls:
                    results["failed"] += 1
                    continue

                adapter = adapter_cls()
                if pid == "codebuddy":
                    parsed = adapter.parse_session(pdata["token"])
                else:
                    parsed = adapter.parse_session(pdata["token"], account["email"])

                inj_result = self.injector.inject_session(parsed)
                if inj_result.get("success"):
                    self.accounts.mark_injected(account["email"], pid)
                    results["injected"] += 1
                else:
                    results["failed"] += 1

        return results
