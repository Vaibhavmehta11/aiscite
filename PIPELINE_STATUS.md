# Aiscite Pipeline Status

Updated: 2026-04-13

## Current State
All critical scripts validated, syntax correct, environment configured. Pipeline ready for execution.

## Verified Scripts

| File | Status | Notes |
|------|--------|-------|
| `scout.py` | OK | Fetches businesses via Brave Search |
| `audit.py` | OK | Scores AI visibility 0-100 |
| `generate_report.py` | OK | Builds HTML report + push |
| `qa_report.py` | OK | 24-point QA check |
| `run_pipeline.py` | OK | Full orchestrator |
| `verify_google_places.py` | OK | Google Places validation |
| `email_lookup.py` | OK | Finds contact emails |
| `outreach.py` | OK | Email send via gog |
| `send_outreach.py` | OK | Wrapper for gog send |
| `reply_monitor.py` | OK | Email tracking |
| `test_pipeline.py` | OK | Pipeline tests |

## Environment

| Variable | Status |
|----------|--------|
| `BRAVE_SEARCH_API_KEY` | Set (BSA89rD6...) |
| `GOG_KEYRING_PASSWORD` | Set (optimus-gog-2026) |
| `GITHUB_TOKEN` | Set (git config) |

## Directory Structure

```
/home/nikunj19/Projects/aiscite/
├── scout.py              # Business discovery
├── audit.py              # Score calculation
├── generate_report.py    # Report generation
├── qa_report.py          # QA checks
├── run_pipeline.py       # Full orchestrator
├── verify_google_places.py
├── email_lookup.py
├── outreach.py
├── send_outreach.py
├── reply_monitor.py
├── test_pipeline.py
├── .env.local            # Local env config
├── audit/                # Report pages (58+)
│   └── *.html
└── audit/<slug>/         # 28 known reports

Domain workspace:
/home/nikunj19/optimus/domains/aiscite/
└── LEADS_TRACKER.json
└── OUTREACH_LOG.md
└── APPROVAL_QUEUE.md

CLI utility:
/home/nikunj19/optimus/runtime/aiscite_ops.py
```

## Commands

### Scout businesses
```bash
cd /home/nikunj19/Projects/aiscite
python3 scout.py --city Toronto --type "med spa" --count 10
```

### Audit single business
```bash
python3 audit.py --name "X" --url "y.com" --city "Toronto" --type "med spa"
```

### Full pipeline (dry-run)
```bash
python3 run_pipeline.py wave --city Toronto --type 'med spa' --count 5 --dry-run
```

### QA report
```bash
python3 qa_report.py <slug> --audit audit_<slug>.json
```

### Generate report
```bash
python3 -c "
from generate_report import generate, push_to_github
import json
with open('audit_<slug>.json') as f:
    audit = json.load(f)
slug, path = generate(audit['business_name'], audit['domain'], audit['city'], audit['biz_type'], audit)
push_to_github(slug)
"
```

## Endpoints

- Reports: `https://aiscite.com/audit/<slug>/`
- Live reports: `carlton-dental`, `kormans-llp`, `premier-med-spa`, `midtown-med-spa`, `north-medical-spa`, `starlight-med-spa`

## Next Steps

1. Run full med spa wave
2. Set up reply monitoring cron
3. Integrate `aiscite_ops.py` into main pipeline
4. Create GitHub Actions workflow for auto-builds

## Known Limitations

- Scout requires `BRAVE_SEARCH_API_KEY` (set in `.env.local`)
- Email send requires `GOG_KEYRING_PASSWORD` (configured)
- Lead tracking via `aiscite_ops.py` not fully integrated
- Some legacy report HTML may have legacy branding (Carlton Dental check)
