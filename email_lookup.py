#!/usr/bin/env python3
"""Email lookup helper for blocked leads.

Searches contact pages via Brave Search API.
"""
import os, json, sys, re
import requests

BRAVE_API_KEY=os.environ.get("BRAVE_SEARCH_API_KEY", "")

LEADS = [
    ("L007", "Dentons", "dentons.ca", "Toronto", "law firm"),
    ("L008", "Kormans LLP", "kormans.ca", "Toronto", "law firm"),
    ("L009", "Westgate Law", "westgatelaw.com", "Toronto", "law firm"),
]

HEADERS = {"User-Agent": "Aiscite-Bot/1.0"}

def search_brave(query):
    if not BRAVE_API_KEY:
        print("BRAVE_API_KEY not set")
        return []
    try:
        r = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": 5},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("web", {}).get("results", [])
        return [
            f"  {i+1}. {res.get('title', 'N/A')}: {res.get('url', 'N/A')}"
            for i, res in enumerate(results)
        ]
    except Exception as e:
        print(f"Brave error: {e}")
        return []

def fetch_contact_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        text = resp.text
        emails = re.findall(r'[\w.]+@[\w.-]+\.\w+', text)
        return emails
    except Exception:
        return []

def main():
    print("Email Lookup for Blocked Leads")
    print("=" * 40)

    for lead_id, name, domain, city, vertical in LEADS:
        print()
        print(f"[{lead_id}] {name} ({domain})")

        queries = [f"contact {name} {city}", f"email {domain}"]
        for q in queries:
            print()
            print(f"  Search: {q}")
            results = search_brave(q)
            for r in results[:3]:
                print(r)

        base = f"https://{domain.replace('www.', '')}"
        for path in ["/contact", "/contact-us"]:
            url = base + path
            print()
            print(f"  Checking: {url}")
            emails = fetch_contact_page(url)
            if emails:
                print(f"  FOUND: {', '.join(emails[:3])}")

if __name__ == "__main__":
    main()
