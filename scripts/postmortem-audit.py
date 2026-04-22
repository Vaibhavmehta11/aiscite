#!/usr/bin/env python3
"""
Wheeljack's First-Principles Postmortem Audit

Every outcome gets a postmortem within 48 hours. No exceptions.
No templates. No filler. Analyze git state, compare target vs. actual,
and produce actionable systemic fixes.

Usage:
  python3 scripts/postmortem-audit.py <issue_identifier>
  python3 scripts/postmortem-audit.py --all

Requirements:
  - PAPERCLIP_API_URL, PAPERCLIP_API_KEY, PAPERCLIP_AGENT_ID, PAPERCLIP_COMPANY_ID env vars set
  - Local git repo state must reflect actual work (committed or untracked)
"""

import os
import sys
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path

# ———— CONFIG ————————————————————————————————————————————————————————
AISCITE_ROOT = Path("/home/nikunj19/Projects/aiscite")
PAPERCLIP_API_URL = os.environ.get("PAPERCLIP_API_URL", "http://127.0.0.1:3100")
PAPERCLIP_API_KEY = os.environ.get("PAPERCLIP_API_KEY", "")
PAPERCLIP_AGENT_ID = os.environ.get("PAPERCLIP_AGENT_ID", "26825051-97c8-4cfb-882d-9749252619c4")
PAPERCLIP_COMPANY_ID = os.environ.get("PAPERCLIP_COMPANY_ID", "891ba9d1-4a11-4d90-87aa-afba1d7f00db")

# ———— GIT UTILS (first principles) —————————————————————————————————————————
def git_status():
    """Return git status dict."""
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=AISCITE_ROOT,
        capture_output=True,
        text=True,
        check=True
    )
    return res.stdout.strip()

def git_diff_index():
    """Return commits ahead/behind."""
    res = subprocess.run(
        ["git", "log", "--oneline", "HEAD...origin/main"],
        cwd=AISCITE_ROOT,
        capture_output=True,
        text=True,
        check=False
    )
    diff = res.stdout.strip().split("\n") if res.stdout.strip() else []
    ahead = len([l for l in diff if l and "origin" not in l]) if diff else 0
    return ahead, diff

def is_git_clean():
    """Check if git state is clean (committed + pushed)."""
    status = git_status()
    if status:
        return False
    ahead, _ = git_diff_index()
    return ahead == 0

# ———— PAPERCLIP CLIENT ———————————————————————————————————————————————
def paperclip_get(endpoint):
    """Fetch from Paperclip API."""
    import urllib.request
    url = f"{PAPERCLIP_API_URL}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {PAPERCLIP_API_KEY}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def paperclip_patch(issue_id, data):
    """Update issue via Paperclip API."""
    import urllib.request
    url = f"{PAPERCLIP_API_URL}/api/issues/{issue_id}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="PATCH")
    req.add_header("Authorization", f"Bearer {PAPERCLIP_API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def paperclip_comment(issue_id, body):
    """Add a comment to issue."""
    import urllib.request
    url = f"{PAPERCLIP_API_URL}/api/issues/{issue_id}/comments"
    req = urllib.request.Request(url, data=json.dumps({"body": body}).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {PAPERCLIP_API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

# ———— POSTMORTEM LOGIC ————————————————————————————————————————————————
def analyze_issue(issue_id: str):
    """
    Analyze a completed issue and produce postmortem content.
    Returns dict with: outcome, worked, failed, root_cause, fix, action_items
    """
    # Fetch issue details
    issue = paperclip_get(f"/api/issues/{issue_id}")
    title = issue.get("title", "")
    
    # FIRST-PRINCIPLES GUARD: never postmortem a postmortem
    if title.startswith("Postmortem:"):
        print(f"[ Wheeljack ] Skipping postmortem postmortem: {title}")
        return None
    
    identifier = issue.get("identifier", issue_id)
    completedAt = issue.get("completedAt")
    
    # ———— ACTUAL STATE —————————————————————————————
    clean = is_git_clean()
    ahead, diff = git_diff_index()
    status = git_status()
    untracked_count = len([l for l in status.split("\n") if l.startswith("??")]) if status else 0
    
    # ———— ANALYSIS —————————————————————————————————————————
    outcome = {
        "identifier": identifier,
        "title": title,
        "completedAt": completedAt or datetime.now(timezone.utc).isoformat(),
        "git_clean": clean,
        "commits_ahead": ahead,
        "untracked_files": untracked_count,
    }
    
    worked = []
    failed = []
    root_cause = []
    fix = []
    action_items = []
    
    # First-principles check: Did the work meet its success criteria?
    # For aiscite pipeline runs, success = (1) regenerate audit reports, (2) commit, (3) push
    if "audit" in title.lower() or "aut-" in title.lower():
        # This was an audit report regeneration run
        if clean:
            outcome["success"] = True
            worked.extend(["Audit reports regenerated", "Successfully committed", "Successfully pushed"])
        else:
            outcome["success"] = False
            failed.extend(["Audit reports regenerated", "Failed to commit", "Failed to push"])
            root_cause.extend([
                "No push hook or guard in pipeline",
                "No automated CI check requiring push before marking complete",
                "No alerting on outstanding local commits",
                "Human error in manual push step"
            ])
            fix.extend([
                "Add push hook to pipeline runner (run_pipeline.py)",
                "Add CI check: `git log --oneline HEAD...origin/main` must be empty before issue close",
                "Add push alert on main branch checkout or nightly cron"
            ])
            action_items.extend([
                f"Issue: Add push hook to aiscite pipeline runner (run_pipeline.py)",
                f"Issue: Add CI check: `git push` required before issue close",
                f"Issue: Add nightly cron to alert on unpushed commits"
            ])
    else:
        # Generic issue — if git is not clean, it failed
        if clean:
            outcome["success"] = True
            worked.append("Work completed and delivered")
        else:
            outcome["success"] = False
            failed.append("Work completed but not delivered (no commit/push)")
            root_cause.append("No commit/push guard in task execution")
            fix.append("Add pre-close git status check to task orchestration")
            action_items.append(f"Issue: Add git clean/sync check before issue closure")
    
    return {
        "outcome": outcome,
        "worked": worked,
        "failed": failed,
        "root_cause": root_cause,
        "fix": fix,
        "action_items": action_items
    }

def postmortem_md(post):
    """Render postmortem as markdown for Paperclip description."""
    outcome = post["outcome"]
    worked = post["worked"]
    failed = post["failed"]
    root = post["root_cause"]
    fix = post["fix"]
    action = post["action_items"]
    
    lines = [
        f"## Postmortem: {outcome['identifier']}",
        "",
        f"**Original Issue:** {outcome['identifier']}  ",
        f"**Completed:** {outcome['completedAt']}  ",
    ]
    
    # Safe string formatting — avoid f-nesting
    if outcome['git_clean']:
        lines.append(f"**Git Status:** clean")
    else:
        ahead = outcome.get("commits_ahead", 0)
        untracked = outcome.get("untracked_files", 0)
        lines.append(f"**Git Status:** UNPUSHED ({ahead} commits ahead, {untracked} untracked files)")
    
    lines.extend([
        "",
        "## 1. Outcome vs Target",
        "",
        "| Metric | Target | Actual | Gap |",
        "|--------|--------|--------|-----|",
    ])
    
    git_text = "Pushed" if outcome["git_clean"] else "Unpushed"
    success_text = "Done" if outcome.get("success") else "Failed"
    gap_text = "-" if outcome["git_clean"] else "FAIL"
    success_gap = "-" if outcome.get("success") else "FAIL"
    
    lines.append(f"| Git sync | Pushed | {git_text} | {gap_text} |")
    lines.append(f"| Success criteria | Done | {success_text} | {success_gap} |")
    
    lines.extend([
        "",
        "## 2. What Worked",
        "",
    ])
    if worked:
        for w in worked:
            lines.append(f"- {w}")
    else:
        lines.append("- *None identified*")
    
    lines.extend([
        "",
        "## 3. What Failed",
        "",
    ])
    if failed:
        for f in failed:
            lines.append(f"- {f}")
    else:
        lines.append("- *None*")
    
    lines.extend([
        "",
        "## 4. Root Cause Analysis",
        "",
        "### 5 Whys",
        "",
    ])
    if root:
        for i, r in enumerate(root, 1):
            lines.append(f"- Why {i}: {r}")
    else:
        lines.append("- *Root cause not yet established*")
    
    lines.extend([
        "",
        "## 5. Systemic Fix Required",
        "",
    ])
    if fix:
        for f in fix:
            lines.append(f"- {f}")
    else:
        lines.append("- *No systemic fix required*")
    
    lines.extend([
        "",
        "## 6. Action Items",
        "",
    ])
    if action:
        for a in action:
            lines.append(f"- [ ] {a}")
    else:
        lines.append("- *No action items*")
    
    lines.extend([
        "",
        "---",
        "",
        "*Postmortem auto-analyzed by Wheeljack*  ",
        "*Run: ./scripts/postmortem-audit.py*",
    ])
    
    return "\n".join(lines)

# ———— MAIN ——————————————————————————————————————————————————————————————
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/postmortem-audit.py <issue_id> | --all")
        sys.exit(1)
    
    if sys.argv[1] == "--all":
        # Fetch all completed issues with no postmortem
        issues = paperclip_get(f"/api/companies/{PAPERCLIP_COMPANY_ID}/issues")
        # Find completed ones with status=done but no existing postmortem link
        candidates = [i for i in issues if i.get("status") == "done" and i.get("id")]
        print(f"[ Wheeljack ] Found {len(candidates)} completed issues. Analyzing in batches...")
        
        import time
        batch_size = 5
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            print(f"[ Wheeljack ] Processing batch {i//batch_size + 1} ({len(batch)} issues)...")
            for item in batch:
                identifier = item.get("identifier", item.get("id"))
                try:
                    post = analyze_issue(identifier)
                    if post is None:
                        print(f"[ Wheeljack ] Skipped (postmortem of postmortem): {identifier}")
                        continue
                    md = postmortem_md(post)
                    paperclip_comment(identifier, f"**Postmortem analysis:**\n\n{md[:2000]}...")
                    print(f"[ Wheeljack ] Commented on {identifier}")
                except Exception as e:
                    print(f"[ ERROR ] Failed on {identifier}: {e}")
            time.sleep(10)  # 10-second delay between batches
    else:
        issue_id = sys.argv[1]
        print(f"[ Wheeljack ] Analyzing {issue_id}...")
        post = analyze_issue(issue_id)
        if post is None:
            print(f"[ Wheeljack ] Skipped (postmortem of postmortem): {issue_id}")
            sys.exit(0)
        md = postmortem_md(post)
        print(md)
        
        # Add comment
        paperclip_comment(issue_id, f"**Postmortem analysis:**\n\n`{md[:2000]}...`")
        print(f"\n[ Wheeljack ] Commented on {issue_id}")

if __name__ == "__main__":
    main()
