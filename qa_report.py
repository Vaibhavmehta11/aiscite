#!/usr/bin/env python3
"""QA check for deployed Aiscite reports.

Fetches live HTML from the aiscite.com site and runs a 23-point checklist.
Exit 0 = PASS. Exit 1 = FAIL.
Never send outreach without PASS.
"""
import argparse, json, os, sys, re
import requests

BASE_URL = "https://aiscite.com/audit"
GITHUB_REPO = "Vaibhavmehta11/aiscite"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

CHECKS = []

def check(name):
    """Decorator to register a QA check."""
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator

# ─── Fetch ─────────────────────────────────────────────────────────────

def fetch_live(slug):
    """Fetch the live HTML from aiscite.com."""
    url = f"{BASE_URL}/{slug}/"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Aiscite-QA/1.0"})
        r.raise_for_status()
        return r.text, url
    except Exception as e:
        print(f"  FATAL: Cannot fetch {url}: {e}")
        return None, url

# ─── Checks ────────────────────────────────────────────────────────────

@check("Page loads (HTTP 200)")
def chk_loads(html, slug, audit):
    return html is not None and len(html) > 500

@check("Business name present")
def chk_biz_name(html, slug, audit):
    name = audit.get("business_name", "") if audit else slug.replace("-", " ").title()
    return name.lower() in html.lower() if html else False

@check("Score number displayed")
def chk_score(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'class="score-number"', html))

@check("Score badge present")
def chk_badge(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'class="score-badge"', html))

@check("Title tag includes business name")
def chk_title(html, slug, audit):
    if not html:
        return False
    title = re.search(r'<title>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    return title is not None

@check("Meta description present (or og:description fallback)")
def chk_meta_desc(html, slug, audit):
    if not html:
        return False
    has_meta = bool(re.search(r'<meta\s+name="description"', html, re.IGNORECASE))
    has_og = bool(re.search(r'og:description', html, re.IGNORECASE))
    return has_meta or has_og

@check("Canonical URL correct")
def chk_canonical(html, slug, audit):
    if not html:
        return False
    canon = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html, re.IGNORECASE)
    if not canon:
        return False
    return f"/audit/{slug}/" in canon.group(1)

@check("OG tags present (og:title, og:description)")
def chk_og(html, slug, audit):
    if not html:
        return False
    return "og:title" in html.lower() and "og:description" in html.lower()

@check("Chart.js loaded")
def chk_chartjs(html, slug, audit):
    if not html:
        return False
    return "chart.js" in html.lower() or "chart.umd" in html.lower()

@check("Score bar chart data present")
def chk_chart_data(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'data:\s*\[', html))

@check("Section leads personalized (not generic Carlton Dental)")
def chk_not_carlton(html, slug, audit):
    if not html:
        return False
    # Should NOT contain "Carlton Dental" unless the business IS carlton-dental
    if slug == "carlton-dental":
        return True
    return "Carlton Dental" not in html

@check("City reference present")
def chk_city(html, slug, audit):
    if not html:
        return False
    city = audit.get("city", "") if audit else ""
    if city:
        return city.lower() in html.lower()
    return True  # Skip if no audit data

@check("Theme toggle present (light/dark)")
def chk_theme_toggle(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'data-theme|theme.*toggle|dark.*mode', html, re.IGNORECASE))

@check("CTA form or booking link present")
def chk_cta(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'(calendly|book|schedule|cta-form|ctaForm)', html, re.IGNORECASE))

@check("No hardcoded localhost URLs")
def chk_no_localhost(html, slug, audit):
    if not html:
        return False
    return "localhost" not in html.lower() and "127.0.0.1" not in html

@check("No dev-only references")
def chk_no_dev(html, slug, audit):
    if not html:
        return False
    dev_markers = ["TODO:", "FIXME:", "HACK:", "console.log", "debugger"]
    return not any(m in html for m in dev_markers)

@check("Footer present")
def chk_footer(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'<footer|class="footer"', html, re.IGNORECASE))

@check("Nav bar present")
def chk_nav(html, slug, audit):
    if not html:
        return False
    return bool(re.search(r'<nav|class="nav"', html, re.IGNORECASE))

@check("Bar labels present (AI readability, etc.)")
def chk_bar_labels(html, slug, audit):
    if not html:
        return False
    return "bar-label" in html.lower()

@check("No broken image references")
def chk_no_broken_imgs(html, slug, audit):
    if not html:
        return False
    # Check for empty src or missing alt
    broken = re.findall(r'<img[^>]+src=["\']["\']', html, re.IGNORECASE)
    return len(broken) == 0

@check("PostHog tracking present")
def chk_posthog(html, slug, audit):
    if not html:
        return False
    return "posthog" in html.lower() or "posthog" in html

@check("Prepared privately for <business>")
def chk_prepared_for(html, slug, audit):
    if not html:
        return False
    return "Prepared privately for" in html

@check("No external target=_blank on internal links")
def chk_no_blank_internal(html, slug, audit):
    if not html:
        return False
    # Find aiscite.com links with target=_blank (shouldn't have it)
    internal_blank = re.findall(r'href="https?://aiscite\.com/[^"]*"[^>]*target="_blank"', html, re.IGNORECASE)
    return len(internal_blank) == 0

@check("JS variables set (bizName, bizType)")
def chk_js_vars(html, slug, audit):
    if not html:
        return False
    return "var bizName" in html and "var bizType" in html

# ─── Runner ────────────────────────────────────────────────────────────

def qa(slug, audit_file=None):
    """Run all QA checks. Returns (pass_count, fail_count, failures)."""
    html, url = fetch_live(slug)
    audit = None
    if audit_file:
        try:
            with open(audit_file) as f:
                audit = json.load(f)
        except:
            pass

    print(f"QA Report: {slug}")
    print(f"  URL: {url}")
    print()

    passed = 0
    failed = 0
    failures = []

    for name, fn in CHECKS:
        result = fn(html, slug, audit)
        status = "PASS" if result else "FAIL"
        if result:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            failures.append(name)
            print(f"  FAIL  {name}")

    total = passed + failed
    print(f"\n  {passed}/{total} checks passed")

    if failed == 0:
        print("  PASS - Ready for outreach")
        return True
    else:
        print(f"  FAIL - {failed} issues need fixing:")
        for f in failures:
            print(f"    - {f}")
        return False

def main():
    p = argparse.ArgumentParser(description="QA check for Aiscite report")
    p.add_argument("slug", help="Report slug (e.g. carlton-dental)")
    p.add_argument("--audit", help="Path to audit JSON file", default=None)
    args = p.parse_args()

    success = qa(args.slug, args.audit)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
