"""
CLI Entrypoint for GitHub OAuth Harvester Suite
Author: D4NNBOZ
License: MIT
"""
import argparse
import asyncio
import sys
import os
import json
import tomllib

from src.generator.email_engine import generate_dot_trick_emails, generate_plus_address_emails
from src.imap.otp_listener import ImapOtpListener
from src.adapters.adapters import CodeBuddyAdapter, GoRouterAdapter, TabiAIAdapter
from src.injector.db_injector import DatabaseInjector


def load_config(config_path: str = None) -> dict:
    """Load config from TOML file."""
    path = config_path or os.path.join(os.path.dirname(__file__), "config", "config.toml")
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="GitHub OAuth Multi-Platform Harvesting Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate email aliases
  python3 main.py generate --user john --domain gmail.com --type dot --count 20

  # Listen for OTP
  python3 main.py listen-otp --user john@gmail.com --password xxxx-xxxx-xxxx-xxxx

  # Inject single token
  python3 main.py inject --platform codebuddy --token "eyJ..."

  # === FULL AUTOMATION ===
  # Farm 5 accounts (GitHub signup → OTP → harvest → inject)
  python3 main.py farm --base-user john --domain gmail.com --count 5

  # Farm with custom delay + specific platforms
  python3 main.py farm --base-user john --domain gmail.com --count 10 \\
      --platforms codebuddy gorouter --delay-min 60 --delay-max 120

  # Farm single account
  python3 main.py farm --email john.d.oth@gmail.com --username ghuser123

  # Inject all pending tokens
  python3 main.py inject-all

  # View account status
  python3 main.py accounts --status
  python3 main.py accounts --json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: generate
    p_gen = subparsers.add_parser("generate", help="Generate Dot-Trick or Plus-Addressing email aliases")
    p_gen.add_argument("--user", required=True, help="Base username")
    p_gen.add_argument("--domain", default="gmail.com", help="Email domain")
    p_gen.add_argument("--type", choices=["dot", "plus"], default="dot", help="Aliasing algorithm")
    p_gen.add_argument("--count", type=int, default=20, help="Number of variations")
    p_gen.add_argument("--json", action="store_true", help="Output JSON")

    # Command: listen-otp
    p_otp = subparsers.add_parser("listen-otp", help="Real-time IMAP listener for GitHub OTP")
    p_otp.add_argument("--user", required=True, help="Master IMAP email")
    p_otp.add_argument("--password", required=True, help="16-digit Google App Password")
    p_otp.add_argument("--server", default="imap.gmail.com", help="IMAP server")
    p_otp.add_argument("--target", help="Specific alias filter")
    p_otp.add_argument("--timeout", type=int, default=60, help="Timeout seconds")
    p_otp.add_argument("--json", action="store_true", help="Output JSON")

    # Command: inject
    p_inj = subparsers.add_parser("inject", help="Inject single token to 9Router")
    p_inj.add_argument("--platform", choices=["codebuddy", "gorouter", "tabiai"], required=True)
    p_inj.add_argument("--token", required=True, help="Raw JWT / Access Token")
    p_inj.add_argument("--email", default="user@oauth", help="Account email")
    p_inj.add_argument("--json", action="store_true")

    # Command: farm (FULL AUTOMATION)
    p_farm = subparsers.add_parser("farm", help="Full automation: signup → OTP → harvest → inject")
    p_farm.add_argument("--email", help="Specific email (single account mode)")
    p_farm.add_argument("--username", help="Specific username (single account mode)")
    p_farm.add_argument("--password", help="Specific password (auto-generated if omitted)")
    p_farm.add_argument("--base-user", help="Base username for dot/plus generation")
    p_farm.add_argument("--domain", default="gmail.com", help="Email domain")
    p_farm.add_argument("--type", choices=["dot", "plus"], default="dot", help="Email aliasing type")
    p_farm.add_argument("--count", type=int, default=5, help="Number of accounts to farm")
    p_farm.add_argument("--platforms", nargs="+", default=None,
                        choices=["codebuddy", "gorouter", "tabiai"],
                        help="Target platforms (default: all)")
    p_farm.add_argument("--no-inject", action="store_true", help="Skip 9Router injection")
    p_farm.add_argument("--delay-min", type=int, default=30, help="Min delay between accounts (s)")
    p_farm.add_argument("--delay-max", type=int, default=90, help="Max delay between accounts (s)")
    p_farm.add_argument("--otp-timeout", type=int, default=120, help="OTP wait timeout (s)")
    p_farm.add_argument("--proxy", help="Proxy URL (socks5://host:port)")
    p_farm.add_argument("--headless", action="store_true", default=True, help="Headless browser (default: True)")
    p_farm.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window")
    p_farm.add_argument("--config", help="Config file path")
    p_farm.add_argument("--json", action="store_true", help="Output JSON")

    # Command: inject-all
    p_ia = subparsers.add_parser("inject-all", help="Inject all pending tokens to 9Router")
    p_ia.add_argument("--platforms", nargs="+", default=None,
                       choices=["codebuddy", "gorouter", "tabiai"])
    p_ia.add_argument("--json", action="store_true")

    # Command: accounts
    p_acc = subparsers.add_parser("accounts", help="View harvested account status")
    p_acc.add_argument("--status", action="store_true", help="Show status summary")
    p_acc.add_argument("--json", action="store_true", help="Output JSON")
    p_acc.add_argument("--data-dir", help="Data directory path")

    args = parser.parse_args()

    # ── generate ──
    if args.command == "generate":
        if args.type == "dot":
            emails = generate_dot_trick_emails(args.user, args.domain, args.count)
        else:
            emails = generate_plus_address_emails(args.user, args.domain, "gh", args.count)

        if args.json:
            print(json.dumps({"status": "ok", "count": len(emails), "emails": emails}, indent=2))
        else:
            print(f"\n[+] Generated {len(emails)} {args.type.upper()} email variations for '{args.user}@{args.domain}':\n")
            for idx, em in enumerate(emails, 1):
                print(f" {idx:2d}. {em}")

    # ── listen-otp ──
    elif args.command == "listen-otp":
        listener = ImapOtpListener(args.server, args.user, args.password)
        code = listener.listen_github_otp(target_email=args.target, timeout_sec=args.timeout)
        if args.json:
            print(json.dumps({"status": "ok" if code else "timeout", "otp_code": code}, indent=2))
        else:
            if code:
                print(f"\n[SUCCESS] GitHub OTP Code: {code}")
            else:
                print(f"\n[!] Timeout. No OTP detected.")

    # ── inject ──
    elif args.command == "inject":
        if args.platform == "codebuddy":
            adapter = CodeBuddyAdapter()
            parsed = adapter.parse_session(args.token)
        elif args.platform == "gorouter":
            adapter = GoRouterAdapter()
            parsed = adapter.parse_session(args.token, args.email)
        elif args.platform == "tabiai":
            adapter = TabiAIAdapter()
            parsed = adapter.parse_session(args.token, args.email)

        injector = DatabaseInjector()
        res = injector.inject_session(parsed)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("success"):
                print(f"\n[SUCCESS] Injected {res.get('provider')} → {res.get('name')} ({res.get('email')}) [{res.get('status').upper()}]")
            else:
                print(f"\n[ERROR] {res.get('error')}")

    # ── farm (FULL AUTOMATION) ──
    elif args.command == "farm":
        config = load_config(args.config)
        config["headless"] = args.headless
        config["otp_timeout"] = args.otp_timeout
        if args.proxy:
            config["proxy"] = args.proxy

        from src.automation.orchestrator import Orchestrator
        orch = Orchestrator(config)

        if args.email:
            # Single account mode
            result = asyncio.run(orch.run_single(
                email=args.email,
                username=args.username,
                password=args.password,
                platforms=args.platforms,
                inject=not args.no_inject,
            ))
        else:
            # Batch mode
            base_user = args.base_user or config.get("generator", {}).get("base_username", "enricko.putra")
            domain = args.domain or config.get("generator", {}).get("domain", "gmail.com")
            email_type = args.type or config.get("generator", {}).get("type", "dot")

            result = asyncio.run(orch.run_batch(
                count=args.count,
                base_email=base_user,
                domain=domain,
                email_type=email_type,
                platforms=args.platforms,
                inject=not args.no_inject,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
            ))

        if args.json:
            print(json.dumps(result, indent=2))

    # ── inject-all ──
    elif args.command == "inject-all":
        from src.automation.orchestrator import Orchestrator
        config = load_config()
        orch = Orchestrator(config)
        result = asyncio.run(orch.inject_pending(platforms=args.platforms))

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n[INJECT-ALL] Injected: {result['injected']}, Failed: {result['failed']}")

    # ── accounts ──
    elif args.command == "accounts":
        from src.automation.account_manager import AccountManager
        am = AccountManager(args.data_dir)

        if args.json:
            print(json.dumps(am.list_all(), indent=2))
        elif args.status:
            print(f"\n[ACCOUNTS] Total: {am.count()}, Harvested: {am.count_harvested()}")
            print(f"  Pending injection: {len(am.get_pending())}")
        else:
            for acc in am.list_all():
                status = "✓" if acc.get("github_status") == "created" else "✗"
                platforms = ", ".join(acc.get("platforms", {}).keys()) or "none"
                print(f"  {status} {acc['email']} ({acc['username']}) → {platforms}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
