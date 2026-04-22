#!/usr/bin/env python3
"""outreach.py - Send Aiscite outreach email from audit JSON.

Usage:
    python3 outreach.py --audit audit_<slug>.json
    python3 outreach.py --lead-id <id>

Reads audit JSON, builds personalized email, sends via gog.
"""
import argparse, json, os, sys, re, subprocess
from pathlib import Path

SENDER_ACCOUNT = "vm@aiscite.com"

def verify_sender_auth():
    """Abort if vm@aiscite.com is not authorized in gog."""
    result = subprocess.run(
        ["gog", "gmail", "list", "in:inbox", "--account", SENDER_ACCOUNT],
        capture_output=True, text=True,
        env={**os.environ, "GOG_KEYRING_PASSWORD": os.environ.get("GOG_KEYRING_PASSWORD", "optimus-gog-2026")}
    )
    if "No auth for gmail" in result.stderr or "No auth for gmail" in result.stdout:
        print(f"ABORT: No gog auth for {SENDER_ACCOUNT}.")
        print(f"Run: gog auth add {SENDER_ACCOUNT} --services gmail")
        sys.exit(2)

def slugify(name):
    """Convert business name to slug for URL."""
    return name.lower().replace(" ", "-").replace("&", "").replace("'", "").replace(".", "").replace(",", "")

from config import TRACKER_FILE as TRACKER

BIZ_TYPE_LABELS = {
    "dentist": "dental practice",
    "dental": "dental practice",
    "lawyer": "law firm",
    "legal": "law firm",
    "accountant": "accounting firm",
    "accounting": "accounting firm",
    "restaurant": "restaurant",
    "gym": "gym",
    "physio": "physiotherapy clinic",
    "physiotherapy": "physiotherapy clinic",
    "optometrist": "optometry clinic",
    "chiropractor": "chiropractic clinic",
    "pharmacy": "pharmacy",
    "vet": "veterinary clinic",
    "veterinary": "veterinary clinic",
    "mortgage": "mortgage brokerage",
    "real estate": "real estate agency",
    "salon": "hair salon",
    "spa": "spa",
    "med spa": "med spa",
}

def get_biz_type_label(biz_type):
    key = biz_type.lower().strip()
    for k, v in BIZ_TYPE_LABELS.items():
        if k in key:
            return v
    return biz_type

def get_email_domain(url):
    """Extract cleaned domain from URL (strip www., https://, etc)."""
    url = url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    # Strip www. prefix
    if url.startswith("www."):
        url = url[4:]
    return url

def load_tracker():
    if not TRACKER.exists():
        return {"last_updated": "2026-04-12T00:00:00Z", "leads": []}
    with open(TRACKER) as f:
        return json.load(f)

def find_lead_in_tracker(lead_id, tracker=None):
    """Find lead by 'id' field (not 'business_name')."""
    if tracker is None:
        tracker = load_tracker()
    for l in tracker.get("leads", []):
        if l.get("id", "").lower() == lead_id.lower():
            return l
    return None

def main():
    p = argparse.ArgumentParser(description="Aiscite outreach sender")
    p.add_argument("--audit", help="Path to audit JSON file")
    p.add_argument("--lead-id", help="Lead ID from LEADS_TRACKER.json")
    p.add_argument("--dry-run", action="store_true", help="Build email but don't send")
    args = p.parse_args()
    
    if not args.dry_run:
        verify_sender_auth()
    
    if args.audit:
        with open(args.audit) as f:
            audit = json.load(f)
        business_name = audit.get("business_name", "Unknown Business")
        domain = get_email_domain(audit.get("url", ""))
        city = audit.get("city", "unknown city")
        biz_type = audit.get("biz_type", "business")
        score = audit.get("overall_score", 0)
    elif args.lead_id:
        tracker = load_tracker()
        lead = find_lead_in_tracker(args.lead_id, tracker)
        if not lead:
            print(f"Lead {args.lead_id} not found")
            sys.exit(1)
        business_name = lead.get("name", "Unknown Business")
        domain = lead.get("domain", "")
        city = lead.get("city", lead.get("location", "unknown city"))
        biz_type = lead.get("biz_type", lead.get("vertical", lead.get("type", "business")))
        score = lead.get("overall_score", lead.get("audit_score", 0))
    else:
        p.error("Must provide --audit or --lead-id")
    
    # Build email - use slugified business_name for URL
    biz_type_label = get_biz_type_label(biz_type)
    live_url = f"https://aiscite.com/audit/{slugify(business_name)}/"
    
    body = f"""
Hi,

I put together a short AI visibility review for {business_name} - it takes about 2 minutes to read.

When someone asks an AI assistant for a {biz_type_label} in {city}, how your site is structured right now means AI either skips you or mentions you without confidence. There are one or two fixable gaps holding it back.

The full breakdown is here: {live_url}

No form, no pitch - just the analysis. If it is useful and you want to talk it through, there is a link to book a 10-minute call at the top.

Best
VM
"""
    
    print("=== Outreach Email Preview ===")
    print(f"Business: {business_name}")
    print(f"To: contact@{domain}")
    print(f"Subject: Your {biz_type_label} and AI search - a private review")
    print("Body:")
    print(body)
    if args.dry_run:
        print("=== DRY RUN - Not sending ===")
        sys.exit(0)
    
    print("=== Ready to send? ===")
    print("Run: GOG_KEYRING_PASSWORD='optimus-gog-2026' gog gmail send --account vm@aiscite.com --to 'contact@{domain}' --subject 'Your {biz_type_label} and AI search - a private review' --body 'HI'")

if __name__ == "__main__":
    main()
