"""
Email Aliasing Engine
Implements RFC-5322 compliant Gmail Dot-Trick and ProtonMail Plus-Addressing algorithms.
Author: D4NNBOZ
License: MIT
"""

from typing import List

def generate_dot_trick_emails(username: str, domain: str = "gmail.com", max_count: int = 50) -> List[str]:
    """Generates unique dot-trick email variations for Gmail addresses."""
    cleaned_user = username.replace(".", "").strip().lower()
    if not cleaned_user:
        return []
    
    def generate_dots(s: str) -> List[str]:
        if len(s) <= 1:
            return [s]
        sub = generate_dots(s[1:])
        res = []
        for v in sub:
            res.append(s[0] + v)
            res.append(s[0] + "." + v)
        return res

    all_variations = generate_dots(cleaned_user)
    unique_list = []
    for v in all_variations:
        # Require at least one dot in alias so it doesn't collide with the owner's primary GitHub account
        if "." not in v:
            continue
        full_email = f"{v}@{domain}"
        if full_email not in unique_list:
            unique_list.append(full_email)
        if len(unique_list) >= max_count:
            break
            
    return unique_list

def generate_plus_address_emails(username: str, domain: str = "proton.me", prefix: str = "gh", count: int = 20) -> List[str]:
    """Generates plus-addressing email variations for ProtonMail / Outlook addresses."""
    cleaned_user = username.strip().lower()
    if not cleaned_user:
        return []
        
    return [f"{cleaned_user}+{prefix}{i:02d}@{domain}" for i in range(1, count + 1)]
