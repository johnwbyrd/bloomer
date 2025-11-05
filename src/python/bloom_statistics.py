"""Bloom filter statistics calculation and display."""
import math
from bloom_filter import BloomFilter


class BloomStatistics:
    """Calculate and display Bloom filter statistics."""

    def __init__(self, bloom_filter: BloomFilter, word_count: int):
        self.filter = bloom_filter
        self.word_count = word_count

    def theoretical_fill_rate(self) -> float:
        """Calculate theoretical fill rate: 1 - e^(-kn/m)."""
        k = self.filter.config.num_hash_functions
        n = self.word_count
        m = self.filter.config.size_bits
        exponent = -k * n / m
        return 1 - math.exp(exponent)

    def false_positive_rate(self) -> float:
        """Calculate false positive rate: (1 - e^(-kn/m))^k."""
        return self.theoretical_fill_rate() ** self.filter.config.num_hash_functions

    def optimal_k(self) -> float:
        """Calculate optimal k for minimum FP rate."""
        m = self.filter.config.size_bits
        n = self.word_count
        return (m / n) * math.log(2)

    def optimal_fp_rate(self) -> float:
        """Calculate FP rate if using optimal k."""
        k_opt = round(self.optimal_k())
        m = self.filter.config.size_bits
        n = self.word_count
        fill = 1 - math.exp(-k_opt * n / m)
        return fill ** k_opt

    def print_statistics(self):
        """Print comprehensive statistics."""
        n = self.word_count
        k = self.filter.config.num_hash_functions
        m = self.filter.config.size_bits

        actual_fill = self.filter.fill_rate
        theoretical_fill = self.theoretical_fill_rate()
        fp_rate = self.false_positive_rate()

        print("\n=== BLOOM FILTER STATISTICS ===")
        print(f"Words inserted (n): {n:,}")
        print(f"Bits in filter (m): {m:,}")
        print(f"Hash functions (k): {k}")
        print(f"Bits per word (m/n): {m/n:.2f}")
        print(f"\nActual bits set: {self.filter.bits_set:,} / {m:,} "
              f"({actual_fill * 100:.2f}%)")
        print(f"Theoretical fill rate: {theoretical_fill * 100:.2f}%")
        print(f"Difference: {abs(actual_fill - theoretical_fill) * 100:.2f}%")
        print(f"\nFalse positive rate: {fp_rate * 100:.4f}% "
              f"(1 in {1/fp_rate:.0f})")
        print(f"Formula: (1 - e^(-{k}×{n}/{m}))^{k} = {fp_rate:.6f}")

        optimal_k = self.optimal_k()
        print(f"\nOptimal k for minimum FP rate: {optimal_k:.2f}")
        if abs(optimal_k - k) > 1:
            k_opt_int = round(optimal_k)
            opt_fp = self.optimal_fp_rate()
            print(f"With k={k_opt_int}: FP rate would be {opt_fp * 100:.4f}%")
            print(f"Trade-off: Using k={k} reduces disk I/O "
                  "(fewer sector reads per word)")
