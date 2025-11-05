"""
C1541 disk geometry calculations for Bloom filter sizing.

Copyright (c) 2025 John Byrd
https://github.com/johnwbyrd/bloomer

SPDX-License-Identifier: BSD-3-Clause
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DiskGeometry:
    """Immutable C1541 disk geometry configuration."""

    total_sectors: int = 683
    directory_sectors: int = 19
    program_sectors: int = 20
    rel_overhead_sectors: int = 15
    bytes_per_sector: int = 256
    rel_record_size: int = 254

    @property
    def available_sectors(self) -> int:
        """Calculate sectors available for Bloom filter data."""
        return (self.total_sectors - self.directory_sectors -
                self.program_sectors - self.rel_overhead_sectors)

    @property
    def bloom_records(self) -> int:
        """Calculate number of REL records for Bloom filter."""
        return self.available_sectors * self.bytes_per_sector // self.rel_record_size

    @property
    def bloom_size_bytes(self) -> int:
        """Calculate Bloom filter size in bytes."""
        return self.bloom_records * self.rel_record_size

    @property
    def bloom_size_bits(self) -> int:
        """Calculate Bloom filter size in bits."""
        return self.bloom_size_bytes * 8

    def print_summary(self):
        """Print disk geometry summary."""
        print("=" * 80)
        print("C1541 DISK GEOMETRY")
        print("=" * 80)
        print(f"Total disk sectors: {self.total_sectors}")
        print(f"  - Directory/BAM: {self.directory_sectors} sectors")
        print(f"  - Program file: {self.program_sectors} sectors")
        print(f"  - REL side sectors: {self.rel_overhead_sectors} sectors")
        print(f"  = Available: {self.available_sectors} sectors")
        print()
        print(f"REL record size: {self.rel_record_size} bytes (CBM DOS max)")
        print(f"Records: {self.available_sectors} × {self.bytes_per_sector} ÷ "
              f"{self.rel_record_size} = {self.bloom_records}")
        print()
        print("BLOOM FILTER SIZE")
        print(f"  Bytes: {self.bloom_records} × {self.rel_record_size} = "
              f"{self.bloom_size_bytes:,} ({self.bloom_size_bytes / 1024:.2f} KB)")
        print(f"  Bits: {self.bloom_size_bytes} × 8 = {self.bloom_size_bits:,}")
        print("=" * 80)
        print()
