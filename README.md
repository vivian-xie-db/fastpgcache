# FastPgCache 🐘⚡

A **fast Redis-like caching library** for PostgreSQL with high performance using UNLOGGED tables. Get Redis-style caching without the extra infrastructure!

## Why FastPgCache?

- **🚀 Fast** - Uses PostgreSQL UNLOGGED tables for Redis-like performance
- **⏰ TTL Support** - Automatic expiry like Redis SET with EX
- **🔄 Redis-like API** - Familiar methods: `set()`, `get()`, `delete()`, `exists()`, `ttl()`
- **🎯 Simple** - One less service to manage
- **💪 ACID** - Get caching within PostgreSQL transactions
- **📦 JSON Support** - Automatic JSON serialization/deserialization
- **🔐 Token Rotation** - Built-in support for Databricks token authentication
- **🔒 User Isolation** - Automatic per-user cache isolation (no race conditions!)

## 🚀 Performance: UNLOGGED vs Regular Tables

FastPgCache uses PostgreSQL **UNLOGGED tables** for dramatically better performance. Here are real-world benchmarks from Databricks PostgreSQL:

### Load Test Results (10 threads, 100 ops each)

| Metric | UNLOGGED Table | Regular Table | Improvement |
|--------|----------------|---------------|-------------|
| **Throughput** | **553 ops/sec** | 496 ops/sec | **+11.5%** |
| **SET Mean** | **7.58 ms** | 12.17 ms | **37% faster** |
| **SET P95** | **10.71 ms** | 17.97 ms | **40% faster** |
| **SET P99** | **14.65 ms** | 21.67 ms | **32% faster** |
| **GET Mean** | **7.60 ms** | 8.04 ms | **5% faster** |
| **GET P95** | **10.74 ms** | 12.09 ms | **11% faster** |

**Key Takeaway:** UNLOGGED tables provide **37% faster writes** and **11.5% higher throughput**, making them ideal for caching workloads.

### What are UNLOGGED Tables?

UNLOGGED tables are a PostgreSQL feature that:
- ✅ **Skip write-ahead logging (WAL)** - Much faster writes
- ✅ **Perfect for cache** - Temporary data that can be regenerated
- ✅ **Still ACID** - Transaction support within PostgreSQL
- ⚠️ **Data lost on crash** - Acceptable for cache (not for permanent data)

Learn more: [PostgreSQL UNLOGGED Tables](https://www.postgresql.org/docs/current/sql-createtable.html#SQL-CREATETABLE-UNLOGGED)

## 🔒 User Isolation

**By default, each user gets isolated cache** - all users share the same table, but rows are filtered by `user_id`:

```python
# All users share public.cache table
cache_alice = FastPgCache(user="alice@company.com")
cache_bob = FastPgCache(user="bob@company.com")

# Same key name, different values - no collision!
cache_alice.set("session", "alice_value")
cache_bob.set("session", "bob_value")

# Each user only sees their own data
cache_alice.get("session")  # Returns: "alice_value"
cache_bob.get("session")    # Returns: "bob_value"
```

**How it works:**
```sql
-- Table structure (UNLOGGED for performance!)
CREATE UNLOGGED TABLE public.cache (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    ...
    PRIMARY KEY (user_id, key)
);

-- Alice's data: WHERE user_id = 'alice@company.com'
-- Bob's data:   WHERE user_id = 'bob@company.com'
```

**Benefits:**
- ✅ Simple (one table for everyone)
- ✅ Fast (indexed lookups on user_id + key)
- ✅ No race conditions (composite primary key)
- ✅ No data interference (automatic row filtering)
- ✅ Scales to millions of users

## Quick Start

### Installation

```bash
pip install fastpgcache
```

Or from source:

```bash
git clone https://github.com/vivian-xie-db/fastpgcache.git
cd fastpgcache
pip install -e .
```

### With Databricks Support

```bash
pip install fastpgcache[databricks]
```

## Usage (Redis-Like Pattern)

> **Important:** Like Redis, there are two distinct roles:
> - **Admin/DBA:** Sets up cache once (like starting Redis server)
> - **Regular Users:** Just connect and use (like Redis clients)

### Step 1: Admin Setup (⚠️ Admin/DBA Only - Once)

**Admin/DBA runs this ONCE to create the UNLOGGED cache table:**

After `pip install fastpgcache`, the admin command is automatically available:

```bash
# Local PostgreSQL
fastpgcache-admin --host localhost --user postgres --password mypass

# With custom schema
fastpgcache-admin --host myhost --user admin --password mypass --schema my_cache

# Databricks (NO password needed - token provider handles authentication)
fastpgcache-admin \
  --databricks \
  --host myhost.cloud.databricks.com \
  --database databricks_postgres \
  --user admin@company.com \
  --instance-name my_instance \
  --profile Oauth

# CI/CD with force recreate (no prompts)
fastpgcache-admin --host myhost --user admin --password $DB_PASS --force
```

**Alternative:** Run the Python script directly:
```bash
python -m fastpgcache.admin --host localhost --user postgres --password mypass
```

**This is NOT for regular users! Only admin/DBA/DevOps.**

> **Note:** The `fastpgcache-admin` command creates UNLOGGED tables automatically for optimal performance. You don't need to write any code - just run the command with appropriate credentials.

The script supports these options:
- `--host`: Database host (default: localhost)
- `--database`: Database name (default: postgres)
- `--user`: Admin user with CREATE TABLE permissions
- `--password`: Database password (**ONLY for local PostgreSQL, omit for Databricks**)
- `--schema`: Schema for cache table (default: public)
- `--force`: Force recreate without prompts (for CI/CD)
- `--databricks`: Use Databricks token authentication (no password needed)
- `--instance-name`: Databricks instance name (required with `--databricks`)
- `--profile`: Databricks auth profile (default: Oauth)

**When to use `--password`:**
- ✅ Local PostgreSQL: `--password mypass`
- ❌ Databricks: Don't use `--password` (token provider handles it)

### Step 2: Users Connect and Use (✅ Regular Users)

**Users just connect - NO setup() calls needed:**

```python
from fastpgcache import FastPgCache

# Just connect - like Redis!
cache = FastPgCache(
    host="your-host",
    database="your-db",
    user="alice@company.com",
    password="user-password"
)

# Use immediately - no setup needed!
cache.set("session", {"user": "Alice"}, ttl=3600)
user_data = cache.get("session")

# Each user's data is automatically isolated
```

## Databricks Token Authentication

### The Solution: DatabricksTokenProvider

✅ **With Automatic Token Rotation:**
```python
from databricks.sdk import WorkspaceClient
from fastpgcache import FastPgCache, DatabricksTokenProvider

# If you use Databricks notebook or Databricks apps runtime, you don't need to add profile
# w = WorkspaceClient()
w = WorkspaceClient()

# Create token provider with automatic rotation
token_provider = DatabricksTokenProvider(
    workspace_client=w,
    instance_names=["my_instance"],
    refresh_interval=3600,  # Refresh every hour
    auto_refresh=True       # Enable background refresh
)

# Cache automatically uses fresh tokens
cache = FastPgCache(
    host="my-instance.database.cloud.databricks.com",
    database="databricks_postgres",
    user="user@databricks.com",
    token_provider=token_provider,  # Automatic token management!
    schema="public"  # Specify the schema for the cache table
)

# 1. Set values with TTL
print("1. Setting cache values...")
cache.set("user:123", {"name": "Alice", "role": "admin"}, ttl=3600)
cache.set("user:456", {"name": "Bob", "role": "user"}, ttl=3600)
cache.set("session:abc", {"user_id": 123, "ip": "192.168.1.1"}, ttl=1800)
print("✓ Values set\n")

# 2. Get values
print("2. Getting cache values...")
user123 = cache.get("user:123")
print(f"user:123 = {user123}")
session = cache.get("session:abc")
print(f"session:abc = {session}\n")

# 3. Check if key exists
print("3. Checking key existence...")
print(f"user:123 exists: {cache.exists('user:123')}")
print(f"user:999 exists: {cache.exists('user:999')}\n")

# 4. Get TTL
print("4. Checking TTL (time to live)...")
ttl = cache.ttl("user:123")
print(f"user:123 expires in {ttl} seconds\n")

# 5. Store value without expiry
print("5. Storing permanent value...")
cache.set("config:app", {"theme": "dark", "language": "en"})
config_ttl = cache.ttl("config:app")
print(f"config:app TTL: {config_ttl} (-1 = no expiry)\n")

# 6. Manual token refresh (optional - normally automatic)
print("6. Manually refreshing token...")
new_token = token_provider.refresh_token()
print(f"Token refreshed (length: {len(new_token)})\n")

# 7. Continue using cache - connection will automatically use new token
print("7. Verifying cache still works after manual refresh...")
test_value = cache.get("user:123")
print(f"user:123 = {test_value}")
print("✓ Cache working perfectly with new token\n")

# Close the connection (also stops token auto-refresh)
cache.close()
print("✓ Cache closed and token provider stopped")
```

## API Reference

### FastPgCache

```python
FastPgCache(
    connection_string=None,
    host='localhost',
    port=5432,
    database='postgres',
    user='postgres',
    password='',
    token_provider=None,
    schema='public',
    minconn=1,
    maxconn=10
)
```

Initialize the cache client.

**Parameters:**
- `connection_string` (str, optional): PostgreSQL connection string
- `host` (str): Database host (default: 'localhost')
- `port` (int): Database port (default: 5432)
- `database` (str): Database name (default: 'postgres')
- `user` (str): Database user (default: 'postgres')
- `password` (str): Database password (ignored if token_provider is set)
- `token_provider` (TokenProvider, optional): Token provider for automatic credential rotation
- `schema` (str): PostgreSQL schema name for cache table (default: 'public')
- `minconn` (int): Minimum connections in pool (default: 1)
- `maxconn` (int): Maximum connections in pool (default: 10)

### Methods

#### set(key, value, ttl=None)

Store a value in the cache.

**Parameters:**
- `key` (str): Cache key
- `value` (str|dict|list): Value to cache (dicts/lists are auto-serialized to JSON)
- `ttl` (int, optional): Time to live in seconds (None = no expiry)

**Returns:** `bool` - True if successful

```python
cache.set("user:123", {"name": "Alice"}, ttl=3600)
```

#### get(key, parse_json=True)

Retrieve a value from the cache.

**Parameters:**
- `key` (str): Cache key
- `parse_json` (bool): Auto-parse JSON values (default: True)

**Returns:** Value or None if not found/expired

```python
user = cache.get("user:123")
```

#### delete(key)

Delete a cache entry.

**Parameters:**
- `key` (str): Cache key

**Returns:** `bool` - True if deleted, False if not found

```python
cache.delete("user:123")
```

#### exists(key)

Check if a key exists and is not expired.

**Parameters:**
- `key` (str): Cache key

**Returns:** `bool` - True if exists

```python
if cache.exists("user:123"):
    print("Key exists!")
```

#### ttl(key)

Get time to live for a key.

**Parameters:**
- `key` (str): Cache key

**Returns:** `int` - Seconds until expiry, -1 if no expiry, -2 if not found

```python
seconds = cache.ttl("user:123")
```

**TTL Return Values:**
- Positive number: Seconds until expiry
- `-1`: No expiry set (permanent)
- `-2`: Key not found

#### cleanup()

Remove all expired cache entries.

**Returns:** `int` - Number of entries deleted

```python
deleted = cache.cleanup()
```

#### close()

Close all connections in the pool.

```python
cache.close()
```


## Important Notes

### Cache Persistence

✅ **Cache data PERSISTS when:**
- You close and reopen connections (`cache.close()` then create new `FastPgCache`)
- You restart your application
- Multiple applications connect to the same database

❌ **Cache data is LOST when:**
- PostgreSQL server crashes or restarts (UNLOGGED table behavior)
- You call `setup(force_recreate=True)` during admin setup

### Other Notes

- **UNLOGGED Tables** - Data is not crash-safe (lost on database crash). This is by design for cache performance. For durability, you would need to modify the setup SQL to remove `UNLOGGED` (not recommended for cache).
- **First Setup** - Admin runs `admin_setup_cache.py` once to create UNLOGGED tables and functions. Safe to run multiple times (won't lose data).
- **Cleanup** - Schedule `cache.cleanup()` to remove expired entries (they're auto-removed on access, but cleanup helps with storage)

### Verifying UNLOGGED Table

To verify your cache table is properly configured as UNLOGGED:

```sql
-- Check table type
SELECT 
    relname as table_name,
    CASE relpersistence
        WHEN 'u' THEN 'UNLOGGED'
        WHEN 'p' THEN 'PERMANENT'
        WHEN 't' THEN 'TEMPORARY'
    END as table_type
FROM pg_class
WHERE relname = 'cache' AND relkind = 'r';
```

You should see `UNLOGGED` as the table_type.

## Troubleshooting

**psycopg2 not found:**
```bash
pip install psycopg2-binary
```

### Databricks Token Issues

**Token Refresh Failing:**

1. **Workspace Client Configuration:**
   ```python
   # Ensure valid authentication. If you use Databricks notebook or Databricks apps runtime, you don't 
   # need to add profile
   # w = WorkspaceClient()
   w = WorkspaceClient()
   # Test credential generation
   cred = w.database.generate_database_credential(
       request_id=str(uuid.uuid4()),
       instance_names=["my_instance"]
   )
   print(f"Token generated: {cred.token[:20]}...")
   ```

2. **Instance Names:**
   ```python
   # Ensure instance name is correct
   token_provider = DatabricksTokenProvider(
       workspace_client=w,
       instance_names=["correct_instance_name"],  # Must match exactly
       ...
   )
   ```

3. **Network Connectivity:**
   - Ensure connection to Databricks workspace
   - Check firewall/proxy settings

**Connection Errors After Token Refresh:**

- Make sure refresh happens before expiry (adjust `refresh_interval`)
- Keep connection pool size reasonable (lower = faster refresh)

## Requirements

- Python 3.7+
- PostgreSQL 9.6+
- psycopg2-binary

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub: https://github.com/vivian-xie-db/fastpgcache/issues

## Additional Resources

- [Databricks SDK Documentation](https://databricks-sdk-py.readthedocs.io/)
- [PostgreSQL UNLOGGED Tables](https://www.postgresql.org/docs/current/sql-createtable.html#SQL-CREATETABLE-UNLOGGED)
- [PostgreSQL Authentication](https://www.postgresql.org/docs/current/auth-password.html)
- [Load Testing Documentation](examples/README_load_testing.md)
- [Examples Directory](examples/)

