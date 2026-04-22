#!/usr/bin/env python3
"""
Aiscite Operations CLI - Wrapper for aiscite_ops.py
Uses project-local configuration for LEADS_TRACKER.json
"""
import sys
from pathlib import Path

# Ensure we're in the aiscite project directory
aiscite_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(aiscite_dir))

# Map project paths to optimus paths for backward compatibility
import os
os.environ['AISCITE_PROJECT_ROOT'] = str(aiscite_dir)

# Import and run the optimus version
from aiscite_ops import main as aiscite_main

sys.exit(aiscite_main(sys.argv))
