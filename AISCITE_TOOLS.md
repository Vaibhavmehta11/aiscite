# Aiscite Tools Reference

Directory: `/home/nikunj19/Projects/aiscite/`
Last updated: 2026-04-14

---

## Scripts

| File | Description |
|---|---|
| `scout.py` | Find local business prospects by city + type using Brave Search. Writes `targets_YYYY-MM-DD.csv`. Args: `--city --type --count` |
| `audit.py` | Score a single business on AI visibility weakness (0-100, lower = better target). Args: `--name --url --city --type`. Writes `audit_<slug>.json` |
| `generate_report.py` | Build personalised HTML report from audit JSON and push to GitHub Pages. Reads `audit/carlton-dental/index.html` as template. Pushes to `https://aiscite.com/audit/<slug>/` |
| `qa_report.py` | 24-point QA check on a deployed report. Fetches live HTML from aiscite.com. Exit 0 = PASS. Args: `<slug> [--audit <file>]` |
| `verify_google_places.py` | Batch Google Places API verifier for Aiscite leads. Validates rating, review count, and place_id |
| `run_pipeline.py` | **Single-command orchestrator.** Chains: scout -> audit -> score gate -> generate -> QA. Args: `--city --type --count`. Optional: `--wave <id>` to resume. Exit 0 = complete. |
| `outreach.py` | Email outreach script for sending AI visibility reports |
| `send_outreach.py` | Wrapper script for gog email send integration |

---

## Project Workspace (Lead Tracking - Local to Project)

| File | Purpose |
|---|---|
| `LEADS_TRACKER.json` | Lead pipeline tracker with stages (now local to project) |
| `OUTREACH_LOG.md` | Outreach send history |
| `APPROVAL_QUEUE.md` | Items needing Board approval |
| `aiscite_cli.py` | CLI for lead management (add_lead, stage, queue_approval, log_outreach) |
| `/home/nikunj19/optimus/runtime/aiscite_ops.py` | Core operations module (shared across domains) |

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `BRAVE_SEARCH_API_KEY` | Required for scout.py and audit.py authority scoring |
| `GITHUB_TOKEN` | Auto-configured in git repo for push |
| `GOG_KEYRING_PASSWORD` | Required for email send via gog CLI |
| `GOOGLE_PLACES_API_KEY` | Required for verify_google_places.py |

---

## Quick Start

```bash
cd /home/nikunj19/Projects/aiscite

# Full automated wave (scout -> audit -> gate -> generate -> QA)
python3 run_pipeline.py wave --city "Toronto" --type "med spa" --count 30

# Status of current leads
python3 run_pipeline.py status

# QA check on deployed report
python3 qa_report.py midtown-med-spa

# Email outreach
python3 send_outreach.py

# Lead management via CLI
python3 aiscite_cli.py add_lead path/to/lead.json
python3 aiscite_cli.py stage "midtown-med-spa" "sent"
python3 aiscite_cli.py log_outreach "midtown-med-spa" "vm@aiscite.com" "Email sent - awaiting reply"
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | SUCCESS - Pipeline completed, targets passed gate, QA passed |
| 1 | FAIL - Bridge missing, broken config, auth error, QA failure |
| 2 | NO_TARGETS - All businesses scored > 65, no outreach opportunity |

---

## Rules

- Never skip QA
- Never send generic reports -- always personalised
- Never send to score > 65
- Always send from vm@aiscite.com
- Subject must use biz_type_label not hardcoded "dentist"
- Signature is "Best\nVM" -- no email, no company name

---

## Pitfalls

- Scout skips aggregator/directory domains (yelp, reddit, ratehub, etc.)
- Some sites return 403 to bots -- audit scores will be near 0
- `info@` is acceptable for small firms but must be rejected for large companies
- `generate_report.py` reads `audit/carlton-dental/index.html` as template -- do not edit directly
- run_pipeline.py requires `BRAVE_SEARCH_API_KEY` for authority scoring (optional, defaults to low score)
- GitHub Actions: no symlinks allowed -- LEADS_TRACKER.json must be a regular file copy

---

## GitHub Pages Fix (2026-04-14)

The symlink `LEADS_TRACKER.json -> /home/nikunj19/optimus/domains/aiscite/LEADS_TRACKER.json` is now replaced with a regular file copy. All scripts have been updated to use `/home/nikunj19/Projects/aiscite/LEADS_TRACKER.json`.

To sync:
```bash
cp /home/nikunj19/optimus/domains/aiscite/LEADS_TRACKER.json /home/nikunj19/Projects/aiscite/LEADS_TRACKER.json
```
