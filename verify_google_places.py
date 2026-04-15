#!/usr/bin/env python3
"""
Batch Google Places API verifier for Aiscite leads.
Validates rating, review count, and place_id for each lead in LEADS_TRACKER.json.

Usage:
    python3 verify_google_places.py [--input LEADS_TRACKER.json] [--output verified_leads.json]

Requires:
    - GOOGLE_PLACES_API_KEY environment variable (from Google Cloud Console)
    - Leads with 'name' and 'city' fields

To set the key (one-time setup):
    export GOOGLE_PLACES_API_KEY="AIzaSy...your-key-here"

Or source from your project env file:
    source ~/.hermes/.env  # if GOOGLE_PLACES_API_KEY is defined there

Pre-requisites:
    - Enable Google Places API in Google Cloud Console
    - Create an API key with Places API permission
    - The free tier gives 200 requests/month
"""
import json
import os
import sys
import time
import argparse
from pathlib import Path
import requests

from config import TRACKER_FILE


def get_api_key():
    """Get API key from environment, with helpful error if missing."""
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("=" * 60)
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        print("=" * 60)
        print("Google Places API requires an API key. To set it up:")
        print("")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create a new API key")
        print("3. Enable 'Places API' for your project")
        print("4. Set the environment variable:")
        print("   export GOOGLE_PLACES_API_KEY='AIzaSy...your-key-here'")
        print("")
        print("You can add this to your ~/.bashrc or ~/.profile to persist it.")
        print("=" * 60)
        sys.exit(1)
    
    # Warn if key looks placeholder-ish
    if api_key == "***" or len(api_key) < 39:
        print("WARNING: GOOGLE_PLACES_API_KEY appears to be a placeholder or truncated value")
        print("Ensure you have the full 39+ character key from Google Cloud Console.")
        sys.exit(1)
    
    return api_key


def get_places_session():
    """Initialize and return places API session with verified key."""
    api_key = get_api_key()
    
    return {
        "api_key": api_key,
        "url": "https://places.googleapis.com/v1/places:searchText",
        "headers": {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName.text,places.rating,places.userRatingCount,places.placeId,places.formattedAddress",
        }
    }


def search_place(business_name: str, city: str, session: dict) -> dict | None:
    """Search for a business using Google Places API."""
    url = session["url"]
    headers = session["headers"]
    payload = {
        "textQuery": f"{business_name} {city}",
        "maxResultCount": 3
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("places"):
            return None
        
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


def verify_lead(lead: dict, session: dict, verbose: bool = True) -> dict:
    """Verify a single lead's Google Places data."""
    name = lead.get("name", "")
    city = lead.get("city", "")
    
    if verbose:
        print(f"Verifying: {name} in {city}...")
    
    result = search_place(name, city, session)
    
    if result:
        if verbose:
            print(f"  Found: {result['rating']} star ({result['reviews']} reviews)")
        
        existing_reviews = lead.get("reviews", 0)
        if existing_reviews and abs(result["reviews"] - existing_reviews) > 5:
            print(f"  WARNING: Review count mismatch! API says {result['reviews']}, tracker says {existing_reviews}")
        
        # Calculate unanswered as 60% of total reviews (Google doesn't provide this directly)
        total_reviews = result["reviews"]
        reply_rate = lead.get("reply_rate", 40)  # Default to 40% if not specified
        unanswered = round(total_reviews * (1 - reply_rate / 100)) if total_reviews > 0 else 0
        
        return {
            **lead,
            "google_verified": True,
            "google_rating": result["rating"],
            "google_reviews": total_reviews,
            "google_place_id": result["place_id"],
            "google_address": result["address"],
            "unanswered": unanswered,
            "verification_confidence": result["confidence"]
        }
    else:
        if verbose:
            print(f"  Not found in Google Places")
        
        return {
            **lead,
            "google_verified": False,
            "google_rating": None,
            "google_reviews": 0,
            "google_place_id": None,
            "google_address": None,
            "verification_confidence": "none"
        }


def batch_verify(input_file: str, output_file: str, quiet: bool = False) -> dict:
    """Process all leads in input file and write to output."""
    session = get_places_session()
    
    try:
        with open(input_file, 'r') as f:
            leads = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in input file: {e}")
        sys.exit(1)
    
    # Handle both direct array and object with leads key
    if isinstance(leads, dict):
        leads = leads.get("leads", [])
    
    if not isinstance(leads, list):
        print("ERROR: Input file must contain a JSON array of leads or an object with a 'leads' array")
        sys.exit(1)
    
    verified = []
    for i, lead in enumerate(leads, 1):
        verbose = not quiet
        result = verify_lead(lead, session, verbose=verbose)
        verified.append(result)
        
        if i < len(leads):
            time.sleep(1)  # Rate limit: 1 req/sec
    
    with open(output_file, 'w') as f:
        json.dump(verified, f, indent=2)
    
    if not quiet:
        print(f"Processed {len(verified)} leads. Output saved to {output_file}")
    
    return {"verified": verified, "count": len(verified)}


def main():
    parser = argparse.ArgumentParser(description="Batch verify leads via Google Places API")
    parser.add_argument("--input", default=str(TRACKER_FILE), help="Input JSON file")
    parser.add_argument("--output", default="verified_leads.json", help="Output JSON file")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()
    
    batch_verify(args.input, args.output, args.quiet)


if __name__ == "__main__":
    main()
