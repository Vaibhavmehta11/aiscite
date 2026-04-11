#!/usr/bin/env python3
"""
Batch Google Places API verifier for Aiscite leads.
Validates rating, review count, and place_id for each lead in LEADS_TRACKER.json.

Usage:
    python3 verify_google_places.py [--input LEADS_TRACKER.json] [--output verified_leads.json]

Requires:
    - GOOGLE_PLACES_API_KEY environment variable
    - Leads with 'domain' and 'city' fields
"""
import json
import os
import sys
import time
import argparse
from pathlib import Path
from urllib.parse import quote
import requests

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
if not GOOGLE_PLACES_API_KEY:
    print("ERROR: GOOGLE_PLACES_API_KEY environment variable not set")
    print("Get it from: https://console.cloud.google.com/apis/credentials")
    sys.exit(1)

PLACES_API_URL = "https://places.googleapis.com/places/v1/places:searchText"

HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
    "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.placeId,places.formattedAddress"
}


def search_place(business_name: str, city: str) -> dict | None:
    """Search for a business using Google Places API."""
    query = f"{business_name} {city}"
    payload = {
        "textQuery": query,
        "maxResultCount": 3
    }
    
    try:
        response = requests.post(PLACES_API_URL, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("places"):
            return None
        
        # Return the first result (most relevant)
        place = data["places"][0]
        return {
            "name": place.get("displayName", {}).get("text", ""),
            "rating": place.get("rating"),
            "reviews": place.get("userRatingCount", 0),
            "place_id": place.get("placeId", ""),
            "address": place.get("formattedAddress", ""),
            "confidence": "high" if len(data["places"]) == 1 else "medium"
        }
    except requests.exceptions.RequestException as e:
        print(f"API error: {e}")
        return None


def verify_lead(lead: dict, verbose: bool = True) -> dict:
    """Verify a single lead's Google Places data."""
    name = lead.get("name", "")
    city = lead.get("city", "")
    
    if verbose:
        print(f"Verifying: {name} in {city}...")
    
    result = search_place(name, city)
    
    if result:
        if verbose:
            print(f"  ✓ Found: {result['rating']}★ ({result['reviews']} reviews)")
        
        # Check for significant discrepancies
        existing_reviews = lead.get("reviews", 0)
        if existing_reviews and abs(result["reviews"] - existing_reviews) > 5:
            print(f"  ⚠ WARNING: Review count mismatch! API says {result['reviews']}, tracker says {existing_reviews}")
        
        return {
            **lead,
            "google_verified": True,
            "google_rating": result["rating"],
            "google_reviews": result["reviews"],
            "google_place_id": result["place_id"],
            "google_address": result["address"],
            "verification_confidence": result["confidence"]
        }
    else:
        if verbose:
            print(f"  ✗ Not found in Google Places")
        return {
            **lead,
            "google_verified": False,
            "google_rating": None,
            "google_reviews": None,
            "google_place_id": None,
            "verification_confidence": "failed"
        }


def main():
    parser = argparse.ArgumentParser(description="Batch verify leads via Google Places API")
    parser.add_argument("--input", default="LEADS_TRACKER.json", help="Input JSON file")
    parser.add_argument("--output", default="verified_leads.json", help="Output JSON file")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    # Load leads
    with open(input_path) as f:
        data = json.load(f)
    
    leads = data.get("leads", [])
    if not leads:
        print("ERROR: No leads found in input file")
        sys.exit(1)
    
    print(f"Loaded {len(leads)} leads from {input_path}")
    print(f"Google Places API quota: 200 requests/month (free tier)")
    print(f"This run will consume {len(leads)} requests")
    print("-" * 60)
    
    # Verify each lead
    verified_leads = []
    for i, lead in enumerate(leads, 1):
        if not args.quiet:
            print(f"\n[{i}/{len(leads)}]", end=" ")
        
        verified = verify_lead(lead, verbose=not args.quiet)
        verified_leads.append(verified)
        
        # Rate limiting: 1 request per second to be safe
        if i < len(leads):
            time.sleep(1.0)
    
    # Save results
    output_data = {
        "pipeline": data.get("pipeline", "aiscite-outreach"),
        "verified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "api_quota_used": len(leads),
        "leads": verified_leads
    }
    
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"Verification complete!")
    print(f"Output: {output_path}")
    print(f"Verified: {sum(1 for l in verified_leads if l.get('google_verified'))}/{len(verified_leads)}")
    
    # Summary
    print("\nSummary:")
    for lead in verified_leads:
        status = "✓" if lead.get("google_verified") else "✗"
        reviews = lead.get("google_reviews", "N/A")
        rating = lead.get("google_rating", "N/A")
        print(f"  {status} {lead['name']}: {rating}★ ({reviews} reviews)")


if __name__ == "__main__":
    main()
