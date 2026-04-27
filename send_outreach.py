#!/usr/bin/env python3
"""Email outreach script for Aiscite med spa wave."""
import os
import subprocess
import json
import time
import re
from pathlib import Path

PROJECT_ROOT = Path("/home/nikunj19/Projects/aiscite")

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
GOG_KEYRING_PASSWORD = os.environ.get("GOG_KEYRING_PASSWORD", "optimus-gog-2026")

# Email validation - blocklist and aggregator domains
AGGREGATOR_DOMAINS = {
    "reddit.com", "yelp.com", "yelp.ca", "tripadvisor.com", "yellowpages.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "ratehub.ca", "blogto.com", "naroomi.com", "findlaw.com", "avvo.com",
    "justia.com", "martindale.com", "healthgrades.com", "ratemds.com",
    "realself.com", "wahanda.com", "treatwell.com",
}

ROLE_EMAIL_PREFIXES = {"info", "admin", "support", "contact", "hello", "sales", "help", "webmaster", "noreply", "no-reply"}
LARGE_FIRM_VERTICALS = {"law_firm", "legal", "accounting", "accountant", "enterprise"}

def validate_email(email, domain, biz_type):
    if not email or "@" not in email:
        return False, "Invalid email format"
    local, _, domain_part = email.partition("@")
    domain_lower = domain_part.lower()
    local_lower = local.lower()
    if domain_lower in AGGREGATOR_DOMAINS:
        return False, f"Aggregator domain: {domain_lower}"
    biz_type_lower = biz_type.lower()
    is_large_firm = any(v in biz_type_lower for v in LARGE_FIRM_VERTICALS)
    if is_large_firm and local_lower in ROLE_EMAIL_PREFIXES:
        return False, f"Role email '{local_lower}@' not acceptable for {biz_type}"
    if local_lower in {"test", "demo", "example"}:
        return False, f"Disposable email pattern: {local}"
    return True, "OK"

def search_brave(query):
    """Search with Brave API, return results."""
    try:
        import requests
        r = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": 5},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return data.get('web', {}).get('results', [])
    except Exception as e:
        print(f"  Brave error: {e}")
        return []

def find_email(lead):
    """Find contact email for a lead."""
    name = lead['name']
    domain = lead['domain']
    queries = [
        f'"{name}" site:{domain} contact email',
        f'"{name}" site:{domain} "contact us"',
        f'site:{domain} "contact" email',
    ]
    for q in queries:
        results = search_brave(q)
        if results:
            snippet = results[0].get('snippet', '')
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
            if emails:
                return emails[0]
    return None

def send_email(to, subject, body):
    """Send email via GOG CLI."""
    cmd = [
        "gog", "gmail", "send",
        "--account", "vm@aiscite.com",
        "--to", to,
        "--subject", subject,
        "--body", body
    ]
    print(f"  Sending to {to}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        print(f"  SUCCESS")
        return True
    else:
        print(f"  FAILED: {result.stderr.strip()[:100] if result.stderr else result.stdout.strip()[:100]}")
        return False

def main():
    print("=== Aiscite Outreach Wave ===")
    
    from config import TRACKER_FILE
    leads_file = TRACKER_FILE
    if os.path.exists(leads_file):
        with open(leads_file) as f:
            tracker = json.load(f)
        leads = [l for l in tracker.get('leads', []) if l.get('current_stage') == 'outreach_ready']
    else:
        leads = []
    
    if not leads:
        print("No leads found. Add to LEADS_TRACKER.json first.")
        return
    
    print(f"Found {len(leads)} leads ready for outreach")
    
    for lead in leads:
        name = lead['name']
        slug = lead['slug']
        domain = lead['domain']
        city = lead.get('city', 'Toronto')
        biz_type = lead.get('biz_type', 'med spa')
        report_url = f"https://aiscite.com/audit/{slug}/"
        print(f"[{name}]")
        
        email = find_email(lead)
        if not email:
            print(f"  No email found, logging for manual research")
            continue
        
        # Validate email before sending
        is_valid, reason = validate_email(email, domain, biz_type)
        if not is_valid:
            print(f"  SKIPPED: Email validation failed - {reason}")
            continue
        
        body = f"""
Hi,

I put together a short AI visibility review for {name} - it takes about 2 minutes to read.

When someone asks an AI assistant for a {biz_type} in {city}, how your site is structured right now means AI either skips you or mentions you without confidence. There are one or two fixable gaps holding it back.

The full breakdown is here: {report_url}

No form, no pitch - just the analysis. If it is useful and you want to talk it through, there is a link to book a 10-minute call at the top.

Best
VM
"""
        success = send_email(email, f"Your {biz_type} and AI search - a private review", body)
        
        log_file = PROJECT_ROOT / "OUTREACH_LOG.md"
        with open(log_file, "a") as f:
            f.write(f"| {lead['id']} | {name} | {email} | {report_url} | N/A | {'sent' if success else 'failed'} |\n")
        
        time.sleep(3)
        print()

if __name__ == "__main__":
    main()
