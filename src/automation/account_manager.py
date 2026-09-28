"""
Account Manager — persistent state tracking for harvested accounts.
Stores email→platform→token mappings, deduplication, and harvest history.
"""
import json
import os
import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path


class AccountManager:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data"
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self.accounts_file = os.path.join(self.data_dir, "accounts.json")
        self._accounts = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.accounts_file):
            with open(self.accounts_file, "r") as f:
                return json.load(f)
        return {"accounts": [], "stats": {"total": 0, "injected": 0, "failed": 0}}

    def _save(self):
        with open(self.accounts_file, "w") as f:
            json.dump(self._accounts, f, indent=2)

    def exists(self, email: str) -> bool:
        return any(a["email"] == email for a in self._accounts["accounts"])

    def add(self, email: str, username: str, password: str, platform: str = "github",
            status: str = "created", token: str = None, extra: Dict = None) -> Dict:
        if self.exists(email):
            return {"success": False, "error": "duplicate"}

        entry = {
            "email": email,
            "username": username,
            "password": password,
            "github_status": status,
            "platforms": {},
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if extra:
            entry.update(extra)

        if token:
            entry["platforms"][platform] = {
                "token": token,
                "harvested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

        self._accounts["accounts"].append(entry)
        self._accounts["stats"]["total"] += 1
        self._save()
        return {"success": True, "email": email}

    def update_github_status(self, email: str, status: str):
        for a in self._accounts["accounts"]:
            if a["email"] == email:
                a["github_status"] = status
                self._save()
                return True
        return False

    def add_platform_token(self, email: str, platform: str, token: str, extra: Dict = None):
        for a in self._accounts["accounts"]:
            if a["email"] == email:
                a["platforms"][platform] = {
                    "token": token,
                    "harvested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                if extra:
                    a["platforms"][platform].update(extra)
                self._save()
                return True
        return False

    def mark_injected(self, email: str, platform: str):
        for a in self._accounts["accounts"]:
            if a["email"] == email:
                if platform in a["platforms"]:
                    a["platforms"][platform]["injected"] = True
                self._accounts["stats"]["injected"] += 1
                self._save()
                return True
        return False

    def mark_failed(self, email: str, reason: str):
        for a in self._accounts["accounts"]:
            if a["email"] == email:
                a["github_status"] = "failed"
                a["fail_reason"] = reason
                self._accounts["stats"]["failed"] += 1
                self._save()
                return True
        return False

    def get_pending(self, platform: str = None) -> List[Dict]:
        """Get accounts that have tokens but haven't been injected yet."""
        result = []
        for a in self._accounts["accounts"]:
            if platform:
                if platform in a["platforms"] and not a["platforms"][platform].get("injected"):
                    result.append(a)
            else:
                for pname, pdata in a.get("platforms", {}).items():
                    if not pdata.get("injected"):
                        result.append(a)
                        break
        return result

    def get_stats(self) -> Dict:
        return self._accounts["stats"]

    def all_emails(self) -> List[str]:
        return [a["email"] for a in self._accounts["accounts"]]

    def list_all(self) -> List[Dict]:
        """Return all accounts."""
        return self._accounts["accounts"]

    def count(self) -> int:
        """Total accounts."""
        return len(self._accounts["accounts"])

    def count_harvested(self) -> int:
        """Accounts with at least one platform token."""
        return sum(1 for a in self._accounts["accounts"] if a.get("platforms"))
