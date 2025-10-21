"""
Advanced load testing script with multiple workload patterns.
Tests different scenarios: read-heavy, write-heavy, mixed workloads.
"""
import time
import threading
import random
from fastpgcache import FastPgCache
from collections import defaultdict
import statistics

# Test configuration
HOST = "localhost"
DATABASE = "postgres"
USER = "postgres"
PASSWORD = "password"

# Workload patterns
WORKLOADS = {
    'read_heavy': {'get': 80, 'set': 15, 'delete': 5},     # 80% reads
    'write_heavy': {'get': 20, 'set': 70, 'delete': 10},   # 70% writes
    'balanced': {'get': 50, 'set': 40, 'delete': 10},       # 50/50
}


class LoadTester:
    """Advanced load tester with configurable workloads."""
    
    def __init__(self, workload_name='balanced', num_threads=10, 
                 duration_seconds=30, key_space_size=1000):
        self.workload_name = workload_name
        self.workload = WORKLOADS[workload_name]
        self.num_threads = num_threads
        self.duration = duration_seconds
        self.key_space_size = key_space_size
        
        # Results tracking
        self.results = defaultdict(list)
        self.operation_counts = defaultdict(int)
        self.errors = []
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
    
    def choose_operation(self):
        """Randomly choose an operation based on workload distribution."""
        rand = random.randint(1, 100)
        cumulative = 0
        for op, percentage in self.workload.items():
            cumulative += percentage
            if rand <= cumulative:
                return op
        return 'get'
    
    def worker_thread(self, thread_id):
        """Worker thread that runs operations continuously."""
        try:
            cache = FastPgCache(
                host=HOST,
                database=DATABASE,
                user=f"loadtest_user_{thread_id}",
                password=PASSWORD
            )
            
            while not self.stop_flag.is_set():
                operation = self.choose_operation()
                key = f"key_{random.randint(1, self.key_space_size)}"
                
                start = time.time()
                
                try:
                    if operation == 'set':
                        value = {
                            "thread": thread_id,
                            "timestamp": time.time(),
                            "data": "x" * random.randint(10, 1000)
                        }
                        cache.set(key, value, ttl=random.randint(60, 300))
                    
                    elif operation == 'get':
                        result = cache.get(key)
                        # Simulate some processing
                        if result:
                            _ = str(result)
                    
                    elif operation == 'delete':
                        cache.delete(key)
                    
                    duration = time.time() - start
                    
                    with self.lock:
                        self.results[operation].append(duration)
                        self.operation_counts[operation] += 1
                
                except Exception as e:
                    with self.lock:
                        self.errors.append(f"Thread {thread_id}, {operation}: {str(e)}")
                
                # Small random delay to simulate real-world usage
                time.sleep(random.uniform(0.001, 0.01))
            
            cache.close()
            
        except Exception as e:
            with self.lock:
                self.errors.append(f"Thread {thread_id} setup error: {str(e)}")
    
    def run(self):
        """Run the load test."""
        print(f"\n{'='*70}")
        print(f"LOAD TEST: {self.workload_name.upper()} WORKLOAD")
        print(f"{'='*70}")
        print(f"Threads: {self.num_threads}")
        print(f"Duration: {self.duration} seconds")
        print(f"Key space: {self.key_space_size} keys")
        print(f"Workload distribution: {self.workload}")
        print(f"\nStarting test...")
        
        # Start threads
        threads = []
        start_time = time.time()
        
        for i in range(self.num_threads):
            t = threading.Thread(target=self.worker_thread, args=(i,))
            threads.append(t)
            t.start()
        
        # Let test run for specified duration
        time.sleep(self.duration)
        
        # Signal threads to stop
        print(f"\nStopping test...")
        self.stop_flag.set()
        
        # Wait for threads to finish
        for t in threads:
            t.join()
        
        actual_duration = time.time() - start_time
        
        # Print results
        self.print_results(actual_duration)
    
    def print_results(self, duration):
        """Print detailed test results."""
        print(f"\n{'='*70}")
        print(f"RESULTS: {self.workload_name.upper()} WORKLOAD")
        print(f"{'='*70}")
        
        total_ops = sum(self.operation_counts.values())
        print(f"\nDuration: {duration:.2f} seconds")
        print(f"Total operations: {total_ops:,}")
        print(f"Throughput: {total_ops / duration:.2f} ops/sec")
        
        print(f"\nOperation breakdown:")
        for op, count in sorted(self.operation_counts.items()):
            percentage = (count / total_ops * 100) if total_ops > 0 else 0
            print(f"  {op.upper()}: {count:,} ({percentage:.1f}%)")
        
        print(f"\nLatency statistics (milliseconds):")
        for op in ['get', 'set', 'delete']:
            if op in self.results and self.results[op]:
                times = [t * 1000 for t in self.results[op]]
                sorted_times = sorted(times)
                
                print(f"\n  {op.upper()}:")
                print(f"    Mean: {statistics.mean(times):.2f} ms")
                print(f"    Median: {statistics.median(times):.2f} ms")
                print(f"    P95: {sorted_times[int(len(sorted_times) * 0.95)]:.2f} ms")
                print(f"    P99: {sorted_times[int(len(sorted_times) * 0.99)]:.2f} ms")
                print(f"    Min: {min(times):.2f} ms")
                print(f"    Max: {max(times):.2f} ms")
        
        if self.errors:
            print(f"\n⚠️  Errors: {len(self.errors)}")
            for error in self.errors[:5]:
                print(f"  - {error}")
        else:
            print(f"\n✅ No errors!")


def main():
    """Run all workload tests."""
    print("\nFastPgCache Advanced Load Testing")
    print("==================================")
    
    configs = [
        ('read_heavy', 10, 20),
        ('balanced', 10, 20),
        ('write_heavy', 10, 20),
    ]
    
    for workload, threads, duration in configs:
        tester = LoadTester(
            workload_name=workload,
            num_threads=threads,
            duration_seconds=duration,
            key_space_size=1000
        )
        tester.run()
        time.sleep(2)  # Brief pause between tests
    
    print(f"\n{'='*70}")
    print("ALL TESTS COMPLETED")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()

