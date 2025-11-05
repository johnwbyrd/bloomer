#!/usr/bin/env python3
"""
Build Bloom filter from TWL06 word list and create C64 disk image.
"""
import os
import sys
import struct
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests module required. Install with: pip install requests")
    sys.exit(1)

try:
    import d64
except ImportError:
    print("Error: d64 module required. Install with: pip install d64")
    sys.exit(1)


# Configuration
WORD_LIST_URL = "https://norvig.com/ngrams/TWL06.txt"
BLOOM_SIZE_BYTES = 160256  # 626 blocks * 256 bytes
BLOOM_SIZE_BITS = BLOOM_SIZE_BYTES * 8  # 1,282,048 bits
NUM_HASH_FUNCTIONS = 5

# Directory structure
BUILD_DIR = Path('build')
CACHE_DIR = BUILD_DIR / 'cache'
GENERATED_DIR = BUILD_DIR / 'generated'
ARTIFACTS_DIR = BUILD_DIR / 'artifacts'

WORD_LIST_CACHE = CACHE_DIR / 'TWL06.txt'


def download_word_list():
    """Download word list if not cached."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if WORD_LIST_CACHE.exists():
        print(f"Using cached word list: {WORD_LIST_CACHE}")
        return

    print(f"Downloading word list from {WORD_LIST_URL}...")
    response = requests.get(WORD_LIST_URL)
    response.raise_for_status()

    with open(WORD_LIST_CACHE, 'wb') as f:
        f.write(response.content)
    print(f"Word list downloaded and cached to {WORD_LIST_CACHE}")


def load_words():
    """Load words from the word list file."""
    with open(WORD_LIST_CACHE, 'r', encoding='utf-8') as f:
        words = [line.strip().upper() for line in f if line.strip()]
    print(f"Loaded {len(words)} words from word list")
    return words


def hash_fnv1a(word, seed=0):
    """FNV-1a hash function."""
    hash_val = 2166136261 + seed
    for char in word:
        hash_val ^= ord(char)
        hash_val = (hash_val * 16777619) & 0xFFFFFFFF
    return hash_val


def hash_djb2(word, seed=0):
    """DJB2 hash function."""
    hash_val = 5381 + seed
    for char in word:
        hash_val = ((hash_val << 5) + hash_val + ord(char)) & 0xFFFFFFFF
    return hash_val


def hash_sdbm(word, seed=0):
    """SDBM hash function."""
    hash_val = seed
    for char in word:
        hash_val = (ord(char) + (hash_val << 6) + (hash_val << 16) - hash_val) & 0xFFFFFFFF
    return hash_val


def hash_jenkins(word, seed=0):
    """Jenkins one-at-a-time hash."""
    hash_val = seed
    for char in word:
        hash_val += ord(char)
        hash_val = (hash_val + (hash_val << 10)) & 0xFFFFFFFF
        hash_val ^= (hash_val >> 6)
    hash_val = (hash_val + (hash_val << 3)) & 0xFFFFFFFF
    hash_val ^= (hash_val >> 11)
    hash_val = (hash_val + (hash_val << 15)) & 0xFFFFFFFF
    return hash_val


def hash_murmur(word, seed=0):
    """Simplified Murmur-inspired hash."""
    hash_val = seed + 0x9747b28c
    for char in word:
        hash_val ^= ord(char)
        hash_val = (hash_val * 0x5bd1e995) & 0xFFFFFFFF
        hash_val ^= (hash_val >> 15)
    return hash_val


HASH_FUNCTIONS = [
    hash_fnv1a,
    hash_djb2,
    hash_sdbm,
    hash_jenkins,
    hash_murmur
]


def get_bit_positions(word):
    """Calculate bit positions for a word using all hash functions."""
    positions = []
    for i, hash_func in enumerate(HASH_FUNCTIONS):
        hash_val = hash_func(word, seed=i)
        bit_pos = hash_val % BLOOM_SIZE_BITS
        positions.append(bit_pos)
    return positions


def build_bloom_filter(words):
    """Build Bloom filter bit array from word list."""
    # Initialize bit array
    bloom = bytearray(BLOOM_SIZE_BYTES)

    print(f"Building Bloom filter ({BLOOM_SIZE_BYTES} bytes, {NUM_HASH_FUNCTIONS} hash functions)...")

    for idx, word in enumerate(words):
        if idx % 10000 == 0:
            print(f"  Processing word {idx}/{len(words)}...")

        positions = get_bit_positions(word)
        for bit_pos in positions:
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            bloom[byte_idx] |= (1 << bit_idx)

    print("Bloom filter built successfully")

    # Calculate actual bits set for statistics
    bits_set = sum(bin(byte).count('1') for byte in bloom)
    fill_rate = (bits_set / BLOOM_SIZE_BITS) * 100

    # Calculate false positive probability: (bits_set / total_bits) ^ num_hash_functions
    false_positive_rate = (bits_set / BLOOM_SIZE_BITS) ** NUM_HASH_FUNCTIONS * 100

    print(f"Statistics: {bits_set}/{BLOOM_SIZE_BITS} bits set ({fill_rate:.2f}% full)")
    print(f"Expected false positive rate: {false_positive_rate:.2f}%")

    return bloom, len(words), false_positive_rate


def write_bloom_file(bloom, output_path):
    """Write Bloom filter to binary file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(bloom)
    print(f"Bloom filter written to {output_path}")


def create_disk_image(prg_path, bloom_path, output_d64):
    """Create .d64 disk image with program and Bloom filter using d64 library."""
    print(f"Creating disk image: {output_d64}")

    output_d64.parent.mkdir(parents=True, exist_ok=True)

    # Create a new D64 disk image
    d64.DiskImage.create('d64', output_d64, b'SPELLCHECK', b'SK')

    # Add files to the disk
    with d64.DiskImage(output_d64, mode='w') as img:
        # Add program file if it exists
        if prg_path.exists():
            print(f"Adding program: {prg_path} ({prg_path.stat().st_size} bytes)")
            p = img.path(b'SPELLCHECK')
            with p.open('w', ftype='prg') as f:
                with open(prg_path, 'rb') as src:
                    f.write(src.read())
        else:
            print(f"Warning: Program file {prg_path} not found")

        # Add Bloom filter data file as REL file with 254-byte records
        # Note: CBM DOS REL files support record lengths 1-254 only
        print(f"Adding Bloom filter: {bloom_path} ({bloom_path.stat().st_size} bytes)")
        p = img.path(b'BLOOM.DAT')
        with p.open('w', ftype='rel', record_len=254) as f:
            with open(bloom_path, 'rb') as src:
                f.write(src.read())

    # Display directory listing
    print(f"\nDisk image created: {output_d64}")
    with d64.DiskImage(output_d64) as img:
        for line in img.directory():
            print(line)

    return True


def main():
    # Change to project directory for relative paths
    script_dir = Path(__file__).parent
    # Handle being in src/python/ subdirectory
    if script_dir.name == 'python':
        project_dir = script_dir.parent.parent
    elif script_dir.name == 'tools':
        project_dir = script_dir.parent
    else:
        project_dir = script_dir
    os.chdir(project_dir)
    
    # Download word list if needed
    download_word_list()
    
    # Load words
    words = load_words()

    # Build Bloom filter
    bloom, word_count, false_positive_rate = build_bloom_filter(words)

    # Write Bloom filter to generated directory
    bloom_path = GENERATED_DIR / 'bloom.dat'
    write_bloom_file(bloom, bloom_path)

    # Generate C header with configuration
    header_path = GENERATED_DIR / 'bloom_config.h'
    header_path.parent.mkdir(parents=True, exist_ok=True)
    with open(header_path, 'w') as f:
        f.write(f"""/* Auto-generated Bloom filter configuration */
#ifndef BLOOM_CONFIG_H
#define BLOOM_CONFIG_H

#define BLOOM_SIZE_BYTES {BLOOM_SIZE_BYTES}UL
#define BLOOM_SIZE_BITS {BLOOM_SIZE_BITS}UL
#define NUM_HASH_FUNCTIONS {NUM_HASH_FUNCTIONS}
#define NUM_RECORDS {BLOOM_SIZE_BYTES // 254}
#define DICT_INFO "dictionary: {word_count} words\\naccuracy: ~{false_positive_rate:.2f}% fpr\\nready to check your spelling!\\n\\n"

#endif /* BLOOM_CONFIG_H */
""")
    print(f"Generated configuration header: {header_path}")

    # Create disk image if program exists
    prg_path = ARTIFACTS_DIR / 'spellcheck.prg'
    d64_path = ARTIFACTS_DIR / 'spellcheck.d64'
    create_disk_image(prg_path, bloom_path, d64_path)
    
    print("\nBuild complete!")
    print(f"Expected false positive rate: ~1.1%")


if __name__ == '__main__':
    main()
