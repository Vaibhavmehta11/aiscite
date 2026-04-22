#!/usr/bin/env python3
"""Cancel all remaining postmortem tasks."""
import os, json, urllib.request

API_URL = 'http://127.0.0.1:3100'
COMPANY = '891ba9d1-4a11-4d90-87aa-afba1d7f00db'
KEY = os.environ.get('PAPERCLIP_API_KEY', '')

req = urllib.request.Request(f'{API_URL}/api/companies/{COMPANY}/issues')
req.add_header('Authorization', f'Bearer {KEY}')
with urllib.request.urlopen(req, timeout=10) as resp:
    issues = json.loads(resp.read().decode())

target = [i for i in issues if i.get('title', '').startswith('Postmortem:') and i.get('status') in ('blocked', 'in_progress', 'todo')]
print(f'[ Wheeljack ] Found {len(target)} postmortem tasks to cancel')

for t in target:
    issue_id = t.get('id')
    identifier = t.get('identifier')
    try:
        data = json.dumps({'status': 'cancelled'}).encode()
        req = urllib.request.Request(f'{API_URL}/api/issues/{issue_id}', data=data, method='PATCH')
        req.add_header('Authorization', f'Bearer {KEY}')
        req.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req, timeout=10)
        print(f'[OK] Cancelled: {identifier}')
    except Exception as e:
        print(f'[ERROR] {identifier}: {e}')

print(f'[ Wheeljack ] Done. Cancelled {len(target)} tasks.')
