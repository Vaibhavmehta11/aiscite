#!/usr/bin/env python3
"""Scout local businesses by city + type using Brave Search API.

Writes targets_<date>.csv with columns: name,domain,city,type
"""
import argparse, csv, json, os, sys, time
from datetime import date
from urllib.parse import quote_plus
import requests

BRAVE_API_KEY=os.environ.get("BRAVE_SEARCH_API_KEY", "")
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

def slugify(name):
    return name.lower().replace(" ", "-").replace("&", "").replace("'", "").replace(".", "").replace(",", "")

def search_brave(query, count=10, offset=0, api_key=None):
    """Search Brave API. Returns list of result dicts."""
    if not api_key and not BRAVE_API_KEY:
        print("ERROR: BRAVE_API_KEY (BRAVE_SEARCH_API_KEY) not set", file=sys.stderr)
        sys.exit(1)
    key = api_key or BRAVE_API_KEY
    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    params = {"q": query, "count": min(count, 20), "offset": offset}
    r = requests.get(BRAVE_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("web", {}).get("results", [])

def extract_domain(url):
    """Strip protocol and path, return bare domain."""
    url = url.replace("https://", "").replace("http://", "")
    return url.split("/")[0].split(":")[0].lower()

def scout(city, biz_type, count=30, api_key=None):
    """Find businesses by city + type, return list of (name, url, city, biz_type)."""
    query = f"best {biz_type} in {city} -medical -spa"
    if biz_type == "law firm":
        query = f"top law firm in {city} -divorce -criminal -paralegal"
    results = search_brave(query, count=count, api_key=api_key)
    
    businesses = []
    for r in results:
        name = r.get("title", "").replace(f" - {city}", "").replace(f"- {city}", "")
        url = r.get("url", "")
        if name and url:
            businesses.append((name, url, city, biz_type))
    
    return businesses

def main():
    p = argparse.ArgumentParser(description="Scout local businesses")
    p.add_argument("--city", required=True)
    p.add_argument("--type", required=True, dest="biz_type")
    p.add_argument("--count", default=30, type=int)
    p.add_argument("--api-key", default=None, help="Brave Search API key (overrides BRAVE_API_KEY env)")
    args = p.parse_args()
    
    businesses = scout(args.city, args.biz_type, args.count, args.api_key)
    print(f"Found {len(businesses)} businesses")
    
    # Write to CSV
    filename = f"targets_{date.today().strftime('%Y-%m-%d')}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "domain", "city", "biz_type"])
        for name, url, city, biz_type in businesses:
            writer.writerow([name, extract_domain(url), city, biz_type])
    
    print(f"Written to {filename}")
