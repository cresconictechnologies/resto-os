"""
RestoOS Supabase Integration Client
Provides helper functions for Supabase Auth, Realtime listeners, and Storage buckets
when cloud sync mode is enabled.
"""

import os
from typing import Optional, Dict, Any

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_supabase_client = None


def get_supabase_client():
    """
    Returns an initialized Supabase client if supabase-py is installed
    and credentials are provided. Gracefully returns None in offline LAN mode.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    try:
        from supabase import create_client, Client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _supabase_client
    except ImportError:
        print("[RestoOS] Notice: 'supabase' package not installed. Running in direct database mode.")
        return None
    except Exception as e:
        print(f"[RestoOS] Warning: Could not initialize Supabase client: {e}")
        return None


def get_supabase_config() -> Dict[str, Any]:
    """Exposes public Supabase connection status for admin dashboard and frontend sync."""
    return {
        "enabled": bool(SUPABASE_URL and SUPABASE_KEY),
        "url": SUPABASE_URL if SUPABASE_URL else None,
        "mode": "supabase_cloud" if (SUPABASE_URL and SUPABASE_KEY) else "local_lan_sqlite",
    }
