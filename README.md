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

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Databricks Token Authentication](#databricks-token-authentication)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Advanced Usage](#advanced-usage)
- [Migration from Redis](#migration-from-redis)
- [Contributing](#contributing)

## Quick Start

### 1. Install

```bash
pip install fastpgcache
```

For development:
```bash
cd /path/to/postgres
pip install -e .
```

For Databricks support:
```bash
pip install fastpgcache[databricks]
```

### 2. Simple Example

```python
from fastpgcache import FastPgCache

# Connect to your PostgreSQL database
cache = FastPgCache(
    host="localhost",
    database="postgres",
    user="postgres",
    password="your_password"
)

# Set up the cache (only needed once)
cache.setup()

# Start caching!
cache.set("user:123", {"name": "Alice", "email": "alice@example.com"}, ttl=3600)

# Retrieve from cache
user = cache.get("user:123")
print(user)  # {'name': 'Alice', 'email': 'alice@example.com'}

# Check if exists
if cache.exists("user:123"):
    print("User is cached!")

# Check TTL
seconds_left = cache.ttl("user:123")
print(f"Expires in {seconds_left} seconds")

# Delete
cache.delete("user:123")

# Close connection
cache.close()
```

### 3. Using Connection String (Easiest)

```python
from fastpgcache import FastPgCache

# One-liner connection
cache = FastPgCache("postgresql://user:password@localhost:5432/mydb", auto_setup=True)

# Use it immediately
cache.set("key", "value", ttl=300)
print(cache.get("key"))

cache.close()
```

### 4. Context Manager (Best Practice)

```python
from fastpgcache import FastPgCache

with FastPgCache("postgresql://user:pass@localhost/mydb") as cache:
    cache.setup()  # Only needed once
    
    cache.set("session:abc", {"user_id": 123}, ttl=1800)
    session = cache.get("session:abc")
    print(session)
    
# Connection automatically closed!
```

## Installation

### Basic Installation

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

Or add to your `requirements.txt`:
```
fastpgcache[databricks]>=0.1.0
```

## Databricks Token Authentication

### The Problem: Token Expiration

Databricks PostgreSQL instances use time-limited tokens for authentication. These tokens expire regularly (typically every 1-2 hours), which causes problems for long-running applications.

❌ **Without Token Rotation:**
```python
from databricks.sdk import WorkspaceClient
import uuid
from fastpgcache import FastPgCache

w = WorkspaceClient(profile="Oauth")
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), 
    instance_names=["my_instance"]
)

# Problem: This token will expire!
cache = FastPgCache(
    host="my-instance.database.cloud.databricks.com",
    database="databricks_postgres",
    user="user@databricks.com",
    password=cred.token,  # Static token - will expire
)

cache.set("key", "value")
# ❌ After token expires: psycopg2.OperationalError: authentication failed
cache.get("key")  # FAILS!
```

### The Solution: DatabricksTokenProvider

✅ **With Automatic Token Rotation:**
```python
from databricks.sdk import WorkspaceClient
from fastpgcache import FastPgCache, DatabricksTokenProvider

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
    auto_setup=True
)

# Works forever - tokens automatically refresh!
cache.set("key", "value")
# ... hours later ...
cache.get("key")  # ✅ Still works!
```

### Quick Upgrade Guide

Already using manual token generation? Here's how to upgrade:

#### Step 1: Update Your Imports

```python
# Add this import
from fastpgcache import DatabricksTokenProvider
```

#### Step 2: Create Token Provider

```python
# Replace this:
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), 
    instance_names=[instance_name]
)
password = cred.token

# With this:
token_provider = DatabricksTokenProvider(
    workspace_client=w,
    instance_names=[instance_name],
    refresh_interval=3600,
    auto_refresh=True
)
```

#### Step 3: Update FastPgCache Initialization

```python
# Replace this:
cache = FastPgCache(
    host=host,
    database=dbname,
    user=user,
    password=password,  # OLD: Static token
    auto_setup=True
)

# With this:
cache = FastPgCache(
    host=host,
    database=dbname,
    user=user,
    token_provider=token_provider,  # NEW: Automatic rotation!
    auto_setup=True
)
```

**That's it!** Your code now has automatic token rotation. No more auth errors!

### Benefits

✅ **Automatic Token Management**
- No manual token refresh required
- No token expiry errors
- Background refresh before expiry

✅ **Resilient Connections**
- Automatic retry on authentication failures
- Seamless connection pool refresh
- No downtime during token rotation

✅ **Production Ready**
- Thread-safe token access
- Proper cleanup on shutdown
- Minimal overhead

✅ **Developer Friendly**
- Drop-in replacement for password auth
- Clear error messages
- Comprehensive examples

### How It Works

#### 1. Automatic Token Refresh

The token provider runs a background thread that refreshes tokens before they expire:

- Tokens are refreshed every `refresh_interval` seconds
- Refresh happens 5 minutes before expiry (configurable buffer)
- Background thread is automatically managed

#### 2. Automatic Retry on Auth Errors

If a token expires unexpectedly, FastPgCache automatically:
1. Catches the authentication error
2. Requests a fresh token from the provider
3. Recreates the connection pool
4. Retries the operation

#### 3. Connection Pool Management

When tokens are refreshed, the connection pool is automatically recreated with the new credentials.

### Configuration Options

#### DatabricksTokenProvider

```python
DatabricksTokenProvider(
    workspace_client,      # Required: Databricks WorkspaceClient
    instance_names,        # Required: List of instance names
    refresh_interval=3600, # Optional: Seconds between refreshes (default: 1 hour)
    auto_refresh=True      # Optional: Enable background refresh (default: True)
)
```

### Common Patterns

#### Long-Running Application

For applications that run continuously (e.g., web servers, background workers):

```python
from databricks.sdk import WorkspaceClient
from fastpgcache import FastPgCache, DatabricksTokenProvider

# Initialize once at startup
w = WorkspaceClient(profile="Oauth")
token_provider = DatabricksTokenProvider(
    workspace_client=w,
    instance_names=["my_instance"],
    refresh_interval=3600,
    auto_refresh=True
)

cache = FastPgCache(
    host="my-instance.database.cloud.databricks.com",
    database="databricks_postgres",
    user="user@databricks.com",
    token_provider=token_provider,
    auto_setup=True
)

# Use cache throughout application lifetime
# Tokens are automatically refreshed in background
```

#### Context Manager (Short-Lived Script)

For scripts that run for a short time:

```python
from databricks.sdk import WorkspaceClient
from fastpgcache import FastPgCache, DatabricksTokenProvider

w = WorkspaceClient(profile="Oauth")
token_provider = DatabricksTokenProvider(
    workspace_client=w,
    instance_names=["my_instance"],
    refresh_interval=3600,
    auto_refresh=False  # No need for background refresh
)

with FastPgCache(
    host="...",
    database="...",
    user="...",
    token_provider=token_provider,
    auto_setup=True
) as cache:
    cache.set("key", "value")
    value = cache.get("key")
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
- `minconn` (int): Minimum connections in pool (default: 1)
- `maxconn` (int): Maximum connections in pool (default: 10)
- `auto_setup` (bool): Automatically run setup() (default: False)

### Methods

#### setup()

Initialize cache tables and functions. Run this once before using the cache.

```python
cache.setup()
```

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

### More Examples

See the `examples/` directory for complete examples:
- `basic_usage.py` - Basic cache operations
- `databricks_token_example.py` - Complete Databricks token usage
- `connection_string.py` - Using connection strings
- `context_manager.py` - Context manager usage
- `advanced_usage.py` - Advanced patterns

## Advanced Usage

### Full Example with All Features

```python
from fastpgcache import FastPgCache
import time

# Initialize with auto-setup
cache = FastPgCache(
    "postgresql://user:password@localhost/mydb",
    auto_setup=True
)

# Store session data with 30 minute expiry
cache.set(
    "session:abc123",
    {
        "user_id": 123,
        "ip": "192.168.1.1",
        "logged_in_at": "2025-10-12T17:00:00Z"
    },
    ttl=1800
)

# Store API response with 5 minute cache
cache.set(
    "api:weather:NYC",
    {"temp": 72, "conditions": "sunny"},
    ttl=300
)

# Store configuration without expiry
cache.set("config:app", {"theme": "dark", "language": "en"})

# Retrieve values
session = cache.get("session:abc123")
weather = cache.get("api:weather:NYC")
config = cache.get("config:app")

# Check TTL
print(f"Session expires in: {cache.ttl('session:abc123')} seconds")
print(f"Config TTL: {cache.ttl('config:app')}")  # Returns -1 (no expiry)

# Clean up when done
cache.close()
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

### Custom Connection Pool

```python
cache = FastPgCache(
    "postgresql://user:pass@localhost/mydb",
    minconn=5,   # Minimum 5 connections
    maxconn=20   # Maximum 20 connections
)
```

## Migration from Redis

```python
# Redis
import redis
r = redis.Redis(host='localhost', port=6379)
r.setex('user:123', 3600, '{"name":"Alice"}')
r.get('user:123')
r.delete('user:123')
r.exists('user:123')
r.ttl('user:123')

# FastPgCache
from fastpgcache import FastPgCache
cache = FastPgCache(host='localhost', database='mydb')
cache.setup()
cache.set('user:123', {"name": "Alice"}, ttl=3600)
cache.get('user:123')
cache.delete('user:123')
cache.exists('user:123')
cache.ttl('user:123')
```

## Comparison with Redis

| Feature | Redis | FastPgCache |
|---------|-------|---------|
| Speed | Very Fast | Fast (UNLOGGED) |
| TTL | Native | Via functions |
| Persistence | Optional | Optional |
| Transactions | Limited | Full ACID |
| Querying | Limited | Full SQL |
| Setup | Separate service | Built-in |
| Infrastructure | Redis server | PostgreSQL only |

## Performance Tips

1. **Connection Pooling** - Automatically handled with configurable pool size
2. **Batch Operations** - Use transactions for multiple operations
3. **Regular Cleanup** - Schedule `cache.cleanup()` periodically
4. **UNLOGGED Tables** - Already configured for maximum write speed

## Important Notes

- **UNLOGGED Tables** - Data is not crash-safe (lost on database crash). For durability, modify the setup SQL to remove `UNLOGGED`.
- **First Setup** - Run `cache.setup()` once to create tables and functions
- **Cleanup** - Schedule `cache.cleanup()` to remove expired entries (they're auto-removed on access, but cleanup helps with storage)

## Troubleshooting

### Connection Issues

**Connection refused:**
- Make sure PostgreSQL is running: `pg_ctl status` or `sudo systemctl status postgresql`
- Check connection settings

**Authentication failed:**
- Verify username and password
- Check `pg_hba.conf` for authentication settings

**Permission denied on setup:**
- Ensure user has CREATE privileges:
  ```sql
  GRANT CREATE ON SCHEMA public TO your_user;
  ```

**psycopg2 not found:**
```bash
pip install psycopg2-binary
```

### Databricks Token Issues

**Token Refresh Failing:**

1. **Workspace Client Configuration:**
   ```python
   # Ensure valid authentication
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

