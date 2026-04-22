#!/usr/bin/env python3
"""
Reply Monitor for Aiscite - Automated response workflow.
Monitors vm@aiscite.com and vaibhavmehta@strutinfra.com for replies,
updates LEADS_TRACKER.json, drafts appropriate responses, and flags Board.
"""
import json, os, sys, re, subprocess
from datetime import datetime, timedelta
from pathlib import Path

from config import TRACKER_FILE, PROJECT_ROOT

LEADS_TRACKER = str(TRACKER_FILE)
APPROVAL_QUEUE = PROJECT_ROOT / "APPROVAL_QUEUE.md"
OUTREACH_LOG = PROJECT_ROOT / "OUTREACH_LOG.md"
SENT_EMAILS = PROJECT_ROOT / "sent_emails"
REPLY_LOG = PROJECT_ROOT / "reply_monitor_log.txt"
EMAILS_SENT_LOG = PROJECT_ROOT / "emails_sent.log"

from_email = "vm@aiscite.com"
copper_email = "vaibhavmehta@strutinfra.com"
GOG_KEYRING_PASSWORD=os.environ.get("GOG_KEYRING_PASSWORD", "optimus-gog-2026")


def gog_search(account, query, days=2):
    """Run gog gmail search and return email metadata."""
    cmd = f"gog gmail search '{query}' --account {account}".split()
    env = dict(os.environ, GOG_KEYRING_PASSWORD=GOG_KEYRING_PASSWORD)
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return parse_search_output(r.stdout)
        return []
    except Exception as e:
        print(f"  gog_search ERROR {account} '{query}': {e}")
        return []


def parse_search_output(raw):
    """Parse gog search output into list of email objects."""
    emails = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            emails.append({
                "id": parts[0].strip("[]"),
                "from": None,
                "subject": " ".join(parts[1:]),
                "date": datetime.now().isoformat()
            })
    return emails


def load_leads():
    """Load LEADS_TRACKER.json."""
    try:
        with open(LEADS_TRACKER) as f:
            data = json.load(f)
            return data.get("leads", [])
    except:
        return []


def save_leads(leads):
    """Save LEADS_TRACKER.json."""
    with open(LEADS_TRACKER, "w") as f:
        json.dump(leads, f, indent=2)


def load_sent_emails():
    """Load emails_sent.log to find message IDs."""
    sent = {}
    try:
        with open(EMAILS_SENT_LOG) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    msgid = parts[0].strip("<>")
                    email = parts[1]
                    subject = parts[2]
                    sent[email] = {"msgid": msgid, "subject": subject}
    except:
        pass
    return sent


def classify_reply(email):
    """Classify reply into type and urgency."""
    from_addr = (email.get("from") or "").lower()
    subject = (email.get("subject") or "").lower()
    body = subject
    types = {
        "interested": ["interesting", "how", "tell me more", "cost", "prices", "pricing"],
        "booked": ["calendly", "confirmed", "booked"],
        "not_interested": ["no thanks", "unsubs", "remove", "not interested"],
        "bounced": ["mailer-daemon", "delivery", "failed", "undelivered", "recipient"],
        "copper_interested": ["scrap", "scrap metal", "quantity", "volume", "copper"],
        "copper_more_info": ["what grade", "spec", "fca", "cif", "terms"],
        "copper_not": ["no", "don't sell", "external", "not selling"]
    }
    category = "unknown"
    urgency = "low"
    if any(t in body for t in types["interested"]):
        category = "aiscite_interested"
        urgency = "high"
    elif any(t in body for t in types["booked"]):
        category = "booked_call"
        urgency = "critical"
    elif any(t in body for t in types["not_interested"]):
        category = "not_interested"
        urgency = "low"
    elif any(t in body for t in types["bounced"]):
        category = "bounce"
        urgency = "medium"
    elif any(t in body for t in types["copper_interested"]):
        category = "copper_interested"
        urgency = "high"
    elif any(t in body for t in types["copper_more_info"]):
        category = "copper_more_info"
        urgency = "medium"
    elif any(t in body for t in types["copper_not"]):
        category = "copper_not"
        urgency = "low"
    elif "copper" in body or "scrap" in body:
        category = "copper_unknown"
        urgency = "low"
    elif "aiscite" in body or "ai visibility" in body:
        category = "aiscite_unknown"
        urgency = "low"
    return category, urgency


def draft_reply(category, email, lead):
    """Draft response based on category."""
    names = [lead.get("name", lead.get("domain", "there").replace(".", " "))]
    name = names[0].split()[0] if names else "there"
    biz_type = lead.get("biz_type", "your business")
    city = lead.get("city", "your location")
    
    if category == "aiscite_interested":
        return f"""
Hi {name},

Great to hear from you. The report gives you the full picture — the short version is that
{lead.get('name', 'your business')} has strong fundamentals but one or two structural gaps that are making it
harder for AI to confidently recommend you over competitors.

The 10-minute walkthrough is the fastest way to see whether it is worth fixing.
You can book here: https://calendly.com/vaibhavmeh/aiscite-introduction

Best
VM
"""
    elif category == "copper_interested":
        return f"""
Dear {name},

Thank you for getting back to me.

We are looking for consistent monthly volumes of Millberry Grade 1 (99.9% purity)
on CIF terms — typically 20MT per shipment. Payment is by LC or TT depending on
the relationship.

Would a brief call work to discuss whether the volumes and terms align? I am
available most days this week.

Best regards
VM
vaibhavmehta@strutinfra.com
"""
    elif category == "copper_more_info":
        return f"""
Dear {name},

Thank you for the details. We require:
- Millberry Grade 1 (99.9% purity)
- CIF terms (we handle logistics to Toronto port)
- Consistent monthly volumes (20MT+)
- Payment: LC for new partners, TT for trusted
- 2-3 month payment terms possible after 3 consecutive on-time payments

Please confirm if this aligns with your offering.

Best regards
VM
vaibhavmehta@strutinfra.com
"""
    elif category in ["bounced", "not_interested"]:
        return None  # No reply needed
    else:
        return f"""
Hi {name},

Thank you for your response. I've noted your feedback.

Best
VM
"""


def log_reply(reply, category, lead):
    """Append reply to reply_monitor_log.txt and APPROVAL_QUEUE.md."""
    timestamp = datetime.now().isoformat()
    lead_id = lead.get("id", "unknown")
    report_url = lead.get("report_url", "")
    log_entry = f"""
{timestamp} [{category}] Lead {lead_id} ({report_url})
Reply:
{reply}
"""
    try:
        with open(REPLY_LOG, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"  Cannot write to REPLY_LOG: {e}")
    try:
        with open(APPROVAL_QUEUE, "a") as f:
            f.write(f"""
## {timestamp} - Reply {category}
- Lead: {lead_id}
- Report: {report_url}
- Category: {category}
- Response:
```
{reply}
```
""")
    except Exception as e:
        print(f"  Cannot write to APPROVAL_QUEUE: {e}")


def update_lead_status(lead, new_status, note=""):
    """Update LEADS_TRACKER.json with new status."""
    leads = load_leads()
    found = False
    for l in leads:
        if l.get("id") == lead.get("id") or (l.get("domain") == lead.get("domain") and l.get("city") == lead.get("city")):
            l["last_status"] = l.get("status", "unknown")
            l["status"] = new_status
            l["note"] = note
            l["last_update"] = datetime.now().isoformat()
            found = True
            break
    if not found:
        lead["status"] = new_status
        lead["note"] = note
        lead["last_update"] = datetime.now().isoformat()
        leads.append(lead)
    save_leads(leads)
    return found


def process_inbox(account, leads):
    """Process one inbox for new replies."""
    print(f"  Checking {account}...")
    emails = gog_search(account, "in:inbox newer_than:1d", 1)
    if not emails:
        print(f"    No new emails found.")
        return 0
    processed = 0
    for email in emails:
        category, urgency = classify_reply(email)
        lead = None
        email_from = (email.get("from") or "").lower()
        if email_from and not email_from.endswith("@aiscite.com"):
            lead = find_lead_by_email(email_from)
        if not lead:
            subject = (email.get("subject") or "").lower()
            for l in leads:
                if l.get("domain", "").lower() in subject or l.get("name", "").lower() in subject:
                    lead = l
                    break
        if lead:
            reply = draft_reply(category, email, lead)
            log_reply(reply or f"Status updated to {category}", category, lead)
            if reply:
                send_reply(email, reply)
            if category == "booked_call":
                update_lead_status(lead, "booked", "call booked via Calendly")
            elif category == "copper_interested":
                update_lead_status(lead, "replied", "copper interested - follow up needed")
            elif category == "aiscite_interested":
                update_lead_status(lead, "replied", "aiscite interested - follow up needed")
            elif category == "not_interested":
                update_lead_status(lead, "declined", "not interested")
            elif category == "bounce":
                update_lead_status(lead, "bounce", "email bounced - needs new address")
            processed += 1
            print(f"    Processed: {email.get('subject', 'unknown')} -> {category} ({urgency})")
        else:
            print(f"    No lead match for: {email.get('subject', 'unknown')}")
    return processed


def find_lead_by_email(email_addr):
    """Find lead in LEADS_TRACKER by email address."""
    leads = load_leads()
    for lead in leads:
        if isinstance(lead, dict):
            lead_email = (lead.get("email") or lead.get("lead_email") or "").lower()
            if lead_email == email_addr.lower():
                return lead
    return None


def send_reply(email, reply):
    """Draft reply by email (not sent automatically - Board approval queue for now)."""
    subject = email.get("subject", "")
    to_addr = email.get("from", "")
    account = copper_email if "scrap" in subject.lower() or "metal" in subject.lower() else from_email
    print(f"    [DRAFT] to {to_addr} from {account}")
    safe_subject = re.sub(r"[^a-z0-9]+", "_", subject.lower())[:50]
    draft_path = f"/home/nikunj19/optimus/domains/aiscite/drafts/{safe_subject}.eml"
    os.makedirs(os.path.dirname(draft_path), exist_ok=True)
    with open(draft_path, "w") as f:
        f.write(f"From: {from_email}\n")
        f.write(f"To: {to_addr}\n")
        f.write(f"Subject: {subject}\n\n")
        f.write(reply)
    try:
        with open(APPROVAL_QUEUE, "a") as f:
            f.write(f"""
## DRAFT REPLY - {to_addr}
- Subject: {subject}
- Reply:
```
{reply}
```
""")
    except Exception:
        pass


def main():
    if not GOG_KEYRING_PASSWORD:
        print("ERROR: GOG_KEYRING_PASSWORD not set")
        sys.exit(1)
    print(f"[ Reply Monitor ] {datetime.now().isoformat()}")
    leads = load_leads()
    if not leads:
        print("  LEADS_TRACKER.json is empty. Exiting.")
        sys.exit(0)
    processed = 0
    processed += process_inbox(from_email, leads)
    processed += process_inbox(copper_email, leads)
    print(f"  Total replies processed: {processed}")
    print("[ Done ]")


if __name__ == "__main__":
    main()
