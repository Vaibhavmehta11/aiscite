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
    
    DOM structure (as of 2026-04-27):
    - Container: div.job-search-card or div.base-card
    - Title: h3.base-search-card__title
    - Company: h4.base-search-card__subtitle
    - Location: span.job-search-card__location
    - Posted: time.job-search-card__listdate
    - Link: a.base-card__full-link
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[WARN] Playwright not installed. LinkedIn scrape disabled.")
        return []
    
    if not SESSION_PATH.exists():
        print("[WARN] LinkedIn session not found. Login manually and save cookies.")
        return []
    
    import json
    
    with open(SESSION_PATH) as f:
        cookies = json.load(f).get("cookies", [])
    
    if not cookies:
        print("[WARN] No LinkedIn cookies in session file.")
        return []
    
    jobs = []
    
    try:
        with sync_playwright() as p:
            # Launch with anti-detection flags
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            context.add_cookies(cookies)
            page = context.new_page()
            
            # Disable automation detection
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            # Build search URL
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
            print(f"[LINKEDIN] Searching: {search_url}")
            
            # Navigate with relaxed wait - LinkedIn never reaches networkidle
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)  # Let JS render and lazy-load jobs
            
            # Find job cards
            job_cards = page.query_selector_all("div.job-search-card")
            print(f"[LINKEDIN] Found {len(job_cards)} job cards")
            
            for card in job_cards[:limit]:
                try:
                    # Extract title
                    title_el = card.query_selector("h3.base-search-card__title")
                    title = title_el.inner_text().strip() if title_el else ""
                    
                    # Extract company
                    company_el = card.query_selector("h4.base-search-card__subtitle")
                    company = company_el.inner_text().strip() if company_el else ""
                    
                    # Extract location
                    location_el = card.query_selector("span.job-search-card__location")
                    job_location = location_el.inner_text().strip() if location_el else ""
                    
                    # Extract posted date
                    time_el = card.query_selector("time.job-search-card__listdate")
                    posted = time_el.get_attribute("datetime") if time_el and time_el.get_attribute("datetime") else time_el.inner_text().strip() if time_el else ""
                    
                    # Extract link - use the full-card-link
                    link_el = card.query_selector("a.base-card__full-link")
                    url = link_el.get_attribute("href") if link_el else ""
                    
                    # Extract full JD text (optional - requires clicking through)
                    jd_text = ""
                    
                    if title and company:
                        jobs.append({
                            "source": "linkedin",
                            "title": title,
                            "company": company,
                            "location": job_location,
                            "posted_date": posted,
                            "jd_text": jd_text,
                            "url": url,
                            "raw": {}
                        })
                except Exception as e:
                    print(f"[LINKEDIN] Error parsing card: {e}")
                    continue
            
            print(f"[LINKEDIN] Extracted {len(jobs)} jobs")
            browser.close()
    except Exception as e:
        print(f"[LINKEDIN] Browser error: {e}")
    
    return jobs


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
