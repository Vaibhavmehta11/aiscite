#!/usr/bin/env python3
"""Audit a single business for AI visibility weakness.

Scores 0-100. Lower = better target (more gaps = more value to offer).
Writes audit_<slug>.json.

Checks:
1. AI readability - does the site structure help AI parse it?
2. Citation signals - structured data, schema.org, OG tags
3. Authority & trust - backlinks, domain age, HTTPS
4. Content depth - pages, blog, FAQs, service detail
5. Positioning clarity - unique value prop, local signals
"""
import argparse, json, os, sys, time
from urllib.parse import urlparse
import requests

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}
BRAVE_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")

def slugify(name):
    return name.lower().replace(" ", "-").replace("&", "").replace("'", "").replace(".", "").replace(",", "").replace(" llp", "").replace(" llc", "")

def fetch_page(url, timeout=10):
    """Fetch a URL, return text or empty string."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  WARN: fetch failed for {url}: {e}", file=sys.stderr)
        return ""

def score_ai_readability(html):
    """0-20: Does the site have semantic HTML, headings, structured content?"""
    if not html:
        return 0
    score = 0
    # Has proper heading structure
    if "<h1" in html.lower():
        score += 3
    if "<h2" in html.lower():
        score += 2
    # Has meta description
    if 'meta name="description"' in html.lower():
        score += 2
    # Has structured headings for services
    h_count = html.lower().count("<h2") + html.lower().count("<h3")
    score += min(5, h_count)
    # Has lists (services, features)
    score += min(3, html.lower().count("<li"))
    # Has paragraphs with actual content
    p_count = html.lower().count("<p")
    score += min(5, p_count // 2)
    return min(20, score)

def score_citation_signals(html, url):
    """0-20: Schema.org, OG tags, local business markup."""
    if not html:
        return 0
    score = 0
    html_low = html.lower()
    # Schema.org / JSON-LD
    if "application/ld+json" in html_low:
        score += 5
        # Check for LocalBusiness or specific schema
        if "localbusiness" in html_low or "dentist" in html_low or "medicalbusiness" in html_low or "legalservice" in html_low or "accountingservice" in html_low:
            score += 3
    # OG tags
    if "og:title" in html_low:
        score += 2
    if "og:description" in html_low:
        score += 1
    if "og:image" in html_low:
        score += 1
    # Canonical
    if 'rel="canonical"' in html_low:
        score += 1
    # NAP info (Name, Address, Phone) structured
    import re
    phone = re.search(r'\(\d{3}\)\s*\d{3}-\d{4}|\+\d{1,2}\s*\d{3}[\s.-]\d{3}[\s.-]\d{4}', html)
    if phone:
        score += 2
    # Address pattern
    addr = re.search(r'\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr)', html)
    if addr:
        score += 2
    # hreflang or multilingual
    if "hreflang" in html_low:
        score += 1
    return min(20, score)

def score_authority_trust(domain):
    """0-20: HTTPS, domain signals from search results."""
    score = 0
    # HTTPS
    try:
        r = requests.head(f"https://{domain}", headers=HEADERS, timeout=5, allow_redirects=True)
        if r.status_code < 400:
            score += 5
    except:
        pass
    # Check if site has privacy/terms
    for path in ["/privacy", "/privacy-policy", "/terms"]:
        try:
            r = requests.head(f"https://{domain}{path}", headers=HEADERS, timeout=5, allow_redirects=True)
            if r.status_code < 400:
                score += 2
                break
        except:
            pass
    # Check search result presence (Brave)
    if BRAVE_API_KEY:
        try:
            headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY}
            params = {"q": f'"{domain}"', "count": 5}
            r = requests.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params, timeout=10)
            data = r.json()
            results = data.get("web", {}).get("results", [])
            if len(results) >= 3:
                score += 5
            elif len(results) >= 1:
                score += 2
        except:
            pass
    else:
        score += 3  # Default if no API key
    return min(20, score)

def score_content_depth(html):
    """0-20: Blog, FAQs, service pages, content volume."""
    if not html:
        return 0
    score = 0
    html_low = html.lower()
    # Internal links suggest multiple pages
    import re
    links = re.findall(r'href=["\'](/[^"\']+)["\']', html)
    unique_paths = set(l.split("?")[0].split("#")[0] for l in links)
    score += min(5, len(unique_paths) // 3)
    # Blog
    if "blog" in html_low or "/blog" in html_low:
        score += 3
    # FAQ
    if "faq" in html_low or "frequently asked" in html_low:
        score += 3
    # Services detail
    if "services" in html_low or "our-services" in html_low:
        score += 2
    # Testimonials/reviews
    if "testimonial" in html_low or "review" in html_low:
        score += 2
    # About page link
    if "/about" in html_low:
        score += 2
    # Content length
    text_len = len(re.sub(r'<[^>]+>', '', html).strip())
    if text_len > 5000:
        score += 3
    elif text_len > 2000:
        score += 1
    return min(20, score)

def score_positioning_clarity(html, name, biz_type, city):
    """0-20: Clear value prop, local signals, differentiation."""
    if not html:
        return 0
    score = 0
    html_low = html.lower()
    # Business name in title/h1
    import re
    title = re.search(r'<title[^>]*>(.*?)</title>', html_low, re.DOTALL)
    if title and name.lower() in title.group(1):
        score += 3
    # City/location mentioned
    if city.lower() in html_low:
        score += 3
    # Biz type keywords
    type_words = biz_type.lower().split()
    for w in type_words:
        if w in html_low:
            score += 1
            break
    # Unique value proposition signals
    uvp_words = ["award", "certified", "specialist", "expert", "leading", "trusted", "premier",
                  "top-rated", "best", "exclusive", "unique", "proven", "guaranteed"]
    for w in uvp_words:
        if w in html_low:
            score += 1
            break
    # Clear CTA
    cta_words = ["book", "schedule", "call", "contact", "appointment", "consultation", "get started"]
    for w in cta_words:
        if w in html_low:
            score += 2
            break
    # Multiple locations or service areas
    if "locations" in html_low or "service area" in html_low or "serving" in html_low:
        score += 2
    # Professional design indicators
    if "font-awesome" in html_low or "fontawesome" in html_low or "cdn.jsdelivr.net" in html_low:
        score += 2
    return min(20, score)

def audit(name, url, city, biz_type):
    """Run full audit. Returns dict with scores."""
    domain = url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0].lower()
    if not url.startswith("http"):
        url = f"https://{domain}"

    print(f"Auditing: {name} ({domain})...")
    html = fetch_page(url)

    ai_readability = score_ai_readability(html)
    citation_signals = score_citation_signals(html, url)
    authority_trust = score_authority_trust(domain)
    content_depth = score_content_depth(html)
    positioning_clarity = score_positioning_clarity(html, name, biz_type, city)

    overall = ai_readability + citation_signals + authority_trust + content_depth + positioning_clarity

    result = {
        "business_name": name,
        "domain": domain,
        "city": city,
        "biz_type": biz_type,
        "url": url,
        "overall_score": overall,
        "ai_readability": ai_readability,
        "citation_signals": citation_signals,
        "authority_trust": authority_trust,
        "content_depth": content_depth,
        "positioning_clarity": positioning_clarity,
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    slug = slugify(name)
    outfile = f"audit_{slug}.json"
    with open(outfile, "w") as f:
        json.dump(result, f, indent=2)

    print(f"  Score: {overall}/100 -> {outfile}")
    return result

def main():
    p = argparse.ArgumentParser(description="Audit a business for AI visibility")
    p.add_argument("--name", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--city", required=True)
    p.add_argument("--type", required=True)
    args = p.parse_args()

    result = audit(args.name, args.url, args.city, args.type)
    if result["overall_score"] <= 65:
        print(f"  PASS: Score {result['overall_score']} <= 65, good target for outreach")
    else:
        print(f"  SKIP: Score {result['overall_score']} > 65, not enough visible gaps")

if __name__ == "__main__":
    main()
