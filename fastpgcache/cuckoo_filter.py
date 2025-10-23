"""
CuckooFilter - A probabilistic data structure for set membership queries

A Cuckoo Filter is a space-efficient probabilistic data structure that is used
to test whether an element is a member of a set, like a Bloom filter does.
Unlike Bloom filters, cuckoo filters support deletion of elements.


"""

import hashlib
import random
from typing import Union, Optional


class CuckooFilter:
    """
    A Cuckoo Filter implementation using only native Python modules.
    
    Args:
        capacity: Expected number of elements (default: 1000000)
        bucket_size: Number of entries per bucket (default: 4)
        fingerprint_size: Size of fingerprint in bits (default: 8)
        max_displacements: Maximum displacements during insertion (default: 500)
        
    Example:
        >>> cf = CuckooFilter(capacity=100000)
        >>> cf.insert("hello")
        True
        >>> cf.lookup("hello")
        True
        >>> cf.lookup("world")
        False
        >>> cf.delete("hello")
        True
        >>> cf.lookup("hello")
        False
    """
    
    def __init__(
        self, 
        capacity: int = 1000000,
        bucket_size: int = 4,
        fingerprint_size: int = 8,
        max_displacements: int = 500
    ):
        """
        Initialize the Cuckoo Filter.
        
        Args:
            capacity: Expected number of elements
            bucket_size: Number of fingerprints per bucket (affects performance vs space)
            fingerprint_size: Size of fingerprint in bits (affects false positive rate)
            max_displacements: Maximum displacements before giving up on insertion
        """
        self.bucket_size = bucket_size
        self.fingerprint_size = fingerprint_size
        self.max_displacements = max_displacements
        
        # Calculate number of buckets
        self.num_buckets = max(1, capacity // bucket_size)
        
        # Initialize buckets - each bucket holds up to bucket_size fingerprints
        self.buckets = [[] for _ in range(self.num_buckets)]
        
        # Track statistics
        self.size = 0
        self.max_size = capacity
        
        # Fingerprint mask for the specified bit size
        self.fingerprint_mask = (1 << fingerprint_size) - 1
        
        # Ensure fingerprints are never 0 (0 means empty)
        if self.fingerprint_mask == 0:
            self.fingerprint_mask = 1
    
    def _primary_hash(self, item: Union[str, bytes, int]) -> int:
        """Primary hash function."""
        if isinstance(item, str):
            item = item.encode('utf-8')
        elif isinstance(item, int):
            item = str(item).encode('utf-8')
        
        return int.from_bytes(
            hashlib.md5(item).digest()[:4], 
            byteorder='big'
        ) % self.num_buckets

    def _fingerprint(self, item: Union[str, bytes, int]) -> int:
        """
        Generate fingerprint for an item.
        
        The fingerprint is a small bit string derived from the item.
        It must never be 0 (which represents empty).
        """
        if isinstance(item, str):
            item = item.encode('utf-8')
        elif isinstance(item, int):
            item = str(item).encode('utf-8')
        
        # Use SHA-256 for fingerprint generation
        fp = int.from_bytes(
            hashlib.sha256(item).digest()[:4], 
            byteorder='big'
        ) & self.fingerprint_mask
        
        # Ensure fingerprint is never 0
        return fp if fp != 0 else 1
    
    def _alt_index(self, index: int, fingerprint: int) -> int:
        """
        Calculate alternate bucket index using current index and fingerprint.
        
        This implements the core of cuckoo hashing where an item can be
        placed in one of two positions.
        """
        # XOR with fingerprint to get alternate position
        alt = index ^ self._hash_fingerprint(fingerprint)
        return alt % self.num_buckets
    
    def _hash_fingerprint(self, fingerprint: int) -> int:
        """Hash a fingerprint to get alternate bucket calculation."""
        # Simple hash of the fingerprint
        return hash(fingerprint) & 0x7FFFFFFF
    
    def insert(self, item: Union[str, bytes, int]) -> bool:
        """
        Insert an item into the cuckoo filter.
        
        Args:
            item: Item to insert (string, bytes, or integer)
            
        Returns:
            True if insertion successful, False if filter is full
            
        Example:
            >>> cf = CuckooFilter()
            >>> cf.insert("hello")
            True
            >>> cf.insert(12345)
            True
        """
        fingerprint = self._fingerprint(item)
        index1 = self._primary_hash(item)
        index2 = self._alt_index(index1, fingerprint)
        
        # Try to insert in first bucket
        if len(self.buckets[index1]) < self.bucket_size:
            self.buckets[index1].append(fingerprint)
            self.size += 1
            return True
        
        # Try to insert in second bucket
        if len(self.buckets[index2]) < self.bucket_size:
            self.buckets[index2].append(fingerprint)
            self.size += 1
            return True
        
        # Both buckets full, try cuckoo eviction
        return self._cuckoo_insert(fingerprint, index1)
    
    def _cuckoo_insert(self, fingerprint: int, start_index: int) -> bool:
        """
        Perform cuckoo insertion with eviction.
        
        When both candidate buckets are full, randomly evict an item
        and try to relocate it. This process continues until either
        all items find a place or max_displacements is reached.
        """
        current_fp = fingerprint
        current_index = start_index
        
        for _ in range(self.max_displacements):
            # Pick random bucket between the two candidates
            if random.random() < 0.5:
                candidate_index = current_index
            else:
                candidate_index = self._alt_index(current_index, current_fp)
            
            # Bucket must be full (otherwise we wouldn't be here)
            if len(self.buckets[candidate_index]) < self.bucket_size:
                self.buckets[candidate_index].append(current_fp)
                self.size += 1
                return True
            
            # Evict random item from the chosen bucket
            evict_pos = random.randint(0, len(self.buckets[candidate_index]) - 1)
            evicted_fp = self.buckets[candidate_index][evict_pos]
            self.buckets[candidate_index][evict_pos] = current_fp
            
            # Now try to reinsert the evicted fingerprint
            current_fp = evicted_fp
            current_index = self._alt_index(candidate_index, evicted_fp)
        
        # Failed to insert after max_displacements
        return False
    
    def lookup(self, item: Union[str, bytes, int]) -> bool:
        """
        Check if an item might be in the filter.
        
        Args:
            item: Item to look up
            
        Returns:
            True if item might be in the set (could be false positive)
            False if item is definitely not in the set
            
        Example:
            >>> cf = CuckooFilter()
            >>> cf.insert("hello")
            True
            >>> cf.lookup("hello")
            True
            >>> cf.lookup("world")
            False
        """
        fingerprint = self._fingerprint(item)
        index1 = self._primary_hash(item)
        index2 = self._alt_index(index1, fingerprint)
        
        # Check both candidate buckets
        return (fingerprint in self.buckets[index1] or 
                fingerprint in self.buckets[index2])
    
    def delete(self, item: Union[str, bytes, int]) -> bool:
        """
        Delete an item from the filter.
        
        Args:
            item: Item to delete
            
        Returns:
            True if item was found and deleted, False otherwise
            
        Example:
            >>> cf = CuckooFilter()
            >>> cf.insert("hello")
            True
            >>> cf.delete("hello")
            True
            >>> cf.lookup("hello")
            False
        """
        fingerprint = self._fingerprint(item)
        index1 = self._primary_hash(item)
        index2 = self._alt_index(index1, fingerprint)
        
        # Try to remove from first bucket
        if fingerprint in self.buckets[index1]:
            self.buckets[index1].remove(fingerprint)
            self.size -= 1
            return True
        
        # Try to remove from second bucket
        if fingerprint in self.buckets[index2]:
            self.buckets[index2].remove(fingerprint)
            self.size -= 1
            return True
        
        return False
    
    def __contains__(self, item: Union[str, bytes, int]) -> bool:
        """Support 'in' operator."""
        return self.lookup(item)
    
    def __len__(self) -> int:
        """Return current number of items in filter."""
        return self.size
    
    def load_factor(self) -> float:
        """Calculate current load factor (0.0 to 1.0)."""
        total_slots = self.num_buckets * self.bucket_size
        return self.size / total_slots if total_slots > 0 else 0.0
    
    def false_positive_rate(self) -> float:
        """
        Estimate current false positive rate.
        
        The false positive rate depends on load factor and fingerprint size.
        This is an approximation based on theoretical analysis.
        """
        load = self.load_factor()
        if load == 0:
            return 0.0
        
        # Theoretical formula: roughly 2^(-fingerprint_size) * load_factor
        base_fpr = 1.0 / (1 << self.fingerprint_size)
        return min(base_fpr * load * 2, 1.0)  # Cap at 100%
    
    def stats(self) -> dict:
        """
        Get filter statistics.
        
        Returns:
            Dictionary with filter statistics including size, load factor,
            estimated false positive rate, and bucket utilization.
        """
        total_slots = self.num_buckets * self.bucket_size
        filled_buckets = sum(1 for bucket in self.buckets if bucket)
        
        return {
            'size': self.size,
            'capacity': self.max_size,
            'num_buckets': self.num_buckets,
            'bucket_size': self.bucket_size,
            'fingerprint_size': self.fingerprint_size,
            'total_slots': total_slots,
            'load_factor': self.load_factor(),
            'estimated_fpr': self.false_positive_rate(),
            'filled_buckets': filled_buckets,
            'bucket_utilization': filled_buckets / self.num_buckets if self.num_buckets > 0 else 0
        }
    
    def clear(self):
        """Clear all items from the filter."""
        self.buckets = [[] for _ in range(self.num_buckets)]
        self.size = 0
    
    def copy(self) -> 'CuckooFilter':
        """Create a copy of the filter."""
        new_filter = CuckooFilter(
            capacity=self.max_size,
            bucket_size=self.bucket_size,
            fingerprint_size=self.fingerprint_size,
            max_displacements=self.max_displacements
        )
        
        # Deep copy buckets
        new_filter.buckets = [bucket.copy() for bucket in self.buckets]
        new_filter.size = self.size
        
        return new_filter
    
    def union(self, other: 'CuckooFilter') -> Optional['CuckooFilter']:
        """
        Create union of two cuckoo filters.
        
        Note: This only works correctly if both filters have the same
        configuration (bucket_size, fingerprint_size, etc.)
        """
        if (self.bucket_size != other.bucket_size or 
            self.fingerprint_size != other.fingerprint_size or
            self.num_buckets != other.num_buckets):
            return None  # Cannot union filters with different configurations
        
        result = self.copy()
        
        # Add all fingerprints from other filter
        for i, bucket in enumerate(other.buckets):
            for fingerprint in bucket:
                # Try to add to result, but we can't guarantee it will fit
                if len(result.buckets[i]) < result.bucket_size:
                    result.buckets[i].append(fingerprint)
                    result.size += 1
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the filter."""
        stats = self.stats()
        return (f"CuckooFilter(size={stats['size']}, "
                f"load_factor={stats['load_factor']:.3f}, "
                f"est_fpr={stats['estimated_fpr']:.6f})")
