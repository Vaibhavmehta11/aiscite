#!/usr/bin/env python3
"""
vm_profile.py — VM profile constants for job matching.
Based on /home/nikunj19/optimus/ceo_linkedin_about_ipl.md
"""
VM_PROFILE = {
    "current_role": "Co-CEO, St Kitts & Nevis Patriots (CPL)",
    "track_record": "2x CPL Champion, $150M+ commercial deals, 12+ yrs T20 franchise ops",
    "expertise": [
        "P&L ownership",
        "Player auction strategy",
        "Salary cap management",
        "Commercial partnerships (sponsors, broadcast, licensing)",
        "Fan engagement",
        "Stadium ops"
    ],
    "geography": ["India", "UAE", "Caribbean", "North America"],
    "target_roles": ["CEO", "COO", "CMO"],
    "target_locations": ["USA", "Canada", "India", "UAE", "Saudi Arabia", "UK"],
    "target_industries": ["Sports", "Entertainment", "Media", "Commercial", "Business Development"],
    "profile_strength": "Championship-proven franchise operator, commercial revenue builder"
}

def get_profile():
    return VM_PROFILE

if __name__ == "__main__":
    import json
    print(json.dumps(VM_PROFILE, indent=2))
