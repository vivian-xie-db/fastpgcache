#!/usr/bin/env python3
"""
FastPgCache Admin Setup Script

⚠️  ADMIN/DBA ONLY - NOT FOR REGULAR USERS ⚠️

This script sets up the cache table infrastructure (like starting a Redis server).
Run this ONCE to initialize the cache table. After this, regular users can just
connect and use the cache - no setup needed!

WHO SHOULD RUN THIS:
    ✓ Admin/DBA (with CREATE TABLE permissions)
    ✓ DevOps (in deployment scripts)
    ✓ CI/CD pipeline
    ✗ NOT regular application users!

USAGE:
    python admin_setup_cache.py

WHAT IT DOES:
    - Creates cache table: public.cache
    - Creates functions: cache_set, cache_get, cache_delete, etc.
    - Creates indexes for performance
    
AFTER RUNNING THIS:
    Regular users connect like Redis:
        cache = FastPgCache(user='alice@company.com')
        cache.set("key", "value")  # Just works!
    
    No setup() calls in user code!
"""

import psycopg2
from psycopg2 import sql
import sys


def check_cache_setup(conn, schema: str) -> bool:
    """
    Check if cache table and functions are already set up.
    
    Args:
        conn: Database connection
        schema: PostgreSQL schema name
        
    Returns:
        True if cache table and functions exist
    """
    print(f"Checking if cache table and functions are already set up in schema: {schema}")
    try:
        with conn.cursor() as cursor:
            # Check if table exists
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                (schema, 'cache')
            )
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                return False
            
            # Check if key functions exist
            cursor.execute(
                """SELECT COUNT(*) FROM information_schema.routines 
                   WHERE routine_schema = %s 
                   AND routine_name IN ('cache_get', 'cache_set', 'cache_delete')""",
                (schema,)
            )
            function_count = cursor.fetchone()[0]
            
            print(f"Table exists: {table_exists}")
            print(f"Function count: {function_count}")
            
            return table_exists and function_count >= 3
    except psycopg2.Error:
        return False


def create_cache_infrastructure(conn, schema: str, force_recreate: bool = False):
    """
    Create cache table and functions in PostgreSQL.
    
    Args:
        conn: Database connection
        schema: PostgreSQL schema name
        force_recreate: If True, drops and recreates all objects
    """
    with conn.cursor() as cursor:
        # Create schema if it doesn't exist
        cursor.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(schema)
            )
        )
        conn.commit()
        
        # If force_recreate, drop everything first
        if force_recreate:
            drop_sql = f"""
-- Drop existing objects if they exist
DROP TABLE IF EXISTS {schema}.cache CASCADE;
DROP FUNCTION IF EXISTS {schema}.cache_set(TEXT, TEXT, TEXT, INTEGER);
DROP FUNCTION IF EXISTS {schema}.cache_get(TEXT, TEXT);
DROP FUNCTION IF EXISTS {schema}.cache_delete(TEXT, TEXT);
DROP FUNCTION IF EXISTS {schema}.cache_exists(TEXT, TEXT);
DROP FUNCTION IF EXISTS {schema}.cache_cleanup();
DROP FUNCTION IF EXISTS {schema}.cache_ttl(TEXT, TEXT);
"""
            cursor.execute(drop_sql)
            conn.commit()
        
        # Create all objects (table and functions)
        setup_sql = f"""
-- Create UNLOGGED table for caching with user isolation (only if not exists)
CREATE UNLOGGED TABLE IF NOT EXISTS {schema}.cache (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

-- Create index for expiry cleanup (only if not exists)
CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON {schema}.cache(expires_at) 
WHERE expires_at IS NOT NULL;

-- Create index for user lookups (only if not exists)
CREATE INDEX IF NOT EXISTS idx_cache_user_id ON {schema}.cache(user_id);

-- Function: SET a cache value with optional TTL
CREATE OR REPLACE FUNCTION {schema}.cache_set(
    p_user_id TEXT,
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
    
    INSERT INTO {schema}.cache (user_id, key, value, expires_at, created_at, accessed_at)
    VALUES (p_user_id, p_key, p_value, v_expires_at, NOW(), NOW())
    ON CONFLICT (user_id, key) 
    DO UPDATE SET
        value = EXCLUDED.value,
        expires_at = EXCLUDED.expires_at,
        accessed_at = NOW();
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function: GET a cache value
CREATE OR REPLACE FUNCTION {schema}.cache_get(p_user_id TEXT, p_key TEXT)
RETURNS TEXT AS $$
DECLARE
    v_value TEXT;
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT value, expires_at 
    INTO v_value, v_expires_at
    FROM {schema}.cache
    WHERE user_id = p_user_id AND key = p_key;
    
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    
    IF v_expires_at IS NOT NULL AND v_expires_at < NOW() THEN
        DELETE FROM {schema}.cache WHERE user_id = p_user_id AND key = p_key;
        RETURN NULL;
    END IF;
    
    UPDATE {schema}.cache SET accessed_at = NOW() WHERE user_id = p_user_id AND key = p_key;
    
    RETURN v_value;
END;
$$ LANGUAGE plpgsql;

-- Function: DELETE a cache entry
CREATE OR REPLACE FUNCTION {schema}.cache_delete(p_user_id TEXT, p_key TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM {schema}.cache WHERE user_id = p_user_id AND key = p_key;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted > 0;
END;
$$ LANGUAGE plpgsql;

-- Function: CHECK if a key exists
CREATE OR REPLACE FUNCTION {schema}.cache_exists(p_user_id TEXT, p_key TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM {schema}.cache
    WHERE user_id = p_user_id AND key = p_key;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    IF v_expires_at IS NOT NULL AND v_expires_at < NOW() THEN
        DELETE FROM {schema}.cache WHERE user_id = p_user_id AND key = p_key;
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function: GET TTL
CREATE OR REPLACE FUNCTION {schema}.cache_ttl(p_user_id TEXT, p_key TEXT)
RETURNS INTEGER AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
    v_ttl_seconds INTEGER;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM {schema}.cache
    WHERE user_id = p_user_id AND key = p_key;
    
    IF NOT FOUND THEN
        RETURN -2;
    END IF;
    
    IF v_expires_at IS NULL THEN
        RETURN -1;
    END IF;
    
    v_ttl_seconds := EXTRACT(EPOCH FROM (v_expires_at - NOW()))::INTEGER;
    
    IF v_ttl_seconds <= 0 THEN
        DELETE FROM {schema}.cache WHERE user_id = p_user_id AND key = p_key;
        RETURN -2;
    END IF;
    
    RETURN v_ttl_seconds;
END;
$$ LANGUAGE plpgsql;

-- Function: CLEANUP expired entries
CREATE OR REPLACE FUNCTION {schema}.cache_cleanup()
RETURNS INTEGER AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM {schema}.cache 
    WHERE expires_at IS NOT NULL 
    AND expires_at < NOW();
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

-- Create view for valid cache entries
CREATE OR REPLACE VIEW {schema}.valid_cache AS
SELECT 
    user_id,
    key,
    value,
    expires_at,
    created_at,
    accessed_at,
    CASE 
        WHEN expires_at IS NULL THEN -1
        ELSE EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER
    END as ttl_seconds
FROM {schema}.cache
WHERE expires_at IS NULL OR expires_at > NOW();
"""
        cursor.execute(setup_sql)
        conn.commit()


def setup_cache(
    host: str,
    database: str,
    user: str,
    password: str = None,
    token_provider = None,
    schema: str = "public",
    force: bool = False
):
    """
    Setup the cache table once (like starting Redis server).
    
    Args:
        host: Database host
        database: Database name
        user: Admin user (with CREATE TABLE permissions)
        password: Password (only for non-Databricks, not needed if using token_provider)
        token_provider: Token provider for Databricks (handles authentication automatically)
        schema: Schema to create cache table in (default: public)
        force: Force recreate without prompting (for CI/CD)
    """

    conn = None
    try:
        # Get credentials
        if token_provider:
            # Token provider handles authentication automatically
            # The token IS the password for PostgreSQL
            password = token_provider.get_token()
        elif password is None:
            print("ERROR: --password is required for non-Databricks connections")
            print("       Use --databricks for Databricks (no password needed)")
            sys.exit(1)
        
        # Connect directly to PostgreSQL
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        
        # Check if already setup
        already_setup = check_cache_setup(conn, schema)
        
        if already_setup:
            if force:
                print("\n🗑️  Force flag set - dropping and recreating cache table...")
                create_cache_infrastructure(conn, schema, force_recreate=True)
                print("✓ Cache table recreated")
            else:
                print("\n⚠️  Cache table already exists!")
                print("   Use --force to recreate (will DELETE ALL CACHE DATA!)")
                print("✓ Setup skipped - cache is ready!")
                return
        else:
            print("\n📦 Creating cache table...")
            create_cache_infrastructure(conn, schema, force_recreate=False)
            print("✓ Cache table created")
        
        # Verify setup
        if check_cache_setup(conn, schema):
            print("\n" + "=" * 70)
            print("✅ SUCCESS - Cache is ready!")
            print("=" * 70)
            print(f"\nTable: {schema}.cache")
            print("Functions: cache_set, cache_get, cache_delete, cache_exists,")
            print("           cache_ttl, cache_cleanup")
            print("\nUsers can now connect and use the cache:")
            print(f"  cache = FastPgCache(host='{host}', database='{database}', user='<their_user>')")
            print("  cache.set('key', 'value')")
            print("  cache.get('key')")
            print("\n✓ Cache is ready - like Redis server is started!")
        else:
            print("\n❌ ERROR - Setup verification failed")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ ERROR during setup: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


def run_admin_setup():
    """Run admin setup with command-line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="FastPgCache Admin Setup Script (Admin/DBA Only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local PostgreSQL (requires password)
  python admin_setup_cache.py --host localhost --user postgres --password mypass
  
  # Setup with custom schema
  python admin_setup_cache.py --host myhost --user admin --password mypass --schema my_cache
  
  # Databricks (NO password needed - token provider handles it)
  python admin_setup_cache.py \\
    --databricks \\
    --host myhost.cloud.databricks.com \\
    --database databricks_postgres \\
    --user admin@company.com \\
    --instance-name my_instance \\
    --profile Oauth
  
  # CI/CD with force recreate
  python admin_setup_cache.py --host myhost --user admin --password $DB_PASS --force
        """
    )
    
    # Connection arguments
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, default=5432, help="Database port")
    parser.add_argument("--database", default="postgres", help="Database name")
    parser.add_argument("--user", default="postgres", help="Admin user (with CREATE TABLE permissions)")
    parser.add_argument("--password", default=None, help="Database password (only for non-Databricks connections)")
    parser.add_argument("--schema", default="public", help="Schema for cache table")
    parser.add_argument("--force", action="store_true", help="Force recreate (no prompts, for CI/CD)")
    
    # Databricks-specific arguments
    parser.add_argument("--databricks", action="store_true", help="Use Databricks token provider (handles auth automatically)")
    parser.add_argument("--instance-name", help="Databricks instance name (required with --databricks)")
    parser.add_argument("--profile", default="Oauth", help="Databricks auth profile (default: Oauth)")
    
    args = parser.parse_args()
    
    # Prepare arguments
    token_provider = None
    if args.databricks:
        try:
            from databricks.sdk import WorkspaceClient
            from fastpgcache import DatabricksTokenProvider
            
            if not args.instance_name:
                print("ERROR: --instance-name required when using --databricks")
                sys.exit(1)
            
            print(f"Setting up Databricks token provider (profile: {args.profile})...")
            w = WorkspaceClient(profile=args.profile)
            token_provider = DatabricksTokenProvider(
                workspace_client=w,
                instance_names=[args.instance_name],
                refresh_interval=3600,
                auto_refresh=True
            )
            print("✓ Token provider ready")
        except ImportError:
            print("ERROR: databricks-sdk not installed. Install with: pip install databricks-sdk")
            sys.exit(1)
    
    # Run setup
    print(f"\n{'='*70}")
    print("FastPgCache Admin Setup")
    print(f"{'='*70}")
    print(f"Host: {args.host}")
    print(f"Database: {args.database}")
    print(f"Schema: {args.schema}")
    print(f"User: {args.user}")
    print(f"{'='*70}\n")
    
    setup_cache(
        host=args.host,
        database=args.database,
        user=args.user,
        password=args.password,
        token_provider=token_provider,
        schema=args.schema,
        force=args.force
    )
    
    print("\n" + "=" * 70)
    print("Setup complete! Users can now use the cache.")
    print("=" * 70)


def main():
    """Entry point for console script"""
    run_admin_setup()


if __name__ == "__main__":
    main()

