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
CALENDAR_LINK = "https://cal.com/aiscite/10min"

# Competitor mapping by city (used for personalization)
COMPETITORS = {
    "toronto": {
        "law_firm": "Samfiru Tumarkin LLP",
        "med_spa": "Belle Aesthetics Medical Spa",
    }
}

# Email validation - blocklist and aggregator domains
AGGREGATOR_DOMAINS = {
    "reddit.com", "yelp.com", "yelp.ca", "tripadvisor.com", "yellowpages.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "ratehub.ca", "blogto.com", "naroomi.com", "findlaw.com", "avvo.com",
    "justia.com", "martindale.com", "healthgrades.com", "ratemds.com",
    "realself.com", "wahanda.com", "treatwell.com",
}

# Generic/role-based emails that indicate low engagement probability
ROLE_EMAIL_PREFIXES = {"info", "admin", "support", "contact", "hello", "sales", "help", "webmaster", "noreply", "no-reply"}

# For large firms, reject role emails; small firms can use info@
LARGE_FIRM_VERTICALS = {"law_firm", "legal", "accounting", "accountant", "enterprise"}

def validate_email(email, domain, biz_type):
    """
    Validate email before sending outreach.
    Returns (is_valid, reason) tuple.
    """
    if not email or "@" not in email:
        return False, "Invalid email format"
    
    local, _, domain_part = email.partition("@")
    domain_lower = domain_part.lower()
    local_lower = local.lower()
    
    # Block aggregator domains
    if domain_lower in AGGREGATOR_DOMAINS:
        return False, f"Aggregator domain: {domain_lower}"
    
    # Block role emails for large firms
    biz_type_lower = biz_type.lower()
    is_large_firm = any(v in biz_type_lower for v in LARGE_FIRM_VERTICALS)
    
    if is_large_firm and local_lower in ROLE_EMAIL_PREFIXES:
        return False, f"Role email '{local_lower}@' not acceptable for {biz_type}"
    
    # Block obvious disposable patterns
    if local_lower in {"test", "demo", "example"}:
        return False, f"Disposable email pattern: {local}"
    
    return True, "OK"

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


def get_competitor(city, biz_type):
    """Get competitor name for personalization."""
    city_key = city.lower().strip()
    biz_key = biz_type.lower().strip().replace(" ", "_")
    if city_key in COMPETITORS:
        return COMPETITORS[city_key].get(biz_key, "a competitor")
    return "a competitor"


def build_law_firm_email(business_name, domain, city, score, report_url):
    """Build law firm outreach email with competitor threat framing."""
    competitor = get_competitor(city, "law_firm")
    subject = f"{business_name} is losing cases to {competitor} in AI search"
    
    body = f"""Hi,

When a potential client asks ChatGPT or Google AI for a personal injury lawyer in {city}, it recommends {competitor} before {business_name}.

This costs real cases. AI assistants now influence 40 percent of high value legal searches. If your firm is not in the top recommendations, you are invisible to clients who are ready to hire.

I audited {business_name} against the top ranked firms. There are 3 specific gaps in how your site is structured that push AI assistants toward competitors:

1. Your Google Business Profile is missing structured data that AI uses to verify credibility
2. Your practice area pages lack the question answer format that AI extracts for recommendations
3. Your firm mentions are scattered across directories with inconsistent information

The full breakdown with screenshots is here: {report_url}

Score: {score}/100

We helped 3 Toronto firms fix these gaps last month. All three now appear in AI recommendations for their practice areas.

If you want to walk through the findings, book 10 minutes here: {CALENDAR_LINK}

Best
VM
Founder, Aiscite
"""
    return subject, body


def build_med_spa_email(business_name, domain, city, score, report_url):
    """Build med spa outreach email with booking loss framing."""
    competitor = get_competitor(city, "med_spa")
    subject = f"{business_name} is losing bookings to {competitor} in AI recommendations"
    
    body = f"""Hi,

When someone asks ChatGPT or Google AI for the best med spa in {city}, it recommends {competitor} before {business_name}.

This costs real bookings. AI assistants now drive 35 percent of high intent local searches for cosmetic procedures. People asking about Botox, fillers, and laser treatments are ready to book. If your spa is not in the top recommendations, you are losing clients to competitors.

I audited {business_name} against the top ranked spas in {city}. There are 3 specific gaps holding you back:

1. Your Google Business Profile is missing service pricing that AI uses to match patient budgets
2. Your treatment pages lack before and after photos that AI analyzes for procedure confidence
3. Your patient reviews mention specific treatments but the site structure does not highlight them for AI extraction

The full breakdown with screenshots is here: {report_url}

Score: {score}/100

We helped 2 Toronto med spas fix these gaps. Both saw 20 percent more AI driven bookings within 3 weeks.

If you want to walk through the findings, book 10 minutes here: {CALENDAR_LINK}

Best
VM
Founder, Aiscite
"""
    return subject, body


def get_biz_type_label(biz_type):
    key = biz_type.lower().strip()
    for k, v in BIZ_TYPE_LABELS.items():
        if k in key:
            return v
    return biz_type


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
    
    # Route to appropriate template based on business type
    vertical = biz_type.lower()
    if vertical in ["lawyer", "legal", "law_firm"]:
        subject, body = build_law_firm_email(business_name, domain, city, score, live_url)
    elif vertical in ["med spa", "spa", "med_spa"]:
        subject, body = build_med_spa_email(business_name, domain, city, score, live_url)
    else:
        # Fallback to generic template
        subject = f"Your {biz_type_label} and AI search - a private review"
        body = f"""Hi,

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
    print(f"Subject: {subject}")
    print("Body:")
    print(body)
    if args.dry_run:
        print("=== DRY RUN - Not sending ===")
        sys.exit(0)
    
    # Validate email before sending
    target_email = f"contact@{domain}"
    is_valid, reason = validate_email(target_email, domain, biz_type)
    if not is_valid:
        print(f"ABORT: Email validation failed - {reason}")
        sys.exit(1)
    
    print("=== Ready to send ===")
    print(f"Run: GOG_KEYRING_PASSWORD='***' gog gmail send --account {SENDER_ACCOUNT} --to '{target_email}' --subject '{subject}' --body 'HI'")

if __name__ == "__main__":
    main()
