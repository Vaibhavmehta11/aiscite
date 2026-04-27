#!/usr/bin/env python3
"""Test email validation logic."""
import sys
sys.path.insert(0, '/home/nikunj19/Projects/aiscite')

from outreach import validate_email

# Test cases
tests = [
    ('info@kormans.ca', 'kormans.ca', 'law_firm', False),  # Role email at law firm
    ('john.doe@kormans.ca', 'kormans.ca', 'law_firm', True),  # Personal email at law firm
    ('info@medspa.com', 'medspa.com', 'med_spa', True),  # Role email OK for small biz
    ('test@yelp.com', 'yelp.com', 'aggregator', False),  # Aggregator domain
    ('demo@example.com', 'example.com', 'test', False),  # Disposable pattern
    ('partner@gmail.com', 'gmail.com', 'consulting', True),  # Valid personal
]

print("Email Validation Tests")
print("=" * 60)
all_pass = True
for email, domain, biz_type, expected in tests:
    result, reason = validate_email(email, domain, biz_type)
    status = 'PASS' if result == expected else 'FAIL'
    if result != expected:
        all_pass = False
    print(f'{status}: {email} -> {result} ({reason}) [expected {expected}]')

print("=" * 60)
print(f"Result: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
sys.exit(0 if all_pass else 1)
