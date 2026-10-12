"""
config.py
=========
Only job: load .env and read environment variables. No network calls,
no Supabase import here -- that's what makes this file safe to import
from anywhere (including tests) without side effects.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# backend/config.py -> parents[1] -> project root, where .env lives
# (same depth as scripts/supabase_insert.py was, one folder below root)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def require_env(name: str) -> str:
    """Read an env var or exit with a clear message if it's missing."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable: {name}")
    return value


# Read once at import time so a missing var fails fast, at startup,
# not on the first request that happens to need it.
SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = require_env("SUPABASE_PUBLISHABLE_KEY")