"""
db.py
=====
Hands back ONE shared Supabase client. @lru_cache means create_client()
only actually runs once -- the first call -- and every call after that
just returns the same remembered object instead of rebuilding it.

Uses the PUBLISHABLE key on purpose, not the secret key: every table
this API reads from has a "public read" RLS policy (see the schema),
so a read-only key is all it ever needs. See the design doc, Section 4,
for the full reasoning.
"""

from functools import lru_cache

from supabase import Client, create_client

from .config import SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL


@lru_cache
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)