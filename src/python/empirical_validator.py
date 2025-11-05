"""Empirical validation of Bloom filter false positive rate."""
import random
import string
from typing import List
from bloom_filter import BloomFilter


class EmpiricalValidator:
    """Validate Bloom filter performance with random non-words."""

    def __init__(self, bloom_filter: BloomFilter, dictionary_words: List[str]):
        self.filter = bloom_filter
        self.word_set = set(dictionary_words)

    def run_validation(self, num_samples: int = 100000) -> dict:
        """Run empirical validation and return results."""
        false_positives = 0

        for _ in range(num_samples):
            random_str = self._generate_random_word()

            # Skip if it happens to be a real word
            if random_str in self.word_set:
                continue

            # Check if Bloom filter accepts it (false positive)
            if self.filter.check(random_str):
                false_positives += 1

        empirical_rate = false_positives / num_samples

        return {
            'samples': num_samples,
            'false_positives': false_positives,
            'empirical_rate': empirical_rate
        }

    def _generate_random_word(self, min_len: int = 3, max_len: int = 15) -> str:
        """Generate a random uppercase string."""
        length = random.randint(min_len, max_len)
        return ''.join(random.choices(string.ascii_uppercase, k=length))

    def print_validation(self, theoretical_fp_rate: float,
                        num_samples: int = 100000):
        """Run and print empirical validation."""
        print("\n" + "=" * 80)
        print("EMPIRICAL VALIDATION")
        print("=" * 80)
        print("Testing false positive rate with random non-words...")

        results = self.run_validation(num_samples)

        print(f"Random samples tested: {results['samples']:,}")
        print(f"False positives: {results['false_positives']:,}")
        print(f"Empirical FP rate: {results['empirical_rate'] * 100:.4f}%")
        print(f"Theoretical FP rate: {theoretical_fp_rate * 100:.4f}%")

        diff = abs(results['empirical_rate'] - theoretical_fp_rate)
        print(f"Difference: {diff * 100:.4f}%")

        if diff < 0.002:
            print("✓ Empirical rate matches theory!")
        else:
            print("⚠ Empirical rate differs from theory "
                  "(expected due to random sampling)")

        print("=" * 80)
