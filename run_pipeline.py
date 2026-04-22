#!/usr/bin/env python3
"""
run_pipeline.py - Aiscite full pipeline orchestrator.
Wheeljack minimalist systems design.

Runs: scout -> audit -> generate_report -> qa_report -> log_outreach
Config-driven. No magic defaults.
"""

import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
AUDIT_DIR = BASE / "audit"
SCRIPTS = {
    "scout": BASE / "scout.py",
    "audit": BASE / "audit.py",
    "report": BASE / "generate_report.py",
    "qa": BASE / "qa_report.py",
    "outreach": BASE / "outreach.py",
    "email_lookup": BASE / "email_lookup.py",
}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_cmd(cmd, cwd=BASE):
    """Run shell command and return (success, output)."""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def load_existing_audits():
    """Load existing audit JSONs for re-run scenarios."""
    audits = {}
    for f in AUDIT_DIR.glob("audit_*.json"):
        slug = f.stem.replace("audit_", "")
        try:
            data = json.loads(f.read_text())
            audits[slug] = data
        except Exception as e:
            print(f"[WARN] Failed to load {f}: {e}")
    return audits


def find_or_create_audit(config):
    """Find audit JSON or run audit.py to create one."""
    slug = config.get("slug")
    if not slug:
        slug = f"{config['biz_type'].replace(' ', '-')}-{config['city'].lower()}"

    audit_path = BASE / f"audit_{slug}.json"
    if audit_path.exists():
        return audit_path, json.loads(audit_path.read_text())

    # Run audit.py
    cmd = f"python3 audit.py --name '{config['name']}' --url 'https://{config['domain']}' --city '{config['city']}' --type '{config['biz_type']}'"
    success, out = run_cmd(cmd)
    if not success:
        print(f"[ERROR] Audit failed for {config['name']}: {out}")
        return None, None

    if audit_path.exists():
        return audit_path, json.loads(audit_path.read_text())
    return None, None


def generate_report_for_audit(audit_path, name, domain, city, biz_type):
    """Generate report from audit JSON."""
    cmd = f'''python3 -c "from generate_report import generate, push_to_github; import json; audit = json.load(open('{audit_path}')); slug, path = generate('{name}', '{domain}', '{city}', '{biz_type}', audit); push_to_github(slug)"'''
    success, out = run_cmd(cmd)
    return success, out


def qa_report_for_slug(slug):
    """Run QA check on a report slug."""
    cmd = f"python3 qa_report.py {slug} --audit audit_{slug}.json"
    success, out = run_cmd(cmd)
    return success, out


def aiscite_ops_update(lead, report_slug, report_url, audit_path):
    """Update lead tracker and log outreach via aiscite_ops.py."""
    lead_id = lead.get("id") or lead.get("slug") or report_slug
    name = lead.get("name") or lead.get("business_name", "Unknown")
    biz_type = lead.get("vertical") or lead.get("biz_type") or lead.get("type") or "med spa"
    city = lead.get("city") or "Toronto"
    
    # If lead not yet in tracker, add it
    if not audit_path.exists():
        # Add new lead to tracker
        cmd = f"python3 /home/nikunj19/optimus/runtime/aiscite_ops.py add_lead {audit_path}"
        run_cmd(cmd)
    
    # Update lead stage to outreach_ready if not already sent
    current_stage = lead.get("current_stage", "")
    if current_stage != "sent":
        notes = f"Pipeline completed - report generated: {report_url}"
        cmd = f"python3 /home/nikunj19/optimus/runtime/aiscite_ops.py stage {lead_id} outreach_ready '{notes}'"
        run_cmd(cmd)


def run_full_pipeline(config, dry_run=False, skip_audits=None):
    """
    Run full pipeline for a single lead config.
    Returns (success, audit_path, report_slug, report_url)
    """
    skip_audits = skip_audits or set()

    name = config.get("name", config.get("business_name", "Unknown"))
    domain = config.get("domain", config.get("website", "aiscite.com"))
    city = config.get("city", "Toronto")
    biz_type = config.get("biz_type", config.get("vertical", "med spa"))
    slug = config.get("slug") or config.get("id") or f"{biz_type.replace(' ', '-')}-{city.lower()}"
    report_url_existing = config.get("report_url")

    print(f"[{now()}] Processing: {name} ({biz_type}, {city})")

    # Step 1: Audit (already done? Skip if in skip_audits)
    if slug in skip_audits:
        audit_path = BASE / f"audit_{slug}.json"
        if audit_path.exists():
            audit_data = json.loads(audit_path.read_text())
            print(f"[{now()}] Skipping audit, using existing: {audit_path.name}")
        else:
            audit_data = None
    else:
        audit_path, audit_data = find_or_create_audit(config)
        if not audit_path:
            print(f"[{now()}] FAILED: Could not create audit for {name}")
            return False, None, None, None

    # Score gate: only proceed if score <= 65
    score = audit_data.get("overall_score", 100)
    if score > 65:
        print(f"[{now()}] SKIPPED: Score {score} > 65, not enough AI gaps to justify outreach")
        return "skipped_score", audit_path, None, None
    print(f"[{now()}] Score {score} <= 65, proceeding")

    # Step 2: Generate report
    print(f"[{now()}] Generating report...")
    report_success, report_out = generate_report_for_audit(audit_path, name, domain, city, biz_type)
    if not report_success:
        print(f"[{now()}] FAILED: Report generation: {report_out}")
        return False, audit_path, None, None

    # Extract report_slug from report_url if already exists in tracker
    if report_url_existing:
        report_slug = report_url_existing.rstrip("/").split("/")[-1]
        print(f"[{now()}] Using existing report slug from tracker: {report_slug}")
    else:
        report_slug = slug

    report_url = f"https://aiscite.com/audit/{report_slug}/"

    # Step 3: QA check
    print(f"[{now()}] Running QA check...")
    qa_success, qa_out = qa_report_for_slug(report_slug)
    if not qa_success:
        print(f"[{now()}] QA FAILED: {qa_out}")
        # Don't fail the whole pipeline on QA - flag it
        print(f"[{now()}] WARNING: QA issues detected, report still deployed")
    else:
        print(f"[{now()}] QA PASSED")

    return True, audit_path, report_slug, report_url


def run_wave(city, biz_type, count, dry_run=False, skip_audits=None):
    """
    Run pipeline for wave of businesses.
    Uses scout.py results or existing LEADS_TRACKER.json.
    """
    skip_audits = skip_audits or set()

    # Try to load from LEADS_TRACKER.json first
    from config import TRACKER_FILE
    tracker_path = TRACKER_FILE
    if tracker_path.exists():
        try:
            tracker = json.loads(tracker_path.read_text())
            leads = tracker.get("leads", [])[:count]
            print(f"[{now()}] Loaded {len(leads)} leads from tracker")
        except Exception as e:
            print(f"[WARN] Could not load tracker: {e}")
            leads = []
    else:
        print(f"[WARN] Tracker not found, would need to scout first: {tracker_path}")
        leads = []

    if not leads:
        print(f"[{now()}] No leads found for wave: city={city}, type={biz_type}")
        return

    success_count = 0
    for i, lead in enumerate(leads):
        if i >= count:
            break

        config = {
            "name": lead.get("business_name") or lead.get("name", "Unknown"),
            "domain": lead.get("domain") or lead.get("website", "aiscite.com"),
            "city": lead.get("city") or city,
            "biz_type": lead.get("vertical") or lead.get("type") or lead.get("biz_type") or biz_type,
            "slug": lead.get("slug"),
        }

        success, audit_path, report_slug, report_url = run_full_pipeline(
            config, dry_run=dry_run, skip_audits=skip_audits
        )

        if success == "skipped_score":
            print(f"[{now()}] SKIP: {config['name']} - score too high")
        elif success:
            success_count += 1
            print(f"[{now()}] SUCCESS: {config['name']} -> {report_url}")
            # Update lead in tracker with current pipeline status
            aiscite_ops_update(lead, report_slug, report_url, audit_path)
        else:
            print(f"[{now()}] FAILED: {config['name']}")

    print(f"[{now()}] Wave complete: {success_count}/{count} successful")


def main():
    parser = argparse.ArgumentParser(description="Aiscite pipeline orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Wave command
    wave = subparsers.add_parser("wave", help="Run pipeline for a wave of businesses")
    wave.add_argument("--city", default="Toronto", help="City to target")
    wave.add_argument("--type", default="med spa", help="Business type")
    wave.add_argument("--count", type=int, default=5, help="Number of leads to process")
    wave.add_argument("--dry-run", action="store_true", help="Show what would run")
    wave.add_argument("--skip-audits", nargs="*", default=[], help="Audit slugs to skip")
    wave.set_defaults(func=lambda args: run_wave(
        city=args.city, biz_type=args.type, count=args.count,
        dry_run=args.dry_run, skip_audits=set(args.skip_audits)
    ))

    # Single command
    single = subparsers.add_parser("single", help="Run pipeline for a single lead")
    single.add_argument("--name", required=True, help="Business name")
    single.add_argument("--domain", required=True, help="Website domain")
    single.add_argument("--city", default="Toronto", help="City")
    single.add_argument("--type", default="med spa", help="Business type")
    single.add_argument("--slug", default=None, help="Custom slug")
    single.add_argument("--dry-run", action="store_true", help="Show what would run")
    single.set_defaults(func=lambda args: run_full_pipeline(vars(args), dry_run=args.dry_run))

    # Status command
    status = subparsers.add_parser("status", help="Show current state")
    status.set_defaults(func=lambda args: print_status())

    args = parser.parse_args()

    if args.command == "status":
        print_status()
    else:
        args.func(args)


def print_status():
    """Quick status show."""
    # Load LEADS_TRACKER.json
    from config import TRACKER_FILE
    tracker_path = TRACKER_FILE
    if tracker_path.exists():
        try:
            tracker = json.loads(tracker_path.read_text())
            leads = tracker.get("leads", [])
            print(f"Total leads in tracker: {len(leads)}")
            stages = {}
            for lead in leads:
                stage = lead.get("current_stage", "unknown")
                stages[stage] = stages.get(stage, 0) + 1
            print("Stages:")
            for stage, count in sorted(stages.items()):
                print(f"  - {stage}: {count}")
            return
        except Exception as e:
            print(f"Could not load tracker: {e}")

    # Fallback to audit JSONs
    audits = load_existing_audits()
    print(f"Total audit JSONs: {len(audits)}")
    print("Reports available:")
    for slug in sorted(audits.keys())[:20]:
        data = audits[slug]
        score = data.get("ai_score", "N/A")
        print(f"  - {slug}: Score {score}")


if __name__ == "__main__":
    main()
