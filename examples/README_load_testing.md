# Load Testing FastPgCache

This directory contains several load testing scripts for FastPgCache.

## Prerequisites

1. **Database Setup**: Make sure you have PostgreSQL running and the cache table set up:
   ```bash
   python admin_setup_cache.py --host localhost --user postgres --password yourpass
   ```

2. **Install Dependencies**:
   ```bash
   # For basic/advanced tests
   pip install fastpgcache
   
   # For Locust web-based testing
   pip install locust
   ```

## Load Testing Scripts

### 1. Basic Load Test (`load_test_basic.py`)

Simple threading-based load test with detailed statistics.

**Usage:**
```bash
python examples/load_test_basic.py
```

**Configuration:**
Edit the script to change:
- `NUM_THREADS`: Number of concurrent threads (default: 10)
- `OPERATIONS_PER_THREAD`: Operations per thread (default: 100)
- Database connection details

**Output:**
- Total operations per second
- Mean, median, min, max latency
- P50, P95, P99 percentiles
- Error count

### 2. Advanced Load Test (`load_test_advanced.py`)

Tests multiple workload patterns (read-heavy, write-heavy, balanced).

**Usage:**
```bash
python examples/load_test_advanced.py
```

**Features:**
- Multiple workload patterns
- Continuous operation for specified duration
- Realistic key distribution
- Random data sizes and TTLs

**Workload Patterns:**
- **Read-Heavy**: 80% reads, 15% writes, 5% deletes
- **Balanced**: 50% reads, 40% writes, 10% deletes
- **Write-Heavy**: 20% reads, 70% writes, 10% deletes

### 3. Locust Load Test (`load_test_locust.py`)

Web-based load testing with real-time metrics and graphs.

**Installation:**
```bash
pip install locust
```

**Usage:**
```bash
locust -f examples/load_test_locust.py --host=http://localhost
```

Then open http://localhost:8089 in your browser.

**Features:**
- Real-time web UI
- Adjustable number of users and spawn rate
- Live charts and metrics
- Export results to CSV
- Distributed testing support

**Web UI Controls:**
- Number of users to simulate
- Spawn rate (users started per second)
- Start/stop controls
- Real-time RPS and response time graphs

## Performance Benchmarking Tips

### 1. Baseline Testing
```python
from fastpgcache import FastPgCache
import time

cache = FastPgCache("postgresql://user:pass@localhost/mydb")

# Warmup
for i in range(100):
    cache.set(f"key_{i}", {"data": "test"})

# Benchmark
start = time.time()
for i in range(1000):
    cache.get(f"key_{i % 100}")
duration = time.time() - start

print(f"1000 reads in {duration:.2f}s = {1000/duration:.2f} ops/sec")
cache.close()
```

### 2. Connection Pool Testing

Test with different pool sizes:
```python
# Small pool
cache = FastPgCache(host="localhost", minconn=1, maxconn=5)

# Large pool
cache = FastPgCache(host="localhost", minconn=10, maxconn=50)
```

### 3. Comparison with Redis

Compare FastPgCache with Redis performance:
```python
import time
import redis
from fastpgcache import FastPgCache

# Test Redis
r = redis.Redis(host='localhost', port=6379)
start = time.time()
for i in range(10000):
    r.set(f"key_{i}", "value")
redis_time = time.time() - start

# Test FastPgCache
cache = FastPgCache("postgresql://user:pass@localhost/mydb")
start = time.time()
for i in range(10000):
    cache.set(f"key_{i}", "value")
pgcache_time = time.time() - start

print(f"Redis: {10000/redis_time:.2f} ops/sec")
print(f"FastPgCache: {10000/pgcache_time:.2f} ops/sec")
```

## Expected Performance

Typical results on modern hardware (local PostgreSQL):

| Operation | Latency (P50) | Latency (P95) | Throughput |
|-----------|---------------|---------------|------------|
| GET       | 0.5-2ms       | 2-5ms         | 1000+ ops/s |
| SET       | 1-3ms         | 3-8ms         | 800+ ops/s |
| DELETE    | 1-2ms         | 2-5ms         | 1000+ ops/s |
| EXISTS    | 0.5-1.5ms     | 1.5-3ms       | 1200+ ops/s |

**Note**: Performance varies based on:
- Network latency (local vs remote database)
- PostgreSQL configuration
- Hardware (CPU, RAM, SSD vs HDD)
- Connection pool size
- Concurrent load

## Optimization Tips

1. **Use Connection Pooling**:
   ```python
   cache = FastPgCache(minconn=10, maxconn=50)
   ```

2. **Batch Operations**:
   ```python
   # Multiple operations in one connection
   for i in range(100):
       cache.set(f"key_{i}", value)
   ```

3. **Regular Cleanup**:
   ```bash
   # Cron job for cleanup
   */5 * * * * python -c "from fastpgcache import FastPgCache; c=FastPgCache(...); c.cleanup(); c.close()"
   ```

4. **PostgreSQL Tuning**:
   ```sql
   -- Increase shared_buffers
   ALTER SYSTEM SET shared_buffers = '256MB';
   
   -- Increase max_connections if needed
   ALTER SYSTEM SET max_connections = 200;
   ```

5. **Monitor PostgreSQL**:
   ```sql
   -- Check cache table size
   SELECT pg_size_pretty(pg_total_relation_size('cache'));
   
   -- Check connection count
   SELECT count(*) FROM pg_stat_activity;
   ```

## Troubleshooting

### Connection Pool Exhaustion
```
psycopg2.pool.PoolError: connection pool exhausted
```
**Solution**: Increase `maxconn` or ensure connections are properly closed.

### Slow Queries
```sql
-- Enable slow query logging in PostgreSQL
ALTER SYSTEM SET log_min_duration_statement = 100;  -- Log queries > 100ms
```

### High Memory Usage
- Run `cache.cleanup()` regularly
- Consider reducing TTL values
- Monitor with: `SELECT count(*) FROM cache;`

## Resources

- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Locust Documentation](https://docs.locust.io/)
- [FastPgCache README](../README.md)

