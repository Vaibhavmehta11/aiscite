#!/usr/bin/env python3
"""
discovery.py - Job discovery pipeline for CEO job matching.
Wheeljack's minimalist systems architecture.

Design philosophy:
- Test before ship
- Simple > complex
- Persistent state (SQLite)
- Hermes-grade analysis on JD parse + scoring
"""

import sys
import hashlib
import json
import time
import re
from datetime import datetime
from pathlib import Path
import sqlite3

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[WARN] Playwright not installed. LinkedIn scrape disabled.")

try:
    import pandas as pd
except ImportError:
    pd = None

BASE_DIR = Path(__file__).parent
TRACKER_DB = BASE_DIR / "job_tracker.db"
SESSION_PATH = Path.home() / ".linkedin_state.json"


# -----------------------------------------------------------------------
# DB Schema
# -----------------------------------------------------------------------
def init_db():
    """Create SQLite tracker if not exists."""
    conn = sqlite3.connect(TRACKER_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            company TEXT,
            location TEXT,
            posted_date TEXT,
            jd_text TEXT,
            url TEXT,
            raw_data TEXT,
            status TEXT DEFAULT 'discovered',
            score REAL DEFAULT 0,
            scanned_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(title)")
    conn.commit()
    conn.close()
    return TRACKER_DB


def job_hash(source: str, title: str, company: str, url: str, posted_date: str = "") -> str:
    """Generate stable job_id from source+title+company+url."""
    data = f"{source}|{title}|{company}|{url}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def insert_job(conn, source: str, title: str, company: str, location: str,
               posted_date: str, jd_text: str, url: str, raw_data: dict = None):
    """Insert or ignore job. Returns (inserted, job_id)."""
    job_id = job_hash(source, title, company, url, posted_date)
    raw_str = json.dumps(raw_data or {}, ensure_ascii=False)

    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO jobs (job_id, source, title, company, location, posted_date, jd_text, url, raw_data, status, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', 0)
    """, (job_id, source, title, company, location, posted_date, jd_text, url, raw_str))
    inserted = cur.rowcount > 0
    conn.commit()
    return inserted, job_id


def count_jobs(conn, status: str = None):
    """Return job counts."""
    cur = conn.cursor()
    if status:
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", (status,))
    else:
        cur.execute("SELECT COUNT(*) FROM jobs")
    return cur.fetchone()[0]


def get_pending_jobs(conn, limit: int = None):
    """Get jobs with status='discovered', ordered by newest first."""
    cur = conn.cursor()
    if limit:
        cur.execute("SELECT * FROM jobs WHERE status = 'discovered' ORDER BY scanned_at DESC LIMIT ?", (limit,))
    else:
        cur.execute("SELECT * FROM jobs WHERE status = 'discovered' ORDER BY scanned_at DESC")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def update_job_status(conn, job_id: str, status: str, score: float = None):
    """Update job status (and optionally score)."""
    cur = conn.cursor()
    if score is not None:
        cur.execute("UPDATE jobs SET status = ?, score = ? WHERE job_id = ?", (status, score, job_id))
    else:
        cur.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))
    conn.commit()


# -----------------------------------------------------------------------
# Sources
# -----------------------------------------------------------------------
def scrape_linkedin(job_title: str, location: str, limit: int = 20) -> list:
    """
    Scrape LinkedIn job listings via Playwright.
    Uses persistent auth from ~/.linkedin_state.json.
    Returns list of job dicts.
    """
    if not hasattr(scrape_linkedin, '_warned'):
        scrape_linkedin._warned = True
        print("[WARN] LinkedIn scrape disabled - DOM structure changed. Use CSV import instead.")

    # TODO: Fix this - LinkedIn DOM has changed
    return []


def scrape_indeed(job_title: str, location: str, limit: int = 20, dry_run: bool = False) -> list:
    """Scrape Indeed job listings (simple fallback)."""
    jobs = []

    if dry_run:
        # Mock response for testing
        jobs = [
            {"source": "indeed", "title": "Chief Executive Officer", "company": "TechCorp Inc", "location": "San Francisco, CA", "posted_date": datetime.now().strftime("%Y-%m-%d"), "jd_text": "Seeking visionary CEO...", "url": "https://indeed.com/mock1", "raw": {}},
            {"source": "indeed", "title": "CEO", "company": "Sports Ventures LLC", "location": "Miami, FL", "posted_date": datetime.now().strftime("%Y-%m-%d"), "jd_text": "CPL team leadership...", "url": "https://indeed.com/mock2", "raw": {}},
        ][:limit]
        return jobs

    return jobs


def import_csv(filepath: str) -> list:
    """Import jobs from CSV file."""
    if pd is None:
        print("[ERROR] pandas not installed. Run: pip install pandas")
        return []
    
    df = pd.read_csv(filepath)
    required_cols = ['title', 'company', 'location', 'url']
    if not all(c in df.columns for c in required_cols):
        print(f"[ERROR] CSV must have columns: {required_cols}")
        return []
    
    jobs = []
    for _, row in df.iterrows():
        jobs.append({
            "source": "csv",
            "title": str(row["title"]).strip(),
            "company": str(row["company"]).strip(),
            "location": str(row["location"]).strip() if pd.notna(row.get("location")) else "",
            "posted_date": datetime.now().strftime("%Y-%m-%d"),
            "jd_text": str(row["description"]).strip() if pd.notna(row.get("description")) else "",
            "url": str(row["url"]).strip(),
            "raw": {}
        })
    return jobs


# -----------------------------------------------------------------------
# CLI Entry Points
# -----------------------------------------------------------------------
def run_search(args):
    """Run discovery search across sources."""
    init_db()
    conn = sqlite3.connect(TRACKER_DB)

    print(f"[DISCOVERY] Searching for '{args.title}' in '{args.location}'")
    print("[DISCOVERY] Sources:", args.sources)

    sources_map = {
        "linkedin": scrape_linkedin,
        "indeed": scrape_indeed,
        "csv": lambda *a: []
    }

    for src in args.sources.split(","):
        src = src.strip()
        if src == "csv":
            # Handle CSV import differently
            continue
        if src not in sources_map:
            continue
        print(f"[DISCOVERY] Running {src}...")
        try:
            jobs = sources_map[src](args.title, args.location, limit=args.limit)
            inserted = 0
            for job in jobs:
                ok, job_id = insert_job(conn, source=job["source"], title=job["title"],
                    company=job["company"], location=job["location"],
                    posted_date=job["posted_date"], jd_text=job["jd_text"],
                    url=job["url"], raw_data=job.get("raw", {}))
                if ok:
                    inserted += 1
            print(f"[DISCOVERY] {src}: {len(jobs)} found, {inserted} inserted")
        except Exception as e:
            print(f"[DISCOVERY] {src} error: {e}")

    # CSV import
    if "csv" in args.sources:
        csv_path = args.csv_file if hasattr(args, "csv_file") and args.csv_file else ""
        if csv_path and Path(csv_path).exists():
            print(f"[DISCOVERY] Importing CSV: {csv_path}")
            jobs = import_csv(csv_path)
            inserted = 0
            for job in jobs:
                ok, job_id = insert_job(conn, **job)
                if ok:
                    inserted += 1
            print(f"[DISCOVERY] csv: {len(jobs)} found, {inserted} inserted")

    total = count_jobs(conn, "discovered")
    print(f"[DISCOVERY] Total pending jobs: {total}")
    conn.close()


def run_import(args):
    """Import jobs from CSV file."""
    init_db()
    conn = sqlite3.connect(TRACKER_DB)

    if not Path(args.csv_file).exists():
        print(f"[ERROR] CSV file not found: {args.csv_file}")
        conn.close()
        return

    print(f"[IMPORT] Importing from {args.csv_file}")
    jobs = import_csv(args.csv_file)
    inserted = 0
    for job in jobs:
        ok, job_id = insert_job(conn, **job)
        if ok:
            inserted += 1

    print(f"[IMPORT] Total: {len(jobs)} imported, {inserted} new")
    conn.close()


def run_stats(args):
    """Print job tracker stats."""
    init_db()
    conn = sqlite3.connect(TRACKER_DB)

    total = count_jobs(conn)
    discovered = count_jobs(conn, "discovered")
    scored = count_jobs(conn, "scored")
    applied = count_jobs(conn, "applied")

    print(f"Total jobs tracked: {total}")
    print(f"  - Discovered: {discovered}")
    print(f"  - Scored: {scored}")
    print(f"  - Applied: {applied}")
    conn.close()


def run_digest(args):
    """Print digest of top jobs."""
    init_db()
    conn = sqlite3.connect(TRACKER_DB)

    jobs = get_pending_jobs(conn, limit=args.limit)
    if not jobs:
        print("[DIGEST] No pending jobs found. Run discovery or import first.")
        conn.close()
        return

    print(f"\n{'='*80}")
    print("DAILY JOB DIGEST")
    print(f"{'='*80}\n")
    print(f"Total pending: {count_jobs(conn, 'discovered')}")
    print(f"Showing top {len(jobs)}:\n")

    for job in jobs:
        print(f"[{job['source'].upper()}] {job['title']}")
        print(f"    {job['company']} | {job['location']}")
        if job['jd_text']:
            preview = job['jd_text'][:200] + "..." if len(job['jd_text']) > 200 else job['jd_text']
            print(f"    JD: {preview}")
        print(f"    {job['url']}")
        print()

    conn.close()


# -----------------------------------------------------------------------
# Main CLI
# -----------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Job discovery pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Discover new jobs")
    p_search.add_argument("--title", default="CEO")
    p_search.add_argument("--location", default="USA")
    p_search.add_argument("--sources", default="csv")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--csv-file", help="CSV file path for import")
    p_search.set_defaults(func=run_search)

    # import
    p_import = subparsers.add_parser("import", help="Import jobs from CSV")
    p_import.add_argument("--csv-file", required=True)
    p_import.set_defaults(func=run_import)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show job tracker stats")
    p_stats.set_defaults(func=run_stats)

    # digest
    p_digest = subparsers.add_parser("digest", help="Print daily digest")
    p_digest.add_argument("--limit", type=int, default=10)
    p_digest.set_defaults(func=run_digest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
