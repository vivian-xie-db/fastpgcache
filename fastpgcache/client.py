"""
FastPgCache Client - Main interface for PostgreSQL caching
"""
import psycopg2
from psycopg2 import pool, sql
from typing import Optional, Union
import json
from contextlib import contextmanager
import threading
from .cuckoo_filter import CuckooFilter

class FastPgCache:
    """
    A Redis-like caching interface using PostgreSQL with UNLOGGED tables.
    
    Features:
    - Fast UNLOGGED table storage
    - TTL support for automatic expiry
    - Redis-like API (set, get, delete, exists, ttl)
    - JSON serialization support
    - Connection pooling
    
    """
 
    def __init__(
        self,
        connection_string: str = None,
        host: str = "localhost",
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: str = "",
        schema: str = "public",
        minconn: int = 1,
        maxconn: int = 10,
        use_cuckoo_filter: bool = True,
        cuckoo_capacity: int = 1000000,
        instance_name: str = None,
        profile: str = None
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
            password: Database password (ignored if instance_name is set)
            schema: PostgreSQL schema name for cache table (default: public)
            minconn: Minimum connections in pool (default: 1)
            maxconn: Maximum connections in pool (default: 10)
            use_cuckoo_filter: Enable CuckooFilter for fast negative lookups (default: True)
            cuckoo_capacity: CuckooFilter capacity if enabled (default: 1,000,000)
            
            instance_name: Databricks PostgreSQL instance name (enables Databricks mode)
                                If provided, auto-creates token provider for authentication
            profile: Databricks profile name for local IDE (optional, for WorkspaceClient)
                    If provided: WorkspaceClient(profile=profile) - for local IDE
                    If not provided: WorkspaceClient() - for online notebooks
            
        Note:
            The cache table must be set up once by admin/DBA using setup().
            Like Redis, users don't run setup - they just connect and use!
            
            CuckooFilter provides ~10-1000x speedup for negative lookups (checking keys that don't exist).
            Disable it if you want to minimize memory usage or don't need negative lookup optimization.
            
        Examples:
            # Regular PostgreSQL
            >>> cache = FastPgCache(
            ...     host="localhost",
            ...     database="mydb",
            ...     user="myuser",
            ...     password="mypass"
            ... )
            
            # Databricks (online notebook mode)
            >>> cache = FastPgCache(
            ...     host="instance-xyz.database.cloud.databricks.com",
            ...     database="databricks_postgres",
            ...     user="user@company.com",
            ...     instance_name="my-instance"
            ... )
            
            # Databricks (local IDE with profile)
            >>> cache = FastPgCache(
            ...     host="instance-xyz.database.cloud.databricks.com",
            ...     database="databricks_postgres",
            ...     user="user@company.com",
            ...     instance_name="my-instance",
            ...     profile="my-profile"
            ... )
        """
        self.connection_string = connection_string
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema
        
        # Auto-detect Databricks mode from presence of instance_name
        if instance_name:
            try:
                from databricks.sdk import WorkspaceClient
                from .token_provider import DatabricksTokenProvider
            except ImportError:
                raise ImportError(
                    "databricks-sdk is required for Databricks integration. "
                    "Install it with: pip install 'fastpgcache[databricks]'"
                )
            
            # Create WorkspaceClient based on profile
            if profile:
                print(f"🔐 Initializing Databricks with profile '{profile}' (local IDE mode)")
                workspace_client = WorkspaceClient(profile=profile)
            else:
                print("🔐 Initializing Databricks with default credentials (online notebook mode)")
                workspace_client = WorkspaceClient()
            
            # Create token provider
            self.token_provider = DatabricksTokenProvider(
                workspace_client=workspace_client,
                instance_names=[instance_name],
                refresh_interval=3600,
                auto_refresh=True
            )
            print(f"✓ Databricks token provider initialized for instance '{instance_name}'")
        else:
            # No token provider for regular PostgreSQL
            self.token_provider = None

        # Optional CuckooFilter for fast negative lookups
        self.use_cuckoo_filter = use_cuckoo_filter
        if use_cuckoo_filter:
            self.cuckoo_filter = CuckooFilter(capacity=cuckoo_capacity)
        else:
            self.cuckoo_filter = None
        
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
                    sql.SQL("SELECT {}.cache_set(%s, %s, %s, %s)").format(
                        sql.Identifier(self.schema)
                    ),
                    (self.user_id, key, value, ttl)
                )
                result = cursor.fetchone()[0]
                conn.commit()
                
                # Update CuckooFilter if enabled
                if self.cuckoo_filter:
                    self.cuckoo_filter.insert(f'{key}:{self.user_id}')
                
                return result
    
    def set_many(
        self,
        items: dict,
        ttl: Optional[int] = None
    ) -> int:
        """
        Set multiple cache values in a single transaction (much faster).
        
        Args:
            items: Dictionary of key-value pairs to cache
            ttl: Time to live in seconds (None = no expiry), applies to all items
        
        Returns:
            Number of items successfully set
        
        Example:
            >>> cache.set_many({
            ...     "user:123": {"name": "Alice"},
            ...     "user:456": {"name": "Bob"},
            ...     "user:789": {"name": "Charlie"}
            ... }, ttl=3600)
            3
        """
        if not items:
            return 0
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                count = 0
                for key, value in items.items():
                    # Auto-serialize dicts and lists to JSON
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    
                    cursor.execute(
                        sql.SQL("SELECT {}.cache_set(%s, %s, %s, %s)").format(
                            sql.Identifier(self.schema)
                        ),
                        (self.user_id, key, value, ttl)
                    )
                    if cursor.fetchone()[0]:
                        count += 1
                        # Update CuckooFilter if enabled
                        if self.cuckoo_filter:
                            self.cuckoo_filter.insert(f'{key}:{self.user_id}')
                
                # Single commit for all items
                conn.commit()
                return count
    
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
        # Fast negative lookup via CuckooFilter (if enabled)
        if self.cuckoo_filter and not self.cuckoo_filter.lookup(f'{key}:{self.user_id}'):
            return None

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT {}.cache_get(%s, %s)").format(
                        sql.Identifier(self.schema)
                    ),
                    (self.user_id, key)
                )
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
                cursor.execute(
                    sql.SQL("SELECT {}.cache_delete(%s, %s)").format(
                        sql.Identifier(self.schema)
                    ),
                    (self.user_id, key)
                )
                result = cursor.fetchone()[0]
                conn.commit()
                
                # Update CuckooFilter if enabled
                if self.cuckoo_filter:
                    self.cuckoo_filter.delete(f'{key}:{self.user_id}')
                
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
        # Fast negative lookup via CuckooFilter (if enabled)
        if self.cuckoo_filter and not self.cuckoo_filter.lookup(f'{key}:{self.user_id}'):
            return False

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT {}.cache_exists(%s, %s)").format(
                        sql.Identifier(self.schema)
                    ),
                    (self.user_id, key)
                )
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
                cursor.execute(
                    sql.SQL("SELECT {}.cache_ttl(%s, %s)").format(
                        sql.Identifier(self.schema)
                    ),
                    (self.user_id, key)
                )
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
                cursor.execute(
                    sql.SQL("SELECT {}.cache_cleanup()").format(
                        sql.Identifier(self.schema)
                    )
                )
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

