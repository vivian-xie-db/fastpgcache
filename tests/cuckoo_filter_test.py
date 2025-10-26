#!/usr/bin/env python3
"""
CuckooFilter Usage Example

This example demonstrates how to use the CuckooFilter class for
efficient membership queries and deletions.


"""
from fastpgcache import CuckooFilter
import time
import random
import string


def generate_random_string(length=10):
    """Generate a random string for testing."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def basic_usage_example():
    """Demonstrate basic CuckooFilter operations."""
    print("=== Basic CuckooFilter Usage ===")
    
    # Create a cuckoo filter for up to 10,000 items
    cf = CuckooFilter(capacity=10000)
    
    # Insert some items
    items = ["apple", "banana", "cherry", "date", "elderberry"]
    print(f"Inserting items: {items}")
    
    for item in items:
        success = cf.insert(item)
        print(f"Insert '{item}': {'✓' if success else '✗'}")
    
    print(f"\nFilter size: {len(cf)}")
    print(f"Filter stats: {cf.stats()}")
    
    # Check membership
    print("\n--- Membership Tests ---")
    test_items = items + ["grape", "kiwi"]  # Some exist, some don't
    
    for item in test_items:
        exists = cf.lookup(item)
        status = "✓ Found" if exists else "✗ Not found"
        print(f"Lookup '{item}': {status}")
    
    # Alternative syntax using 'in' operator
    print(f"\n'apple' in filter: {'apple' in cf}")
    print(f"'grape' in filter: {'grape' in cf}")
    
    # Delete an item
    print("\n--- Deletion Test ---")
    print(f"Deleting 'banana': {'✓' if cf.delete('banana') else '✗'}")
    print(f"'banana' in filter after deletion: {'banana' in cf}")
    print(f"Filter size after deletion: {len(cf)}")
    
    print()


def performance_example():
    """Demonstrate CuckooFilter performance with larger datasets."""
    print("=== Performance Example ===")
    
    # Create filter for 100K items
    cf = CuckooFilter(capacity=100000, fingerprint_size=12)  # Lower false positive rate
    
    # Generate test data
    print("Generating 50,000 random items...")
    items = [generate_random_string() for _ in range(50000)]
    
    # Measure insertion time
    start_time = time.time()
    successful_inserts = 0
    
    for item in items:
        if cf.insert(item):
            successful_inserts += 1
    
    insert_time = time.time() - start_time
    
    print(f"Inserted {successful_inserts:,} items in {insert_time:.3f} seconds")
    print(f"Insertion rate: {successful_inserts/insert_time:,.0f} items/second")
    
    # Measure lookup time
    print(f"\nTesting lookups on {len(items):,} items...")
    start_time = time.time()
    
    found_count = sum(1 for item in items if cf.lookup(item))
    
    lookup_time = time.time() - start_time
    
    print(f"Performed {len(items):,} lookups in {lookup_time:.3f} seconds")
    print(f"Lookup rate: {len(items)/lookup_time:,.0f} lookups/second")
    print(f"Found {found_count:,} items ({found_count/len(items)*100:.1f}%)")
    
    # Show statistics
    stats = cf.stats()
    print(f"\nFilter Statistics:")
    print(f"  Size: {stats['size']:,} items")
    print(f"  Load factor: {stats['load_factor']:.3f}")
    print(f"  Estimated false positive rate: {stats['estimated_fpr']:.6f}")
    print(f"  Bucket utilization: {stats['bucket_utilization']:.3f}")
    
    print()


def false_positive_demonstration():
    """Demonstrate false positives in cuckoo filters."""
    print("=== False Positive Demonstration ===")
    
    # Create a small filter to increase chance of false positives
    cf = CuckooFilter(capacity=1000, fingerprint_size=6)  # Higher FP rate
    
    # Insert known items
    known_items = [f"item_{i}" for i in range(500)]
    for item in known_items:
        cf.insert(item)
    
    # Test unknown items
    unknown_items = [f"unknown_{i}" for i in range(1000)]
    false_positives = 0
    
    for item in unknown_items:
        if cf.lookup(item):
            false_positives += 1
    
    actual_fpr = false_positives / len(unknown_items)
    estimated_fpr = cf.false_positive_rate()
    
    print(f"Tested {len(unknown_items):,} unknown items")
    print(f"False positives found: {false_positives}")
    print(f"Actual false positive rate: {actual_fpr:.6f}")
    print(f"Estimated false positive rate: {estimated_fpr:.6f}")
    print(f"Difference: {abs(actual_fpr - estimated_fpr):.6f}")
    
    print()


def filter_operations_example():
    """Demonstrate advanced filter operations."""
    print("=== Advanced Filter Operations ===")
    
    # Create filter
    cf = CuckooFilter(capacity=5000)
    
    # Add some items
    items = [f"user_{i}" for i in range(100)]
    for item in items:
        cf.insert(item)
    
    print(f"Original filter size: {len(cf)}")
    
    # Create a copy
    cf_copy = cf.copy()
    print(f"Copy size: {len(cf_copy)}")
    
    # Add more items to copy
    more_items = [f"admin_{i}" for i in range(50)]
    for item in more_items:
        cf_copy.insert(item)
    
    print(f"Copy size after additions: {len(cf_copy)}")
    
    # Clear original filter
    cf.clear()
    print(f"Original filter size after clear: {len(cf)}")
    
    # Test union (works with same configurations)
    cf1 = CuckooFilter(capacity=1000)
    cf2 = CuckooFilter(capacity=1000)
    
    # Add different items to each
    for i in range(10):
        cf1.insert(f"set1_item_{i}")
        cf2.insert(f"set2_item_{i}")
    
    # Create union
    cf_union = cf1.union(cf2)
    if cf_union:
        print(f"\nUnion successful!")
        print(f"Filter 1 size: {len(cf1)}")
        print(f"Filter 2 size: {len(cf2)}")
        print(f"Union size: {len(cf_union)}")
        
        # Test that union contains items from both filters
        print(f"Union contains 'set1_item_0': {'set1_item_0' in cf_union}")
        print(f"Union contains 'set2_item_0': {'set2_item_0' in cf_union}")
    else:
        print("Union failed - incompatible filter configurations")
    
    print()


def use_case_examples():
    """Show practical use cases for CuckooFilter."""
    print("=== Practical Use Cases ===")
    
    print("1. Web Crawler URL Deduplication")
    url_filter = CuckooFilter(capacity=1000000)  # 1M URLs
    
    def crawl_url(url):
        if url in url_filter:
            return f"Already crawled: {url}"
        else:
            url_filter.insert(url)
            return f"Crawling: {url}"
    
    urls = [
        "https://example.com/page1",
        "https://example.com/page2", 
        "https://example.com/page1",  # Duplicate
        "https://example.com/page3"
    ]
    
    for url in urls:
        print(f"  {crawl_url(url)}")
    
    print(f"  Total unique URLs: {len(url_filter)}")
    
    print("\n2. Cache Membership Tracking")
    cache_filter = CuckooFilter(capacity=10000)
    
    def is_cached(key):
        return key in cache_filter
    
    def cache_item(key):
        cache_filter.insert(key)
        print(f"  Cached: {key}")
    
    def evict_item(key):
        if cache_filter.delete(key):
            print(f"  Evicted: {key}")
        else:
            print(f"  Not in cache: {key}")
    
    # Simulate cache operations
    cache_item("user:123:profile")
    cache_item("user:456:settings")
    print(f"  Is user:123:profile cached? {is_cached('user:123:profile')}")
    evict_item("user:123:profile")
    print(f"  Is user:123:profile cached? {is_cached('user:123:profile')}")
    
    print("\n3. Blacklist Management")
    blacklist = CuckooFilter(capacity=50000)
    
    # Add some blocked IPs
    blocked_ips = ["192.168.1.100", "10.0.0.50", "172.16.0.10"]
    for ip in blocked_ips:
        blacklist.insert(ip)
    
    def is_blocked(ip):
        return ip in blacklist
    
    test_ips = ["192.168.1.100", "192.168.1.101", "10.0.0.50"]
    for ip in test_ips:
        status = "BLOCKED" if is_blocked(ip) else "ALLOWED"
        print(f"  IP {ip}: {status}")
    
    print()


def main():
    """Run all examples."""
    print("CuckooFilter Examples\n")
    print("=" * 50)
    
    basic_usage_example()
    performance_example()
    false_positive_demonstration()
    filter_operations_example()
    use_case_examples()
    
    print("=" * 50)
    print("Examples completed!")
    print("\nKey Benefits of CuckooFilter:")
    print("- Fast O(1) lookups and insertions")
    print("- Support for deletions (unlike Bloom filters)")
    print("- Configurable false positive rates")
    print("- Space efficient")
    print("- No external dependencies")


if __name__ == "__main__":
    main()
