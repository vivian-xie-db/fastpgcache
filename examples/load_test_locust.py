"""
Load testing using Locust framework.
Provides a web UI for load testing and real-time metrics.

Installation:
    pip install locust

Usage:
    locust -f load_test_locust.py --host=http://localhost
    
Then open http://localhost:8089 in your browser
"""
from locust import User, task, between, events
from fastpgcache import FastPgCache
import random
import time

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'password',
}


class CacheUser(User):
    """Simulated user performing cache operations."""
    
    # Wait 0.1-1 second between tasks
    wait_time = between(0.1, 1.0)
    
    def on_start(self):
        """Initialize cache connection for this user."""
        # Each user gets their own connection with unique user ID
        user_id = f"locust_user_{id(self)}"
        self.cache = FastPgCache(
            **DB_CONFIG,
            user=user_id
        )
    
    def on_stop(self):
        """Clean up cache connection."""
        if hasattr(self, 'cache'):
            self.cache.close()
    
    @task(3)  # Weight: 3 (runs more often)
    def get_cached_value(self):
        """Test GET operation."""
        key = f"test_key_{random.randint(1, 1000)}"
        start_time = time.time()
        
        try:
            result = self.cache.get(key)
            response_time = (time.time() - start_time) * 1000  # ms
            
            # Report to Locust
            events.request.fire(
                request_type="GET",
                name="cache.get",
                response_time=response_time,
                response_length=len(str(result)) if result else 0,
                exception=None
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="GET",
                name="cache.get",
                response_time=response_time,
                response_length=0,
                exception=e
            )
    
    @task(2)  # Weight: 2
    def set_cached_value(self):
        """Test SET operation."""
        key = f"test_key_{random.randint(1, 1000)}"
        value = {
            "user": self.cache.user,
            "timestamp": time.time(),
            "data": "x" * random.randint(100, 1000)
        }
        start_time = time.time()
        
        try:
            self.cache.set(key, value, ttl=300)
            response_time = (time.time() - start_time) * 1000
            
            events.request.fire(
                request_type="SET",
                name="cache.set",
                response_time=response_time,
                response_length=len(str(value)),
                exception=None
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="SET",
                name="cache.set",
                response_time=response_time,
                response_length=0,
                exception=e
            )
    
    @task(1)  # Weight: 1 (runs less often)
    def check_exists(self):
        """Test EXISTS operation."""
        key = f"test_key_{random.randint(1, 1000)}"
        start_time = time.time()
        
        try:
            exists = self.cache.exists(key)
            response_time = (time.time() - start_time) * 1000
            
            events.request.fire(
                request_type="EXISTS",
                name="cache.exists",
                response_time=response_time,
                response_length=1,
                exception=None
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="EXISTS",
                name="cache.exists",
                response_time=response_time,
                response_length=0,
                exception=e
            )
    
    @task(1)
    def delete_cached_value(self):
        """Test DELETE operation."""
        key = f"test_key_{random.randint(1, 1000)}"
        start_time = time.time()
        
        try:
            deleted = self.cache.delete(key)
            response_time = (time.time() - start_time) * 1000
            
            events.request.fire(
                request_type="DELETE",
                name="cache.delete",
                response_time=response_time,
                response_length=1,
                exception=None
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="DELETE",
                name="cache.delete",
                response_time=response_time,
                response_length=0,
                exception=e
            )

