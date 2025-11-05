"""Bloom filter implementation."""
from typing import List
from bloom_config import BloomConfig
from hash_functions import ALL_HASH_FUNCTIONS


class BloomFilter:
    """Bloom filter for efficient set membership testing."""

    def __init__(self, config: BloomConfig):
        self.config = config
        self.data = bytearray(config.size_bytes)
        self._hash_functions = ALL_HASH_FUNCTIONS[:config.num_hash_functions]

    def _get_bit_positions(self, word: str) -> List[int]:
        """Calculate bit positions for a word using all hash functions."""
        positions = []
        for i, hash_func in enumerate(self._hash_functions):
            hash_val = hash_func(word, seed=i)
            bit_pos = hash_val % self.config.size_bits
            positions.append(bit_pos)
        return positions

    def add(self, word: str):
        """Add a word to the Bloom filter."""
        for bit_pos in self._get_bit_positions(word):
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            self.data[byte_idx] |= (1 << bit_idx)

    def check(self, word: str) -> bool:
        """Check if a word might be in the filter."""
        for bit_pos in self._get_bit_positions(word):
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            if (self.data[byte_idx] & (1 << bit_idx)) == 0:
                return False
        return True

    def build_from_words(self, words: List[str], progress_interval: int = 10000):
        """Build filter from word list with optional progress display."""
        print(f"Building Bloom filter ({self.config.size_bytes:,} bytes, "
              f"{self.config.num_hash_functions} hash functions)...")

        for idx, word in enumerate(words):
            if progress_interval and idx % progress_interval == 0:
                print(f"  Processing word {idx}/{len(words)}...")
            self.add(word)

        print("Bloom filter built successfully")

    @property
    def bits_set(self) -> int:
        """Count number of bits set in the filter."""
        return sum(bin(byte).count('1') for byte in self.data)

    @property
    def fill_rate(self) -> float:
        """Calculate actual fill rate (proportion of bits set)."""
        return self.bits_set / self.config.size_bits
