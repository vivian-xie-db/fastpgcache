"""
Basic load testing script for FastPgCache using threading.
Tests concurrent reads/writes and measures performance.
"""
import time
import threading
from fastpgcache import FastPgCache
import random
import statistics

# Test configuration
NUM_THREADS = 10
OPERATIONS_PER_THREAD = 100
HOST = "localhost"
DATABASE = "postgres"
USER = "postgres"
PASSWORD = "password"

# Results storage
results = {
    'set_times': [],
    'get_times': [],
    'errors': []
}
results_lock = threading.Lock()


def worker_thread(thread_id):
    """Worker thread that performs cache operations."""
    try:
        # Each thread gets its own connection
        cache = FastPgCache(
            host=HOST,
            database=DATABASE,
            user=f"user_{thread_id}",  # Isolated cache per user
            password=PASSWORD
        )
        
        for i in range(OPERATIONS_PER_THREAD):
            key = f"test_key_{thread_id}_{i}"
            value = {
                "thread_id": thread_id,
                "iteration": i,
                "data": "x" * 100  # 100 bytes of data
            }
            
            # Test SET operation
            start = time.time()
            cache.set(key, value, ttl=300)
            set_duration = time.time() - start
            
            with results_lock:
                results['set_times'].append(set_duration)
            
            # Test GET operation
            start = time.time()
            retrieved = cache.get(key)
            get_duration = time.time() - start
            
            with results_lock:
                results['get_times'].append(get_duration)
            
            # Verify data integrity
            if retrieved != value:
                with results_lock:
                    results['errors'].append(f"Data mismatch in thread {thread_id}")
        
        cache.close()
        
    except Exception as e:
        with results_lock:
            results['errors'].append(f"Thread {thread_id} error: {str(e)}")


def print_statistics(name, times):
    """Print statistics for operation times."""
    if not times:
        print(f"{name}: No data")
        return
    
    times_ms = [t * 1000 for t in times]  # Convert to milliseconds
    print(f"\n{name} Statistics:")
    print(f"  Total operations: {len(times_ms)}")
    print(f"  Mean: {statistics.mean(times_ms):.2f} ms")
    print(f"  Median: {statistics.median(times_ms):.2f} ms")
    print(f"  Min: {min(times_ms):.2f} ms")
    print(f"  Max: {max(times_ms):.2f} ms")
    print(f"  Std Dev: {statistics.stdev(times_ms) if len(times_ms) > 1 else 0:.2f} ms")
    
    # Calculate percentiles
    sorted_times = sorted(times_ms)
    p50 = sorted_times[int(len(sorted_times) * 0.50)]
    p95 = sorted_times[int(len(sorted_times) * 0.95)]
    p99 = sorted_times[int(len(sorted_times) * 0.99)]
    print(f"  P50: {p50:.2f} ms")
    print(f"  P95: {p95:.2f} ms")
    print(f"  P99: {p99:.2f} ms")


def main():
    print(f"Starting load test...")
    print(f"Threads: {NUM_THREADS}")
    print(f"Operations per thread: {OPERATIONS_PER_THREAD}")
    print(f"Total operations: {NUM_THREADS * OPERATIONS_PER_THREAD * 2}")  # SET + GET
    print(f"\nRunning test...\n")
    
    # Start timer
    start_time = time.time()
    
    # Create and start threads
    threads = []
    for i in range(NUM_THREADS):
        t = threading.Thread(target=worker_thread, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Print results
    print("=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    
    total_ops = len(results['set_times']) + len(results['get_times'])
    print(f"\nTotal time: {total_time:.2f} seconds")
    print(f"Total operations: {total_ops}")
    print(f"Operations per second: {total_ops / total_time:.2f}")
    
    print_statistics("SET Operations", results['set_times'])
    print_statistics("GET Operations", results['get_times'])
    
    if results['errors']:
        print(f"\n⚠️  Errors encountered: {len(results['errors'])}")
        for error in results['errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")
    else:
        print("\n✅ No errors encountered!")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

