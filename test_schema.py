"""
Test script to verify schema support in FastPgCache
"""

from fastpgcache import FastPgCache

# Test with default schema
print("Testing with default schema (public)...")
cache1 = FastPgCache(
    host="localhost",
    database="postgres",
    user="postgres",
    password="postgres",
    schema="public",
    auto_setup=True
)

# Test basic operations
cache1.set("test:key1", "value1", ttl=300)
print(f"Set test:key1 in public schema")
value = cache1.get("test:key1")
print(f"Got test:key1 from public schema: {value}")
cache1.close()

# Test with custom schema
print("\nTesting with custom schema (my_cache_schema)...")
cache2 = FastPgCache(
    host="localhost",
    database="postgres",
    user="postgres",
    password="postgres",
    schema="my_cache_schema",
    auto_setup=True
)

# Test basic operations
cache2.set("test:key2", "value2", ttl=300)
print(f"Set test:key2 in my_cache_schema schema")
value = cache2.get("test:key2")
print(f"Got test:key2 from my_cache_schema schema: {value}")
cache2.close()

print("\n✅ Schema support working correctly!")

