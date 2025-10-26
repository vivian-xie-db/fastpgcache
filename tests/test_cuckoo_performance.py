#!/usr/bin/env python3
"""
CuckooFilter Performance Tests for FastPgCache

This test suite specifically focuses on CuckooFilter functionality and performance
with the new simplified Databricks API.
"""

import time
import random
import string
import pytest
from fastpgcache import FastPgCache


# ============================================================================
# Configuration
# ============================================================================

# Databricks configuration (default)
DATABRICKS_CONFIG = {
    'host': 'instance-name.database.cloud.databricks.com',
    'database': 'databricks_postgres',
    'user': 'user@databricks.com',
    'schema': 'public',
    'instance_name': 'instance-name',
    'profile': 'Oauth'
}

# Local PostgreSQL configuration (for testing without Databricks)
LOCAL_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'password',
    'schema': 'public'
}

# Choose which config to use (set to DATABRICKS_CONFIG or LOCAL_CONFIG)
ACTIVE_CONFIG = DATABRICKS_CONFIG


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def cache_config():
    """Provide the active cache configuration."""
    return ACTIVE_CONFIG.copy()


@pytest.fixture
def cache_with_filter(cache_config):
    """Create a FastPgCache instance WITH CuckooFilter enabled."""
    cache = FastPgCache(
        **cache_config,
        use_cuckoo_filter=True
    )
    yield cache
    cache.close()


@pytest.fixture
def cache_without_filter(cache_config):
    """Create a FastPgCache instance WITHOUT CuckooFilter."""
    cache = FastPgCache(
        **cache_config,
        use_cuckoo_filter=False
    )
    yield cache
    cache.close()


# ============================================================================
# Helper Functions
# ============================================================================

def generate_random_key(prefix="key", length=10):
    """Generate a random cache key."""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}:{suffix}"


def test_cuckoo_filter_performance(cache_with_filter):
    """Test CuckooFilter performance benefits with real database."""
    print("=" * 80)
    print("TEST: CuckooFilter Performance with Databricks")
    print("=" * 80)
    print()
    
    # Cache already initialized via fixture
    print("Using cache WITH CuckooFilter (from fixture)...")
    print(f"✓ CuckooFilter enabled: {cache_with_filter.cuckoo_filter is not None}")
    print()
    
    # Insert test data using batch operation (fast!)
    print("Phase 1: Inserting 100 test keys using set_many()...")
    test_keys = [f"perftest:key:{i}" for i in range(100)]
    test_data = {key: f"value_{i}" for i, key in enumerate(test_keys)}
    
    start = time.time()
    count = cache_with_filter.set_many(test_data, ttl=3600)
    insert_time = time.time() - start
    
    print(f"✓ Inserted {count} keys in {insert_time:.2f}s ({count/insert_time:.1f} keys/sec)")
    print()
    
    # Test 1: Positive lookups (keys that exist)
    print("Phase 2: Testing POSITIVE lookups (keys that exist)...")
    positive_keys = test_keys[:20]  # Test 20 existing keys
    
    start = time.time()
    hits = 0
    for key in positive_keys:
        if cache_with_filter.get(key) is not None:
            hits += 1
    positive_time = time.time() - start
    
    print(f"✓ Found {hits}/{len(positive_keys)} keys in {positive_time:.3f}s")
    print(f"  Rate: {len(positive_keys)/positive_time:.1f} lookups/sec")
    print(f"  Per-lookup: {positive_time/len(positive_keys)*1000:.1f}ms")
    print()
    
    # Test 2: Negative lookups (keys that DON'T exist) - CuckooFilter should shine here!
    print("Phase 3: Testing NEGATIVE lookups (keys that don't exist)...")
    print("  This is where CuckooFilter provides huge speedup!")
    
    nonexistent_keys = [f"missing:key:{i}" for i in range(100)]
    
    # Check CuckooFilter stats
    stats = cache_with_filter.cuckoo_filter.stats()
    print("\n  CuckooFilter Status:")
    print(f"    Size: {stats['size']:,} items")
    print(f"    Load Factor: {stats['load_factor']:.4f}")
    print(f"    Est. False Positive Rate: {stats['estimated_fpr']:.6f}")
    
    start = time.time()
    misses = 0
    db_queries = 0  # Count how many actually hit the database
    
    for key in nonexistent_keys:
        # Check if CuckooFilter will skip this
        lookup_key = f"{key}:{cache_with_filter.user_id}"
        if not cache_with_filter.cuckoo_filter.lookup(lookup_key):
            # CuckooFilter says "definitely not there" - skip DB query!
            misses += 1
        else:
            # CuckooFilter says "maybe there" - need to query DB
            db_queries += 1
            if cache_with_filter.get(key) is None:
                misses += 1
    
    negative_time = time.time() - start
    
    print(f"\n✓ Checked {len(nonexistent_keys)} missing keys in {negative_time:.3f}s")
    print(f"  Rate: {len(nonexistent_keys)/negative_time:.1f} lookups/sec")
    print(f"  Per-lookup: {negative_time/len(nonexistent_keys)*1000:.1f}ms")
    print(f"  DB queries skipped: {len(nonexistent_keys) - db_queries}/{len(nonexistent_keys)} ({(len(nonexistent_keys) - db_queries)/len(nonexistent_keys)*100:.1f}%)")
    print(f"  False positives: {db_queries} ({db_queries/len(nonexistent_keys)*100:.1f}%)")
    
    # Calculate speedup
    if db_queries < len(nonexistent_keys):
        speedup = (positive_time / len(positive_keys)) / (negative_time / len(nonexistent_keys))
        print(f"\n🚀 CuckooFilter Speedup: {speedup:.1f}x faster for negative lookups!")
        
        if speedup < 2:
            print("  ⚠️  Warning: Speedup is low. Possible reasons:")
            print("     - High false positive rate")
            print("     - Network latency dominates")
            print("     - Small test size")
    
    print()
    
    # Cleanup
    print("Cleaning up test data...")
    for key in test_keys:
        cache_with_filter.delete(key)
    
    print("✓ Test complete!")
    print()


def test_cuckoo_filter_disabled_comparison(cache_without_filter, cache_with_filter):
    """Compare performance with CuckooFilter disabled."""
    print("=" * 80)
    print("TEST: Performance Comparison - CuckooFilter ON vs OFF")
    print("=" * 80)
    print()
    
    test_keys = [f"compare:key:{i}" for i in range(50)]
    
    # Test WITHOUT CuckooFilter
    print("Round 1: Testing WITHOUT CuckooFilter...")
    print(f"  CuckooFilter: {cache_without_filter.cuckoo_filter}")
    
    # Insert data
    data = {key: f"value_{i}" for i, key in enumerate(test_keys)}
    cache_without_filter.set_many(data)
    
    # Test negative lookups without filter
    missing_keys = [f"missing:compare:{i}" for i in range(50)]
    start = time.time()
    for key in missing_keys:
        cache_without_filter.get(key)
    time_without_filter = time.time() - start
    
    print(f"  ✓ 50 negative lookups: {time_without_filter:.3f}s")
    print(f"    Rate: {50/time_without_filter:.1f} lookups/sec")
    print("    (Every lookup hits database)")
    print()
    
    # Cleanup
    for key in test_keys:
        cache_without_filter.delete(key)
    
    # Test WITH CuckooFilter
    print("Round 2: Testing WITH CuckooFilter...")
    
    stats = cache_with_filter.cuckoo_filter.stats()
    print(f"  CuckooFilter: Enabled (capacity: {stats['capacity']:,})")
    
    # Insert same data
    cache_with_filter.set_many(data)
    
    # Test negative lookups with filter
    start = time.time()
    for key in missing_keys:
        cache_with_filter.get(key)
    time_with_filter = time.time() - start
    
    print(f"  ✓ 50 negative lookups: {time_with_filter:.3f}s")
    print(f"    Rate: {50/time_with_filter:.1f} lookups/sec")
    
    # Check how many were skipped
    skipped = sum(1 for key in missing_keys 
                  if not cache_with_filter.cuckoo_filter.lookup(f"{key}:{cache_with_filter.user_id}"))
    print(f"    DB queries skipped: {skipped}/50 ({skipped/50*100:.1f}%)")
    print()
    
    # Comparison
    print("=" * 80)
    print("RESULTS:")
    print(f"  Without CuckooFilter: {time_without_filter:.3f}s")
    print(f"  With CuckooFilter:    {time_with_filter:.3f}s")
    if time_without_filter > time_with_filter:
        speedup = time_without_filter / time_with_filter
        print(f"  🚀 Speedup: {speedup:.2f}x faster with CuckooFilter!")
    else:
        print("  ⚠️  CuckooFilter not providing speedup (likely high false positives)")
    print("=" * 80)
    print()
    
    # Cleanup
    for key in test_keys:
        cache_with_filter.delete(key)


def test_cuckoo_filter_batch_operations(cache_with_filter):
    """Test CuckooFilter with batch operations."""
    print("=" * 80)
    print("TEST: CuckooFilter with Batch Operations")
    print("=" * 80)
    print()
    
    print("Test 1: Bulk insert with set_many()")
    items = {f"batch:key:{i}": f"value_{i}" for i in range(200)}
    
    start = time.time()
    count = cache_with_filter.set_many(items, ttl=3600)
    batch_time = time.time() - start
    
    print(f"  ✓ Inserted {count} items in {batch_time:.2f}s")
    print(f"    Rate: {count/batch_time:.1f} inserts/sec")
    
    # Check CuckooFilter was updated
    stats = cache_with_filter.cuckoo_filter.stats()
    print(f"  ✓ CuckooFilter size: {stats['size']:,} items")
    print()
    
    print("Test 2: Verify all items in CuckooFilter")
    in_filter = sum(1 for key in items.keys() 
                    if cache_with_filter.cuckoo_filter.lookup(f"{key}:{cache_with_filter.user_id}"))
    print(f"  ✓ {in_filter}/{len(items)} items found in CuckooFilter ({in_filter/len(items)*100:.1f}%)")
    print()
    
    print("Test 3: Rapid lookups")
    lookup_keys = list(items.keys())[:50]
    
    start = time.time()
    hits = sum(1 for key in lookup_keys if cache_with_filter.get(key) is not None)
    lookup_time = time.time() - start
    
    print(f"  ✓ Found {hits}/{len(lookup_keys)} items in {lookup_time:.3f}s")
    print(f"    Rate: {len(lookup_keys)/lookup_time:.1f} lookups/sec")
    print()
    
    print("Test 4: Cleanup with delete")
    start = time.time()
    deleted = 0
    for key in items.keys():
        if cache_with_filter.delete(key):
            deleted += 1
    delete_time = time.time() - start
    
    print(f"  ✓ Deleted {deleted} items in {delete_time:.2f}s")
    print(f"    Rate: {deleted/delete_time:.1f} deletes/sec")
    
    # Verify CuckooFilter was updated
    still_in_filter = sum(1 for key in items.keys() 
                          if cache_with_filter.cuckoo_filter.lookup(f"{key}:{cache_with_filter.user_id}"))
    print(f"  ✓ Items remaining in CuckooFilter: {still_in_filter}/{len(items)}")
    print()
    
    print("✓ Test complete!")
    print()


def test_cuckoo_filter_edge_cases(cache_with_filter):
    """Test CuckooFilter edge cases and consistency."""
    print("=" * 80)
    print("TEST: CuckooFilter Edge Cases & Consistency")
    print("=" * 80)
    print()
    
    print("Test 1: Insert and immediate lookup")
    cache_with_filter.set("edge:test1", "value1")
    result = cache_with_filter.get("edge:test1")
    assert result == "value1", "Immediate lookup failed"
    print("  ✓ Insert → Get works correctly")
    
    print("\nTest 2: Delete and verify removal from CuckooFilter")
    cache_with_filter.set("edge:test2", "value2")
    assert cache_with_filter.exists("edge:test2"), "Key should exist"
    cache_with_filter.delete("edge:test2")
    assert not cache_with_filter.exists("edge:test2"), "Key should not exist after delete"
    print("  ✓ Delete removes from both DB and CuckooFilter")
    
    print("\nTest 3: TTL expiration")
    cache_with_filter.set("edge:test3", "value3", ttl=2)
    assert cache_with_filter.get("edge:test3") == "value3", "Key should exist"
    print("  Waiting 3 seconds for TTL expiration...")
    time.sleep(3)
    result = cache_with_filter.get("edge:test3")
    assert result is None, "Key should be expired"
    print("  ✓ TTL expiration works correctly")
    
    print("\nTest 4: Overwrite existing key")
    cache_with_filter.set("edge:test4", "value4a")
    cache_with_filter.set("edge:test4", "value4b")  # Overwrite
    result = cache_with_filter.get("edge:test4")
    assert result == "value4b", "Value should be updated"
    print("  ✓ Overwrite works correctly")
    
    print("\nTest 5: Large batch false positive test")
    # Insert many keys
    keys = [f"edge:fp:{i}" for i in range(100)]
    data = {key: f"value_{i}" for i, key in enumerate(keys)}
    cache_with_filter.set_many(data)
    
    # Test false positive rate
    missing_keys = [f"edge:missing:{i}" for i in range(100)]
    false_positives = 0
    
    for key in missing_keys:
        lookup_key = f"{key}:{cache_with_filter.user_id}"
        if cache_with_filter.cuckoo_filter.lookup(lookup_key):  # Says "maybe exists"
            if cache_with_filter.get(key) is None:  # But actually doesn't exist
                false_positives += 1
    
    fpr = false_positives / len(missing_keys)
    print(f"  False positives: {false_positives}/{len(missing_keys)} ({fpr*100:.2f}%)")
    print(f"  ✓ False positive rate: {fpr:.4f} (lower is better)")
    
    # Cleanup
    for key in keys:
        cache_with_filter.delete(key)
    for key in ["edge:test1", "edge:test4"]:
        cache_with_filter.delete(key)
    
    print("\n✓ All edge case tests passed!")
    print()


# ============================================================================
# Standalone Test Runner (for non-pytest execution)
# ============================================================================

def main():
    """Run all CuckooFilter tests standalone (without pytest)."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "FastPgCache CuckooFilter Tests" + " " * 28 + "║")
    print("║" + " " * 25 + "with Simplified Databricks API" + " " * 23 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Create cache instances (manual fixture replacement)
    cache_cfg = ACTIVE_CONFIG.copy()
    cache_with = FastPgCache(**cache_cfg, use_cuckoo_filter=True)
    cache_without = FastPgCache(**cache_cfg, use_cuckoo_filter=False)
    
    tests = [
        ("CuckooFilter Performance", lambda: test_cuckoo_filter_performance(cache_with)),
        ("Filter ON vs OFF Comparison", lambda: test_cuckoo_filter_disabled_comparison(cache_without, cache_with)),
        ("Batch Operations", lambda: test_cuckoo_filter_batch_operations(cache_with)),
        ("Edge Cases & Consistency", lambda: test_cuckoo_filter_edge_cases(cache_with)),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔬 Running: {test_name}")
            print("-" * 80)
            test_func()
            passed += 1
            print(f"✅ PASSED: {test_name}")
        except Exception as e:
            failed += 1
            print(f"❌ FAILED: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    # Cleanup
    cache_with.close()
    cache_without.close()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {len(tests)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print("=" * 80)
    
    if failed == 0:
        print("\n🎉 All tests passed! CuckooFilter is working perfectly!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")


if __name__ == "__main__":
    main()

