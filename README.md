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

## 🔒 User Isolation (Important!)

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
-- Table structure
CREATE TABLE public.cache (
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

See `row_isolation_example.py` for details.

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

**Admin/DBA runs this ONCE to create the cache table:**

```bash
# Local PostgreSQL (requires password)
python admin_setup_cache.py --host localhost --user postgres --password mypass

# With custom schema
python admin_setup_cache.py --host myhost --user admin --password mypass --schema my_cache

# Databricks (NO password needed - token provider handles authentication)
python admin_setup_cache.py \
  --databricks \
  --host myhost.cloud.databricks.com \
  --database databricks_postgres \
  --user admin@company.com \
  --instance-name my_instance \
  --profile Oauth

# CI/CD (non-interactive mode)
python admin_setup_cache.py --host myhost --user admin --password $DB_PASS --force
```

**This is NOT for regular users! Only admin/DBA/DevOps.**

> **Note:** The `admin_setup_cache.py` script handles all setup internally. You don't need to write any code - just run the script with appropriate credentials.

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

### Redis Comparison

| Redis | FastPgCache |
|-------|-------------|
| `$ redis-server` | Admin runs `cache.setup()` once |
| `r = redis.Redis(...)` | `cache = FastPgCache(...)` |
| `r.set('key', 'value')` | `cache.set('key', 'value')` |
| `r.get('key')` | `cache.get('key')` |

**Key Point:** Like Redis, users don't run setup - they just connect and use!

## Databricks Token Authentication

### The Solution: DatabricksTokenProvider

✅ **With Automatic Token Rotation:**
```python
from databricks.sdk import WorkspaceClient
from fastpgcache import FastPgCache, DatabricksTokenProvider
# If you use Databricks notebook or Databricks apps runtime, you don't need to add profile
# w = WorkspaceClient()
w = WorkspaceClient(profile="Oauth")

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
    schema="public",  # Specify the schema for the cache table
    auto_setup=True
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
    minconn=1,
    maxconn=10,
    auto_setup=False
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
- `auto_setup` (bool): Automatically run setup() if not already set up (default: True)

### Methods

#### is_setup()

Check if the cache system is already initialized.

**Returns:** `bool` - True if cache table exists

```python
if not cache.is_setup():
    cache.setup()
```

#### setup(force_recreate=False)

Initialize cache tables and functions. Safe to run multiple times.

**Parameters:**
- `force_recreate` (bool): If True, drops and recreates all objects (⚠️ loses all cache data). If False (default), creates objects only if they don't exist.

```python
# First time setup - creates tables and functions
cache.setup()

# Safe to run again - won't lose data
cache.setup()

# Force recreate - WILL DELETE ALL CACHE DATA
cache.setup(force_recreate=True)
```

**Note:** 
- With `auto_setup=True`, setup only runs if needed (checks with `is_setup()` first)
- Functions use `CREATE OR REPLACE` (PostgreSQL standard) - very fast, no overhead
- After initial setup, you can skip `setup()` entirely on subsequent connections

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

## Examples

### API Response Caching

```python
from fastpgcache import FastPgCache
import requests

cache = FastPgCache("postgresql://user:pass@localhost/mydb", auto_setup=True)

def get_weather(city):
    cache_key = f"weather:{city}"
    
    # Try cache first
    cached = cache.get(cache_key)
    if cached:
        print("Cache HIT!")
        return cached
    
    # Cache miss - fetch from API
    print("Cache MISS - fetching from API...")
    response = requests.get(f"https://api.weather.com/{city}")
    data = response.json()
    
    # Cache for 5 minutes
    cache.set(cache_key, data, ttl=300)
    return data

# First call - fetches from API
weather = get_weather("NYC")

# Second call - instant from cache!
weather = get_weather("NYC")

cache.close()
```

### Session Management

```python
cache.set(f"session:{session_id}", user_data, ttl=1800)  # 30 min
```

### Database Query Caching

```python
cache.set(f"query:{query_hash}", results, ttl=3600)  # 1 hour
```

### Rate Limiting

```python
count = cache.get(f"ratelimit:{user_id}") or 0
if count < 100:
    cache.set(f"ratelimit:{user_id}", count + 1, ttl=3600)
```


### Cache Persistence Example

```python
from fastpgcache import FastPgCache

# Create cache and store data
cache1 = FastPgCache("postgresql://user:pass@localhost/mydb", auto_setup=True)
cache1.set("user:123", {"name": "Alice"})
cache1.close()

# Later... new connection, data still there!
cache2 = FastPgCache("postgresql://user:pass@localhost/mydb")
user = cache2.get("user:123")  # ✅ Works! Returns {"name": "Alice"}
cache2.close()
```

### Scheduled Cleanup with Cron

```python
# cleanup_cron.py
from fastpgcache import FastPgCache

cache = FastPgCache("postgresql://user:pass@localhost/mydb")
deleted = cache.cleanup()
print(f"Cleaned up {deleted} expired entries")
cache.close()
```

Then schedule with crontab:
```bash
# Run cleanup every 5 minutes
*/5 * * * * /usr/bin/python /path/to/cleanup_cron.py
```

## Performance Tips

1. **Connection Pooling** - Automatically handled with configurable pool size
2. **Batch Operations** - Use transactions for multiple operations
3. **Regular Cleanup** - Schedule `cache.cleanup()` periodically
4. **UNLOGGED Tables** - Already configured for maximum write speed

## Important Notes

### Cache Persistence

✅ **Cache data PERSISTS when:**
- You close and reopen connections (`cache.close()` then create new `FastPgCache`)
- You restart your application
- Multiple applications connect to the same database

❌ **Cache data is LOST when:**
- PostgreSQL server crashes or restarts (UNLOGGED table behavior)
- You call `cache.setup(force_recreate=True)`

### Other Notes

- **UNLOGGED Tables** - Data is not crash-safe (lost on database crash). For durability, modify the setup SQL to remove `UNLOGGED`.
- **First Setup** - Run `cache.setup()` once to create tables and functions. Safe to run multiple times (won't lose data).
- **Cleanup** - Schedule `cache.cleanup()` to remove expired entries (they're auto-removed on access, but cleanup helps with storage)
- **auto_setup=True** - Safe to use! Creates tables if they don't exist, but won't drop existing cache data.


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
   w = WorkspaceClient(profile="Oauth")
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
- [PostgreSQL Authentication](https://www.postgresql.org/docs/current/auth-password.html)
- [Examples Directory](examples/)

