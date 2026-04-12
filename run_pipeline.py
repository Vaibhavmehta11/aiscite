#!/usr/bin/env python3
"""Aiscite pipeline orchestrator.

Single command: scout -> audit -> score gate -> generate -> QA
No email sending. That stays manual.

Usage:
  python3 run_pipeline.py --city "Toronto" --type "med spa" --count 10
  python3 run_pipeline.py --csv targets_2026-04-11.csv
  python3 run_pipeline.py --audit audit_some-biz.json --push
"""
import argparse, csv, json, os, sys, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCORE_GATE = 65

def run(cmd, cwd=None, timeout=60):
    """Run a subprocess, return (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or SCRIPT_DIR
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"

def audit_one(name, url, city, biz_type):
    """Run audit.py on a single target. Returns audit dict or None."""
    cmd = f'python3 audit.py --name "{name}" --url "{url}" --city "{city}" --type "{biz_type}"'
    code, out, err = run(cmd, timeout=90)
    if code != 0:
        print(f"  AUDIT FAIL: {name} (exit {code}): {err}")
        return None
    # Find the output file
    from generate_report import slugify
    slug = slugify(name)
    audit_file = os.path.join(SCRIPT_DIR, f"audit_{slug}.json")
    if not os.path.exists(audit_file):
        print(f"  AUDIT FAIL: {name} - no output file {audit_file}")
        return None
    with open(audit_file) as f:
        return json.load(f)

def generate_and_qa(audit_file, push=False):
    """Generate report and run QA. Returns (slug, passed_qa)."""
    # Generate
    cmd = f'python3 generate_report.py --audit "{audit_file}"'
    if push:
        cmd += " --push"
    code, out, err = run(cmd, timeout=60)
    if code != 0:
        print(f"  GEN FAIL: {audit_file} (exit {code}): {err}")
        return None, False

    # Extract slug from audit
    with open(audit_file) as f:
        audit = json.load(f)
    from generate_report import slugify
    slug = slugify(audit["business_name"])

    # QA (only if pushed or local file exists)
    qa_cmd = f'python3 qa_report.py {slug} --audit "{audit_file}"'
    code, out, err = run(qa_cmd, timeout=30)
    passed = "PASS" in out and "FAIL" not in out.split("PASS")[-1].split("\n")[0]
    # More precise: check for "PASS - Ready for outreach"
    if "PASS - Ready for outreach" in out:
        passed = True
    elif "FAIL -" in out:
        passed = False

    return slug, passed

def pipeline_from_csv(csv_path, push=False, max_workers=5):
    """Run full pipeline from a targets CSV."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        targets = list(reader)

    print(f"Loaded {len(targets)} targets from {csv_path}")

    # Phase 1: Audit all targets (parallel)
    print(f"\n=== Phase 1: Auditing {len(targets)} targets ===")
    audits = []
    for t in targets:
        name = t["name"]
        url = t.get("url", "") or t.get("domain", "")
        if not url.startswith("http"):
            url = f"https://{url}"
        city = t["city"]
        biz_type = t["type"]
        result = audit_one(name, url, city, biz_type)
        if result:
            audits.append(result)
        time.sleep(0.5)  # Gentle rate limit

    # Phase 2: Score gate
    print(f"\n=== Phase 2: Score gate (<= {SCORE_GATE}) ===")
    qualified = []
    for a in audits:
        score = a["overall_score"]
        name = a["business_name"]
        if score <= SCORE_GATE:
            print(f"  PASS: {name} ({score}/100)")
            qualified.append(a)
        else:
            print(f"  SKIP: {name} ({score}/100) -- above gate")

    if not qualified:
        print("No targets passed score gate. Pipeline complete.")
        return

    # Phase 3: Generate + QA
    print(f"\n=== Phase 3: Generate + QA ({len(qualified)} qualified) ===")
    results = []
    for a in qualified:
        from generate_report import slugify
        slug = slugify(a["business_name"])
        audit_file = os.path.join(SCRIPT_DIR, f"audit_{slug}.json")
        slug_out, qa_passed = generate_and_qa(audit_file, push=push)
        status = "QA PASS" if qa_passed else "QA FAIL"
        print(f"  {status}: {slug} -> https://aiscite.com/audit/{slug}/")
        results.append({
            "slug": slug,
            "name": a["business_name"],
            "score": a["overall_score"],
            "qa_passed": qa_passed,
            "url": f"https://aiscite.com/audit/{slug}/",
        })

    # Summary
    print(f"\n=== Pipeline Complete ===")
    print(f"  Audited: {len(audits)}")
    print(f"  Passed gate: {len(qualified)}")
    qa_pass = sum(1 for r in results if r["qa_passed"])
    print(f"  QA passed: {qa_pass}")
    print(f"  QA failed: {len(results) - qa_pass}")

    if qa_pass > 0:
        print(f"\n  Ready for outreach ({qa_pass} businesses):")
        for r in results:
            if r["qa_passed"]:
                print(f"    {r['name']} ({r['score']}/100) -> {r['url']}")

    # Write summary JSON
    summary_file = os.path.join(SCRIPT_DIR, f"pipeline_results_{time.strftime('%Y-%m-%d')}.json")
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Summary: {summary_file}")

def pipeline_single_audit(audit_file, push=False):
    """Run pipeline on a single pre-existing audit JSON."""
    with open(audit_file) as f:
        audit = json.load(f)

    score = audit["overall_score"]
    name = audit["business_name"]

    if score > SCORE_GATE:
        print(f"SKIP: {name} scores {score}/100 -- above {SCORE_GATE} gate")
        return

    print(f"PASS: {name} ({score}/100) -- generating report")
    slug, qa_passed = generate_and_qa(audit_file, push=push)
    if qa_passed:
        print(f"QA PASS: https://aiscite.com/audit/{slug}/")
    else:
        print(f"QA FAIL: fix issues and re-run")

def main():
    p = argparse.ArgumentParser(description="Aiscite pipeline orchestrator")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="Path to targets CSV from scout.py")
    group.add_argument("--audit", help="Path to single audit JSON")
    group.add_argument("--scout", action="store_true", help="Run scout first (needs --city and --type)")
    p.add_argument("--city", help="City for scouting")
    p.add_argument("--type", help="Business type for scouting")
    p.add_argument("--count", type=int, default=30, help="Number of targets to scout")
    p.add_argument("--push", action="store_true", help="Push generated reports to GitHub")
    p.add_argument("--max-workers", type=int, default=5, help="Parallel audit workers")
    args = p.parse_args()

    if args.scout:
        if not args.city or not args.type:
            p.error("--scout requires --city and --type")
        print(f"=== Scouting: {args.type} in {args.city} ===")
        from datetime import date
        today = date.today().isoformat()
        csv_path = os.path.join(SCRIPT_DIR, f"targets_{today}.csv")
        cmd = f'python3 scout.py --city "{args.city}" --type "{args.type}" --count {args.count}'
        code, out, err = run(cmd, timeout=180)
        if code != 0:
            print(f"Scout failed: {err}")
            sys.exit(1)
        print(out)
        pipeline_from_csv(csv_path, push=args.push, max_workers=args.max_workers)

    elif args.csv:
        pipeline_from_csv(args.csv, push=args.push, max_workers=args.max_workers)

    elif args.audit:
        pipeline_single_audit(args.audit, push=args.push)

if __name__ == "__main__":
    main()
