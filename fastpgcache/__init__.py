"""
FastPgCache - A Redis-like caching library using PostgreSQL
"""

from .client import FastPgCache
from .token_provider import TokenProvider, DatabricksTokenProvider
from .admin import setup_cache

__version__ = "0.1.4"
__all__ = ["FastPgCache", "TokenProvider", "DatabricksTokenProvider", "setup_cache"]

