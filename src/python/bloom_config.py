"""Bloom filter configuration."""
import math
from dataclasses import dataclass
from disk_geometry import DiskGeometry


@dataclass
class BloomConfig:
    """Bloom filter configuration combining disk geometry and hash settings."""

    geometry: DiskGeometry
    num_hash_functions: int = 5

    @property
    def size_bytes(self) -> int:
        """Bloom filter size in bytes."""
        return self.geometry.bloom_size_bytes

    @property
    def size_bits(self) -> int:
        """Bloom filter size in bits."""
        return self.geometry.bloom_size_bits

    @property
    def num_records(self) -> int:
        """Number of REL records."""
        return self.geometry.bloom_records

    def optimal_k(self, expected_words: int) -> float:
        """Calculate optimal number of hash functions for given word count."""
        return (self.size_bits / expected_words) * math.log(2)

    def print_summary(self, expected_words: int = 124000):
        """Print configuration summary."""
        self.geometry.print_summary()
        optimal = self.optimal_k(expected_words)
        print(f"Hash functions: {self.num_hash_functions}")
        print(f"Optimal k for ~{expected_words:,} words: (m/n) × ln(2) = {optimal:.2f}")
        print(f"Using k={self.num_hash_functions} (fewer disk reads per lookup)")
        print("=" * 80)
        print()
