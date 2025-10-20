"""
FastPgCache Client - Main interface for PostgreSQL caching
"""
import psycopg2
from psycopg2 import pool
from typing import Optional, Union
import json
from contextlib import contextmanager
import threading


class FastPgCache:
    """
    A Redis-like caching interface using PostgreSQL with UNLOGGED tables.
    
    Features:
    - Fast UNLOGGED table storage
    - TTL support for automatic expiry
    - Redis-like API (set, get, delete, exists, ttl)
    - JSON serialization support
    - Connection pooling
    
    Example:
        >>> cache = FastPgCache("postgresql://user:pass@localhost/mydb")
        >>> cache.setup()  # Initialize cache tables and functions
        >>> cache.set("user:123", {"name": "Alice"}, ttl=3600)
        >>> cache.get("user:123")
        {'name': 'Alice'}
    """
 
    def __init__(
        self,
        connection_string: str = None,
        host: str = "localhost",
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: str = "",
        token_provider = None,
        schema: str = "public",
        minconn: int = 1,
        maxconn: int = 10
    ):
        """
        Initialize FastPgCache connection.
        
        Like Redis, the cache table should already be set up by admin/DBA.
        Users just connect and use it - no setup needed!
        
        Each user automatically gets isolated cache via row-level filtering (user_id column).
        All users share the same table, but can only see their own data.
        
        Args:
            connection_string: PostgreSQL connection string (e.g., "postgresql://user:pass@host/db")
                              If provided, overrides other connection parameters.
            host: Database host (default: localhost)
            port: Database port (default: 5432)
            database: Database name (default: postgres)
            user: Database user - used for cache isolation (default: postgres)
            password: Database password (ignored if token_provider is set)
            token_provider: TokenProvider instance for automatic credential rotation
            schema: PostgreSQL schema name for cache table (default: public)
            minconn: Minimum connections in pool (default: 1)
            maxconn: Maximum connections in pool (default: 10)
            
        Note:
            The cache table must be set up once by admin/DBA using setup().
            Like Redis, users don't run setup - they just connect and use!
        """
        self.connection_string = connection_string
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.token_provider = token_provider
        self.schema = schema
        
        # Row-level isolation: same table, filtered by user_id
        self.table_name = "cache"
        self.user_id = user  # Each user only sees their own rows
        
        self.minconn = minconn
        self.maxconn = maxconn
        self._pool_lock = threading.Lock()
        
        # Initialize connection pool
        self._create_connection_pool()
    
            
    
    def _create_connection_pool(self):
        """Create or recreate the connection pool."""
        # Get password from token provider if available
        effective_password = self.password
        if self.token_provider:
            effective_password = self.token_provider.get_token()
        
        if self.connection_string:
            self.connection_pool = pool.ThreadedConnectionPool(
                self.minconn, self.maxconn, self.connection_string
            )
        else:
            self.connection_pool = pool.ThreadedConnectionPool(
                self.minconn, self.maxconn,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=effective_password
            )
    
    def _refresh_connection_pool(self):
        """Refresh the connection pool with a new token."""
        with self._pool_lock:
            # Close existing connections
            if hasattr(self, 'connection_pool'):
                try:
                    self.connection_pool.closeall()
                except:
                    pass
            
            # Create new pool with refreshed token
            self._create_connection_pool()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for getting and releasing connections from pool."""
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                conn = self.connection_pool.getconn()
                try:
                    yield conn
                    return
                finally:
                    self.connection_pool.putconn(conn)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_error = e
                # If we have a token provider and this isn't the last attempt, refresh and retry
                if self.token_provider and attempt < max_retries - 1:
                    self.token_provider.refresh_token()
                    self._refresh_connection_pool()
                else:
                    raise
        
        # If we get here, all retries failed
        if last_error:
            raise last_error
    
    def set(
        self,
        key: str,
        value: Union[str, dict, list],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a cache value with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON-encoded if dict/list)
            ttl: Time to live in seconds (None = no expiry)
        
        Returns:
            True if successful
        
        Example:
            >>> cache.set("user:123", {"name": "Alice"}, ttl=3600)
            >>> cache.set("config", {"theme": "dark"})  # No expiry
        """
        # Auto-serialize dicts and lists to JSON
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT {self.schema}.cache_set(%s, %s, %s, %s)",
                    (self.user_id, key, value, ttl)
                )
                result = cursor.fetchone()[0]
                conn.commit()
                return result
    
    def get(
        self,
        key: str,
        parse_json: bool = True
    ) -> Optional[Union[str, dict, list]]:
        """
        Get a cache value.
        
        Args:
            key: Cache key
            parse_json: Attempt to parse value as JSON (default: True)
        
        Returns:
            Cached value or None if not found/expired
        
        Example:
            >>> cache.get("user:123")
            {'name': 'Alice'}
            >>> cache.get("user:123", parse_json=False)
            '{"name": "Alice"}'
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {self.schema}.cache_get(%s, %s)", (self.user_id, key))
                result = cursor.fetchone()
                
                if result is None or result[0] is None:
                    return None
                
                value = result[0]
                
                # Try to parse as JSON if requested
                if parse_json:
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        return value
                
                return value
    
    def delete(self, key: str) -> bool:
        """
        Delete a cache entry.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted, False if not found
        
        Example:
            >>> cache.delete("user:123")
            True
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {self.schema}.cache_delete(%s, %s)", (self.user_id, key))
                result = cursor.fetchone()[0]
                conn.commit()
                return result
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists and is not expired.
        
        Args:
            key: Cache key
        
        Returns:
            True if exists, False otherwise
        
        Example:
            >>> cache.exists("user:123")
            True
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {self.schema}.cache_exists(%s, %s)", (self.user_id, key))
                result = cursor.fetchone()[0]
                return result
    
    def ttl(self, key: str) -> int:
        """
        Get time to live for a key.
        
        Args:
            key: Cache key
        
        Returns:
            Seconds until expiry, -1 if no expiry, -2 if not found
        
        Example:
            >>> cache.ttl("user:123")
            3599
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {self.schema}.cache_ttl(%s, %s)", (self.user_id, key))
                result = cursor.fetchone()[0]
                return result
    
    def cleanup(self) -> int:
        """
        Remove all expired cache entries.
        
        Returns:
            Number of entries deleted
        
        Example:
            >>> cache.cleanup()
            5
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {self.schema}.cache_cleanup()")
                result = cursor.fetchone()[0]
                conn.commit()
                return result
    
    def close(self):
        """Close all connections in the pool and stop token provider if active."""
        self.connection_pool.closeall()
        if self.token_provider and hasattr(self.token_provider, 'stop'):
            self.token_provider.stop()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

