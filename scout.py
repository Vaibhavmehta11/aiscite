#!/usr/bin/env python3
"""Scout local businesses by city + type using Brave Search API.

Writes targets_<date>.csv with columns: name,domain,city,type
"""
import argparse, csv, json, os, sys, time
from datetime import date
from urllib.parse import quote_plus
import requests

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "") or os.environ.get("BRAVE_SEARCH_API_KEY", "")
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

def slugify(name):
    return name.lower().replace(" ", "-").replace("&", "").replace("'", "").replace(".", "").replace(",", "")

def search_brave(query, count=10, offset=0):
    """Search Brave API. Returns list of result dicts."""
    if not BRAVE_API_KEY:
        print("ERROR: BRAVE_API_KEY or BRAVE_SEARCH_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY}
    params = {"q": query, "count": min(count, 20), "offset": offset}
    r = requests.get(BRAVE_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("web", {}).get("results", [])

def extract_domain(url):
    """Strip protocol and path, return bare domain."""
    return url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0].lower()

def scout(city, biz_type, count=30):
    """Find businesses. Returns list of dicts with name, domain, city, type."""
    query = f'{biz_type} in {city}'
    targets = []
    seen_domains = set()
    offset = 0

    while len(targets) < count:
        batch = min(20, count - len(targets))
        results = search_brave(query, count=batch, offset=offset)
        if not results:
            break
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "").strip()
            if not url or not title:
                continue
            domain = extract_domain(url)
            # Skip directories, aggregators, generic pages
            skip_patterns = ["yelp.", "google.", "facebook.", "instagram.", "linkedin.",
                             "yellowpages.", "tripadvisor.", "gmb.", "maps.google",
                             "foursquare.", "healthgrades.", "zocdoc.", "ratemds.",
                             "threebestrated.", "nearme.", "homestars.", "canadabusiness.",
                             "reddit.", "ratehub.", "thebesttoronto.", "designrush.",
                             "wowa.", "clearlyrated.", "provenexpert.", "g2.", "capterra.",
                             "trustpilot.", "sitejabber.", "angi.", "homeadvisor.",
                             "thumbtack.", "porch.", "bbb.org", "wikidata.", "wikipedia.",
                             "mapquest.", "citysearch.", "superpages.", "hotfrog.",
                             "foursquare.", "manta.", "chamberofcommerce.", "cybo.",
                             "tuugo.", "hotels.", "booking.", "expedia.", "airbnb.",
                             "opentable.", "grubhub.", "ubereats.", "doordash.",
                             "yelp.ca", "yelp.co", "yelp.com"]
            if any(p in domain for p in skip_patterns):
                continue
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            # Clean title - remove common suffixes and pipe/dash separators
            for suffix in [" - Home", " | Home", " - Yelp", " | Facebook", " - Instagram"]:
                title = title.replace(suffix, "")
            # Take only the first segment before pipe or em-dash (Brave often returns "Name | Tagline | Location")
            for sep in [" | ", " – ", " - ", " |", "–"]:
                if sep in title:
                    title = title.split(sep)[0].strip()
                    break
            targets.append({
                "name": title,
                "domain": domain,
                "city": city,
                "type": biz_type,
            })
            if len(targets) >= count:
                break
        offset += batch
        time.sleep(1)  # Rate limit

    return targets

def main():
    p = argparse.ArgumentParser(description="Scout local businesses")
    p.add_argument("--city", required=True)
    p.add_argument("--type", required=True, help="Business type: dentist, lawyer, etc.")
    p.add_argument("--count", type=int, default=30)
    args = p.parse_args()

    targets = scout(args.city, args.type, args.count)
    if not targets:
        print("No targets found.")
        sys.exit(0)

    today = date.today().isoformat()
    outfile = f"targets_{today}.csv"
    with open(outfile, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "domain", "city", "type"])
        w.writeheader()
        w.writerows(targets)

    print(f"Found {len(targets)} targets -> {outfile}")
    for t in targets:
        print(f"  {t['name']}  ({t['domain']})")

if __name__ == "__main__":
    main()
