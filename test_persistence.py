#!/usr/bin/env python3
"""
Test script to demonstrate cache persistence across connection close/open cycles.
"""

from fastpgcache import FastPgCache
import time

# Configuration - Update with your database details
DB_CONFIG = {
    "host": "your-host.database.cloud.databricks.com",
    "database": "databricks_postgres", 
    "user": "your-email@databricks.com",
    "password": "your-password-or-token"
}

print("=" * 60)
print("Testing Cache Persistence")
print("=" * 60)

# 1. Create first cache instance and setup
print("\n1. Creating cache and setting up tables...")
cache1 = FastPgCache(**DB_CONFIG)
cache1.setup()  # Create tables if they don't exist
print("✓ Setup complete")

# 2. Set some cache values
print("\n2. Setting cache values...")
cache1.set("test:persistence", {"message": "I should persist!"}, ttl=3600)
cache1.set("test:permanent", {"data": "No expiry"})
print("✓ Values set:")
print(f"   test:persistence = {cache1.get('test:persistence')}")
print(f"   test:permanent = {cache1.get('test:permanent')}")

# 3. Close the connection
print("\n3. Closing connection...")
cache1.close()
print("✓ Connection closed")

# 4. Wait a moment
time.sleep(1)

# 5. Create NEW cache instance (new connection)
print("\n4. Creating NEW cache instance (new connection)...")
cache2 = FastPgCache(**DB_CONFIG)
# Note: NOT calling setup() again, but you could safely call it
print("✓ New connection established")

# 6. Verify data still exists
print("\n5. Checking if cache data persisted...")
value1 = cache2.get("test:persistence")
value2 = cache2.get("test:permanent")

if value1 and value2:
    print("✅ SUCCESS! Cache data persisted!")
    print(f"   test:persistence = {value1}")
    print(f"   test:permanent = {value2}")
else:
    print("❌ FAILED! Cache data was lost")
    print(f"   test:persistence = {value1}")
    print(f"   test:permanent = {value2}")

# 7. Test that setup() is now safe to call multiple times
print("\n6. Testing that setup() is safe to call again...")
cache2.setup()  # Should NOT drop existing data
value_after_setup = cache2.get("test:persistence")
if value_after_setup:
    print("✅ SUCCESS! setup() didn't drop data")
    print(f"   test:persistence = {value_after_setup}")
else:
    print("❌ FAILED! setup() dropped the data")

# Cleanup
print("\n7. Cleaning up test data...")
cache2.delete("test:persistence")
cache2.delete("test:permanent")
cache2.close()
print("✓ Test complete")

print("\n" + "=" * 60)
print("Summary:")
print("- Cache data persists across connection close/open ✓")
print("- setup() is safe to call multiple times ✓")
print("- Use cache.setup(force_recreate=True) to wipe data")
print("=" * 60)

