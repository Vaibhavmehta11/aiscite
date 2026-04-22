#!/usr/bin/env python3
"""
Wheeljack: Cancel recursive postmortem tasks.

This script cancels the 21 known recursive postmortem tasks:
AUT-130, AUT-131, AUT-133-158, AUT-161-162, AUT-166-169, AUT-171, AUT-173-175

Usage:
  python3 scripts/cancel_recursive_postmortems.py --dry-run
  python3 scripts/cancel_recursive_postmortems.py --confirm

Requirements:
  - PAPERCLIP_API_URL, PAPERCLIP_API_KEY, PAPERCLIP_AGENT_ID, PAPERCLIP_COMPANY_ID
"""

import os
import sys
import json
from typing import List, Dict
from pathlib import Path

AISCITE_ROOT = Path("/home/nikunj19/Projects/aiscite")
PAPERCLIP_API_URL = os.environ.get("PAPERCLIP_API_URL", "http://127.0.0.1:3100")
PAPERCLIP_API_KEY = os.environ.get("PAPERCLIP_API_KEY", "")
PAPERCLIP_AGENT_ID = os.environ.get("PAPERCLIP_AGENT_ID", "26825051-97c8-4cfb-882d-9749252619c4")
PAPERCLIP_COMPANY_ID = os.environ.get("PAPERCLIP_COMPANY_ID", "891ba9d1-4a11-4d90-87aa-afba1d7f00db")

def paperclip_get(endpoint: str) -> Dict:
    import urllib.request
    url = f"{PAPERCLIP_API_URL}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {PAPERCLIP_API_KEY}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def paperclip_patch(issue_id: str, data: Dict) -> Dict:
    import urllib.request
    url = f"{PAPERCLIP_API_URL}/api/issues/{issue_id}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="PATCH")
    req.add_header("Authorization", f"Bearer {PAPERCLIP_API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def get_all_issues() -> List[Dict]:
    return paperclip_get(f"/api/companies/{PAPERCLIP_COMPANY_ID}/issues")

def get_target_issues(issues: List[Dict]) -> List[Dict]:
    # IDs to cancel: AUT-130, AUT-131, AUT-133-158, AUT-161-162, AUT-166-169, AUT-171, AUT-173-175
    target_ids = {
        "AUT-130", "AUT-131",
        "AUT-133", "AUT-134", "AUT-135", "AUT-136", "AUT-137", "AUT-138", "AUT-139",
        "AUT-140", "AUT-141", "AUT-142", "AUT-143", "AUT-144", "AUT-145", "AUT-146",
        "AUT-147", "AUT-148", "AUT-149", "AUT-150", "AUT-151", "AUT-152", "AUT-153",
        "AUT-154", "AUT-155", "AUT-156", "AUT-157", "AUT-158",
        "AUT-161", "AUT-162",
        "AUT-166", "AUT-167", "AUT-168", "AUT-169",
        "AUT-171",
        "AUT-173", "AUT-174", "AUT-175",
    }
    return [i for i in issues if i.get("identifier") in target_ids and i.get("status") != "cancelled"]

def cancel_issue(issue: Dict, dry_run: bool = True) -> bool:
    identifier = issue.get("identifier", "UNKNOWN")
    issue_id = issue.get("id", "UNKNOWN")
    current_status = issue.get("status", "UNKNOWN")
    
    if dry_run:
        print(f"[DRY-RUN] Would cancel: {identifier} ({issue_id}) from {current_status}")
        return True
    
    try:
        result = paperclip_patch(issue_id, {"status": "cancelled"})
        print(f"[OK] Cancelled: {identifier} ({issue_id})")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to cancel {identifier} ({issue_id}): {e}")
        return False

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("--dry-run", "--confirm"):
        print("Usage: python3 scripts/cancel_recursive_postmortems.py [--dry-run|--confirm]")
        sys.exit(1)
    
    dry_run = sys.argv[1] == "--dry-run"
    
    if not PAPERCLIP_API_KEY:
        print("[ERROR] PAPERCLIP_API_KEY environment variable not set")
        sys.exit(1)
    
    print(f"[ Wheeljack ] Fetching all issues...")
    issues = get_all_issues()
    target = get_target_issues(issues)
    
    print(f"[ Wheeljack ] Found {len(target)} recursive postmortem tasks to cancel")
    
    if not target:
        print("[ Wheeljack ] No tasks to cancel. Exit.")
        sys.exit(0)
    
    if dry_run:
        print("[ Wheeljack ] DRY-RUN mode — no changes made")
        for t in target:
            cancel_issue(t, dry_run=True)
        print(f"[ Wheeljack ] Would cancel {len(target)} tasks. Run with --confirm to apply.")
    else:
        print("[ Wheeljack ] CANCELLING RECURSIVE POSTMORTEM TASKS")
        for t in target:
            cancel_issue(t, dry_run=False)
        print(f"[ Wheeljack ] Cancelled {len(target)} tasks.")

if __name__ == "__main__":
    main()
