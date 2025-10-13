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
        minconn: int = 1,
        maxconn: int = 10,
        auto_setup: bool = False
    ):
        """
        Initialize FastPgCache connection.
        
        Args:
            connection_string: PostgreSQL connection string (e.g., "postgresql://user:pass@host/db")
                              If provided, overrides other connection parameters.
            host: Database host (default: localhost)
            port: Database port (default: 5432)
            database: Database name (default: postgres)
            user: Database user (default: postgres)
            password: Database password (ignored if token_provider is set)
            token_provider: TokenProvider instance for automatic credential rotation
            minconn: Minimum connections in pool (default: 1)
            maxconn: Maximum connections in pool (default: 10)
            auto_setup: Automatically run setup() on initialization (default: False)
        """
        self.connection_string = connection_string
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.token_provider = token_provider
        self.minconn = minconn
        self.maxconn = maxconn
        self._pool_lock = threading.Lock()
        
        # Initialize connection pool
        self._create_connection_pool()
        
        if auto_setup:
            self.setup()
    
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
    
    def setup(self) -> bool:
        """
        Initialize the cache system by creating tables and functions.
        Should be run once before using the cache.
        
        Returns:
            True if setup was successful
        """
        setup_sql = """
-- Drop existing objects if they exist
DROP TABLE IF EXISTS cache CASCADE;
DROP FUNCTION IF EXISTS cache_set(TEXT, TEXT, INTEGER);
DROP FUNCTION IF EXISTS cache_get(TEXT);
DROP FUNCTION IF EXISTS cache_delete(TEXT);
DROP FUNCTION IF EXISTS cache_exists(TEXT);
DROP FUNCTION IF EXISTS cache_cleanup();
DROP FUNCTION IF EXISTS cache_ttl(TEXT);

-- Create UNLOGGED table for caching
CREATE UNLOGGED TABLE cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for expiry cleanup
CREATE INDEX idx_cache_expires_at ON cache(expires_at) 
WHERE expires_at IS NOT NULL;

-- Function: SET a cache value with optional TTL
CREATE OR REPLACE FUNCTION cache_set(
    p_key TEXT,
    p_value TEXT,
    p_ttl_seconds INTEGER DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    IF p_ttl_seconds IS NOT NULL THEN
        v_expires_at := NOW() + (p_ttl_seconds || ' seconds')::INTERVAL;
    ELSE
        v_expires_at := NULL;
    END IF;
    
    INSERT INTO cache (key, value, expires_at, created_at, accessed_at)
    VALUES (p_key, p_value, v_expires_at, NOW(), NOW())
    ON CONFLICT (key) 
    DO UPDATE SET
        value = EXCLUDED.value,
        expires_at = EXCLUDED.expires_at,
        accessed_at = NOW();
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function: GET a cache value
CREATE OR REPLACE FUNCTION cache_get(p_key TEXT)
RETURNS TEXT AS $$
DECLARE
    v_value TEXT;
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT value, expires_at 
    INTO v_value, v_expires_at
    FROM cache
    WHERE key = p_key;
    
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    
    IF v_expires_at IS NOT NULL AND v_expires_at < NOW() THEN
        DELETE FROM cache WHERE key = p_key;
        RETURN NULL;
    END IF;
    
    UPDATE cache SET accessed_at = NOW() WHERE key = p_key;
    
    RETURN v_value;
END;
$$ LANGUAGE plpgsql;

-- Function: DELETE a cache entry
CREATE OR REPLACE FUNCTION cache_delete(p_key TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM cache WHERE key = p_key;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted > 0;
END;
$$ LANGUAGE plpgsql;

-- Function: CHECK if a key exists
CREATE OR REPLACE FUNCTION cache_exists(p_key TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM cache
    WHERE key = p_key;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    IF v_expires_at IS NOT NULL AND v_expires_at < NOW() THEN
        DELETE FROM cache WHERE key = p_key;
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function: GET TTL
CREATE OR REPLACE FUNCTION cache_ttl(p_key TEXT)
RETURNS INTEGER AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
    v_ttl_seconds INTEGER;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM cache
    WHERE key = p_key;
    
    IF NOT FOUND THEN
        RETURN -2;
    END IF;
    
    IF v_expires_at IS NULL THEN
        RETURN -1;
    END IF;
    
    v_ttl_seconds := EXTRACT(EPOCH FROM (v_expires_at - NOW()))::INTEGER;
    
    IF v_ttl_seconds <= 0 THEN
        DELETE FROM cache WHERE key = p_key;
        RETURN -2;
    END IF;
    
    RETURN v_ttl_seconds;
END;
$$ LANGUAGE plpgsql;

-- Function: CLEANUP expired entries
CREATE OR REPLACE FUNCTION cache_cleanup()
RETURNS INTEGER AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM cache 
    WHERE expires_at IS NOT NULL 
    AND expires_at < NOW();
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

-- Create view for valid cache entries
CREATE OR REPLACE VIEW valid_cache AS
SELECT 
    key,
    value,
    expires_at,
    created_at,
    accessed_at,
    CASE 
        WHEN expires_at IS NULL THEN -1
        ELSE EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER
    END as ttl_seconds
FROM cache
WHERE expires_at IS NULL OR expires_at > NOW();
"""
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(setup_sql)
                conn.commit()
        
        return True
    
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
                    "SELECT cache_set(%s, %s, %s)",
                    (key, value, ttl)
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
                cursor.execute("SELECT cache_get(%s)", (key,))
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
                cursor.execute("SELECT cache_delete(%s)", (key,))
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
                cursor.execute("SELECT cache_exists(%s)", (key,))
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
                cursor.execute("SELECT cache_ttl(%s)", (key,))
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
                cursor.execute("SELECT cache_cleanup()")
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

