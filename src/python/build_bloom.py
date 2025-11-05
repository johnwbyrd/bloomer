#!/usr/bin/env python3
"""
Build Bloom filter from SCOWL word list and create C64 disk image.

Copyright (c) 2025 John Byrd
https://github.com/johnwbyrd/bloomer

SPDX-License-Identifier: BSD-3-Clause
"""
import os
import sys
from pathlib import Path

# Import our modules
from disk_geometry import DiskGeometry
from bloom_config import BloomConfig
from bloom_filter import BloomFilter
from bloom_statistics import BloomStatistics
from empirical_validator import EmpiricalValidator
from scowl_downloader import SCOWLDownloader
from scowl_parser import SCOWLParser
from header_generator import CHeaderGenerator
from disk_creator import DiskImageCreator


# SCOWL Configuration
SCOWL_CONFIG = {
    'max_size': 60,
    'spelling': ['US'],
    'max_variant': 0,
    'diacritic': 'strip',
    'special': ['hacker', 'roman-numerals'],
    'encoding': 'utf-8',
    'format': 'inline',
}

# Directory structure
BUILD_DIR = Path('build')
CACHE_DIR = BUILD_DIR / 'cache'
GENERATED_DIR = BUILD_DIR / 'generated'
ARTIFACTS_DIR = BUILD_DIR / 'artifacts'
WORD_LIST_CACHE = CACHE_DIR / 'scowl_wordlist.txt'


def main():
    # Change to project directory
    script_dir = Path(__file__).parent
    if script_dir.name == 'python':
        os.chdir(script_dir.parent.parent)

    # Setup configuration
    geometry = DiskGeometry()
    config = BloomConfig(geometry=geometry, num_hash_functions=5)
    config.print_summary()

    # Download word list
    downloader = SCOWLDownloader(CACHE_DIR)
    word_file = downloader.download(SCOWL_CONFIG, WORD_LIST_CACHE)

    # Parse words
    parser = SCOWLParser()
    words = parser.parse(word_file)

    # Build Bloom filter
    bloom = BloomFilter(config)
    bloom.build_from_words(words)

    # Calculate and display statistics
    stats = BloomStatistics(bloom, len(words))
    stats.print_statistics()

    # Run empirical validation
    validator = EmpiricalValidator(bloom, words)
    validator.print_validation(stats.false_positive_rate())

    # Write Bloom filter data
    bloom_path = GENERATED_DIR / 'bloom.dat'
    bloom_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bloom_path, 'wb') as f:
        f.write(bloom.data)
    print(f"Bloom filter written to {bloom_path}")

    # Generate C header
    header_gen = CHeaderGenerator()
    header_path = GENERATED_DIR / 'bloom_config.h'
    header_gen.generate(config, len(words), stats.false_positive_rate() * 100,
                       SCOWL_CONFIG, header_path)

    # Create disk image
    disk_creator = DiskImageCreator()
    prg_path = ARTIFACTS_DIR / 'spellcheck.prg'
    d64_path = ARTIFACTS_DIR / 'spellcheck.d64'
    disk_creator.create(prg_path, bloom_path, d64_path)

    print("\n" + "=" * 60)
    print("BUILD COMPLETE!")
    print("=" * 60)


if __name__ == '__main__':
    main()
