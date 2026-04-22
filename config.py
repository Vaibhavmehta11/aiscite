#!/usr/bin/env python3
"""
Configuration and path settings for Aiscite pipeline.
Centralized to avoid path duplication and symlink issues.
"""
from pathlib import Path

# Aiscite project root
PROJECT_ROOT = Path("/home/nikunj19/Projects/aiscite")

# Optimus domain root (for shared data)
OPTIMUS_DOMAIN_ROOT = Path("/home/nikunj19/optimus/domains/aiscite")

# Tracker file - now a proper file copy, not symlink
TRACKER_FILE = PROJECT_ROOT / "LEADS_TRACKER.json"

# Outreach log
OUTREACH_LOG = PROJECT_ROOT / "outreach.log"

# Approval queue
APPROVAL_QUEUE = PROJECT_ROOT / "APPROVAL_QUEUE.md"

# Target directories
LEADS_DIR = PROJECT_ROOT / "leads"
AUDIT_DIR = PROJECT_ROOT / "audit"
TARGETS_DIR = PROJECT_ROOT / "targets"

# Default paths for scripts that need to reference the old structure
# These are aliases for backward compatibility
TRACKER_PATH = TRACKER_FILE
OPTIMUS_TRACKER = OPTIMUS_DOMAIN_ROOT / "LEADS_TRACKER.json"

# Domain root for HTML reports (local)
DOMAIN_ROOT = PROJECT_ROOT
