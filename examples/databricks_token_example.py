"""
Example: Using FastPgCache with Databricks token-based authentication
"""

from databricks.sdk import WorkspaceClient
from fastpgcache import FastPgCache, DatabricksTokenProvider

# Initialize Databricks workspace client
w = WorkspaceClient(profile="Oauth")

# Configuration
instance_name = "fe_shared_demo"
host = "instance-33607cf0-86c1-4306-a5c3-2464761fa328.database.cloud.databricks.com"
user = "wenwen.xie@databricks.com"
dbname = "databricks_postgres"

# Create token provider with automatic rotation
# Tokens will be automatically refreshed every hour (3600 seconds)
token_provider = DatabricksTokenProvider(
    workspace_client=w,
    instance_names=[instance_name],
    refresh_interval=3600,  # Refresh every hour
    auto_refresh=True  # Enable automatic background refresh
)

# Initialize cache with token provider
cache = FastPgCache(
    host=host,
    port=5432,
    database=dbname,
    user=user,
    token_provider=token_provider,  # Use token provider instead of static password
    auto_setup=True
)

print("=== FastPgCache with Databricks Token Authentication ===\n")

# The cache will now automatically handle token rotation
# No need to manually refresh credentials!

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

print("\n=== Benefits of Token Provider ===")
print("✓ Automatic token rotation in the background")
print("✓ No manual credential management needed")
print("✓ Automatic retry on authentication failures")
print("✓ Seamless connection pool refresh")

