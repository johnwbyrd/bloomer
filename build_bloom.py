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


# Configuration
WORD_LIST_URL = "https://norvig.com/ngrams/TWL06.txt"
WORD_LIST_CACHE = "TWL06.txt"
BLOOM_SIZE_BYTES = 160256  # 626 blocks * 256 bytes
BLOOM_SIZE_BITS = BLOOM_SIZE_BYTES * 8  # 1,282,048 bits
NUM_HASH_FUNCTIONS = 5


def download_word_list():
    """Download word list if not cached."""
    if os.path.exists(WORD_LIST_CACHE):
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
    print(f"Statistics: {bits_set}/{BLOOM_SIZE_BITS} bits set ({fill_rate:.2f}% full)")
    
    return bloom


def write_bloom_file(bloom, output_path):
    """Write Bloom filter to binary file."""
    with open(output_path, 'wb') as f:
        f.write(bloom)
    print(f"Bloom filter written to {output_path}")


def create_disk_image(prg_path, bloom_path, output_d64):
    """Create .d64 disk image with program and Bloom filter using raw format."""
    print(f"Creating disk image: {output_d64}")
    
    # D64 format constants
    D64_SIZE = 174848  # Standard D64 size in bytes
    SECTOR_SIZE = 256
    SECTORS_PER_TRACK = [
        0, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21,  # Tracks 1-10
        21, 21, 21, 21, 21, 21, 21, 19, 19, 19,     # Tracks 11-20
        19, 19, 19, 19, 18, 18, 18, 18, 18, 18,     # Tracks 21-30
        17, 17, 17, 17, 17                           # Tracks 31-35
    ]
    
    # Initialize empty disk
    disk = bytearray(D64_SIZE)
    
    # Track 18, Sector 0 is the BAM (Block Availability Map)
    bam_track = 18
    bam_sector = 0
    bam_offset = track_sector_to_offset(bam_track, bam_sector)
    
    # BAM header
    disk[bam_offset + 0] = 18  # Track of first directory sector
    disk[bam_offset + 1] = 1   # Sector of first directory sector
    disk[bam_offset + 2] = 0x41  # DOS version ('A')
    disk[bam_offset + 3] = 0    # Reserved
    
    # Initialize BAM entries for all tracks (mark all sectors as free)
    for track in range(1, 36):
        bam_entry_offset = bam_offset + 4 * track
        sectors_free = SECTORS_PER_TRACK[track]
        disk[bam_entry_offset] = sectors_free
        # Mark all sectors as free (bits set)
        disk[bam_entry_offset + 1] = 0xFF
        disk[bam_entry_offset + 2] = 0xFF
        disk[bam_entry_offset + 3] = 0xFF if sectors_free >= 16 else (1 << (sectors_free - 8)) - 1 if sectors_free > 8 else 0
    
    # Disk name and ID at offset 0x90 in BAM
    disk_name = b"SPELLCHECK      "  # 16 chars, padded with spaces
    disk_id = b"SK"
    disk[bam_offset + 0x90:bam_offset + 0xA0] = disk_name
    disk[bam_offset + 0xA0] = 0xA0  # Shifted space
    disk[bam_offset + 0xA1] = 0xA0  # Shifted space
    disk[bam_offset + 0xA2:bam_offset + 0xA4] = disk_id
    disk[bam_offset + 0xA4] = 0xA0  # Shifted space
    disk[bam_offset + 0xA5] = ord('2')
    disk[bam_offset + 0xA6] = ord('A')
    
    # Directory starts at Track 18, Sector 1
    dir_track = 18
    dir_sector = 1
    
    files_to_add = []
    
    # Add program file if exists
    if os.path.exists(prg_path):
        with open(prg_path, 'rb') as f:
            prg_data = f.read()
        files_to_add.append(('SPELLCHECK', prg_data, 0x82))  # PRG type
        print(f"Will add program: {prg_path} ({len(prg_data)} bytes)")
    else:
        print(f"Warning: Program file {prg_path} not found")
    
    # Add Bloom filter
    with open(bloom_path, 'rb') as f:
        bloom_data = f.read()
    files_to_add.append(('BLOOM.DAT', bloom_data, 0x81))  # SEQ type
    print(f"Will add Bloom filter: {bloom_path} ({len(bloom_data)} bytes)")
    
    # Allocate sectors for files and write them
    current_track = 1
    current_sector = 0
    
    dir_entries = []
    
    for filename, file_data, file_type in files_to_add:
        # Allocate first track/sector for this file
        start_track, start_sector = allocate_sector(disk, SECTORS_PER_TRACK, current_track, current_sector)
        first_track, first_sector = start_track, start_sector
        
        # Write file data in sectors
        offset = 0
        prev_track, prev_sector = None, None
        blocks_used = 0
        
        while offset < len(file_data):
            current_track, current_sector = allocate_sector(disk, SECTORS_PER_TRACK, current_track, current_sector)
            sector_offset = track_sector_to_offset(current_track, current_sector)
            
            # Amount of data to write in this sector (max 254 bytes, 2 bytes for link)
            chunk_size = min(254, len(file_data) - offset)
            
            # Write link to next sector (or 0,last_byte_count if last)
            if offset + chunk_size < len(file_data):
                # More data to come
                next_track, next_sector = find_free_sector(disk, SECTORS_PER_TRACK, current_track, current_sector)
                disk[sector_offset] = next_track
                disk[sector_offset + 1] = next_sector
            else:
                # Last sector
                disk[sector_offset] = 0
                disk[sector_offset + 1] = chunk_size + 1  # +1 because it includes the link bytes
            
            # Write data
            disk[sector_offset + 2:sector_offset + 2 + chunk_size] = file_data[offset:offset + chunk_size]
            
            offset += chunk_size
            blocks_used += 1
            current_sector += 1
        
        # Create directory entry
        dir_entries.append({
            'filename': filename,
            'file_type': file_type,
            'track': first_track,
            'sector': first_sector,
            'blocks': blocks_used
        })
        
        print(f"  Added '{filename}': {blocks_used} blocks")
    
    # Write directory entries
    write_directory(disk, dir_track, dir_sector, dir_entries)
    
    # Write disk image to file
    with open(output_d64, 'wb') as f:
        f.write(disk)
    
    print(f"\nDisk image created: {output_d64}")
    print(f"Total size: {len(disk)} bytes")
    
    # Calculate free blocks
    total_blocks = sum(SECTORS_PER_TRACK[1:])
    used_blocks = sum(e['blocks'] for e in dir_entries) + 2  # +2 for BAM and directory
    free_blocks = total_blocks - used_blocks
    print(f"Blocks free: {free_blocks}/{total_blocks}")
    
    return True


def track_sector_to_offset(track, sector):
    """Convert track/sector to byte offset in D64 image."""
    SECTORS_PER_TRACK = [
        0, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21,
        21, 21, 21, 21, 21, 21, 21, 19, 19, 19,
        19, 19, 19, 19, 18, 18, 18, 18, 18, 18,
        17, 17, 17, 17, 17
    ]
    offset = 0
    for t in range(1, track):
        offset += SECTORS_PER_TRACK[t] * 256
    offset += sector * 256
    return offset


def find_free_sector(disk, sectors_per_track, start_track, start_sector):
    """Find next free sector, avoiding track 18 (directory)."""
    track = start_track
    sector = start_sector
    
    while True:
        sector += 1
        if sector >= sectors_per_track[track]:
            sector = 0
            track += 1
            if track == 18:  # Skip directory track
                track = 19
            if track > 35:
                track = 1
        
        if track == start_track and sector == start_sector:
            raise Exception("Disk full!")
        
        if track != 18 and is_sector_free(disk, track, sector):
            return track, sector


def is_sector_free(disk, track, sector):
    """Check if a sector is marked as free in BAM."""
    bam_offset = track_sector_to_offset(18, 0)
    bam_entry_offset = bam_offset + 4 * track
    
    byte_index = sector // 8
    bit_index = sector % 8
    
    return (disk[bam_entry_offset + 1 + byte_index] & (1 << bit_index)) != 0


def allocate_sector(disk, sectors_per_track, start_track, start_sector):
    """Allocate a free sector and mark it as used in BAM."""
    track, sector = find_free_sector(disk, sectors_per_track, start_track, start_sector)
    
    # Mark as used in BAM
    bam_offset = track_sector_to_offset(18, 0)
    bam_entry_offset = bam_offset + 4 * track
    
    byte_index = sector // 8
    bit_index = sector % 8
    
    # Clear the bit (mark as used)
    disk[bam_entry_offset + 1 + byte_index] &= ~(1 << bit_index)
    
    # Decrement free sector count
    disk[bam_entry_offset] -= 1
    
    return track, sector


def write_directory(disk, dir_track, dir_sector, dir_entries):
    """Write directory entries to disk."""
    dir_offset = track_sector_to_offset(dir_track, dir_sector)
    
    # Directory link (no next directory sector)
    disk[dir_offset] = 0
    disk[dir_offset + 1] = 0xFF
    
    # Write each directory entry
    for i, entry in enumerate(dir_entries):
        if i >= 8:  # Only 8 entries per directory sector
            break
        
        entry_offset = dir_offset + 2 + (i * 32)
        
        # File type and flags
        disk[entry_offset] = entry['file_type']
        
        # Track/sector of first block
        disk[entry_offset + 1] = entry['track']
        disk[entry_offset + 2] = entry['sector']
        
        # Filename (16 bytes, padded with shifted spaces 0xA0)
        filename_bytes = entry['filename'][:16].encode('ascii')
        padded_name = filename_bytes + b'\xA0' * (16 - len(filename_bytes))
        disk[entry_offset + 3:entry_offset + 19] = padded_name
        
        # File size in blocks (little-endian)
        disk[entry_offset + 30] = entry['blocks'] & 0xFF
        disk[entry_offset + 31] = (entry['blocks'] >> 8) & 0xFF


def main():
    # Change to tools directory for relative paths
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    os.chdir(project_dir)
    
    # Download word list if needed
    download_word_list()
    
    # Load words
    words = load_words()
    
    # Build Bloom filter
    bloom = build_bloom_filter(words)
    
    # Write Bloom filter to build directory
    build_dir = Path('build')
    build_dir.mkdir(exist_ok=True)
    
    bloom_path = build_dir / 'bloom.dat'
    write_bloom_file(bloom, bloom_path)
    
    # Generate C header with configuration
    header_path = Path('src') / 'bloom_config.h'
    with open(header_path, 'w') as f:
        f.write(f"""/* Auto-generated Bloom filter configuration */
#ifndef BLOOM_CONFIG_H
#define BLOOM_CONFIG_H

#define BLOOM_SIZE_BYTES {BLOOM_SIZE_BYTES}UL
#define BLOOM_SIZE_BITS {BLOOM_SIZE_BITS}UL
#define NUM_HASH_FUNCTIONS {NUM_HASH_FUNCTIONS}
#define NUM_RECORDS {BLOOM_SIZE_BYTES // 256}

#endif /* BLOOM_CONFIG_H */
""")
    print(f"Generated configuration header: {header_path}")
    
    # Create disk image if program exists
    prg_path = build_dir / 'spellcheck.prg'
    d64_path = build_dir / 'spellcheck.d64'
    create_disk_image(prg_path, bloom_path, d64_path)
    
    print("\nBuild complete!")
    print(f"Expected false positive rate: ~1.1%")


if __name__ == '__main__':
    main()
