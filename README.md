# C64 Bloom Filter Spell Checker

A spell checker for the Commodore 64 using Bloom filters to check words against the Tournament Word List (TWL06 - Scrabble word list).

## Features

- 178,691 word dictionary (TWL06)
- ~1.1% false positive rate
- Fits on a single 1541 floppy disk
- On-demand disk sector loading (no need to load entire filter into RAM)
- 5 hash functions for optimal distribution

## Requirements

### Build Environment
- CMake 3.18 or later
- LLVM-MOS SDK (https://github.com/llvm-mos/llvm-mos-sdk)
- Python 3.6+ with `requests` module
- VICE emulator suite (for `c1541` disk image tool)

### Runtime
- Commodore 64
- 1541 disk drive (or emulator)

## Building

1. Install dependencies:
```bash
# Install Python dependencies
pip install requests

# Install LLVM-MOS SDK (follow instructions at https://github.com/llvm-mos/llvm-mos-sdk)

# Install VICE emulator for c1541 tool
# On Ubuntu/Debian:
sudo apt-get install vice

# On macOS with Homebrew:
brew install vice
```

2. Configure and build:
```bash
mkdir build
cd build
cmake -DCMAKE_PREFIX_PATH=/path/to/llvm-mos-sdk ..
make
```

The build process will:
1. Compile the C64 program to `spellcheck.prg`
2. Download the TWL06 word list (cached locally)
3. Generate the Bloom filter (`bloom.dat`)
4. Create a .d64 disk image (`spellcheck.d64`) with both files

## Usage

### In VICE Emulator
1. Start x64 (C64 emulator)
2. Attach disk image: File → Attach disk image → Unit 8 → select `spellcheck.d64`
3. Load and run:
```
LOAD"SPELLCHECK",8
RUN
```

### On Real Hardware
1. Transfer `spellcheck.d64` to real disk using tools like sd2iec or ZoomFloppy
2. Load and run as above

### Using the Program
- Enter a word to check its spelling
- Type 'quit' to exit
- Words are case-insensitive
- The program will report "probably correct" or "not found"

## Technical Details

### Bloom Filter
- Size: 160,256 bytes (626 disk blocks)
- Bits: 1,282,048
- Hash functions: 5 (FNV-1a, DJB2, SDBM, Jenkins, Murmur-inspired)
- False positive rate: ~1.1%

### Disk Layout
- Program: ~5KB
- Bloom filter: 160KB
- Total: ~165KB (fits on 170KB disk)

### Performance
- Hash computation: Fast (pure CPU)
- Disk access: 5 reads worst-case per word (one per hash function)
- Typical: 2-3 reads if hashes map to same/nearby sectors

## Project Structure
```
c64-spellcheck/
├── CMakeLists.txt          # Build configuration
├── README.md               # This file
├── src/
│   ├── spellcheck.c        # Main C64 program
│   └── bloom_config.h      # Auto-generated configuration
├── tools/
│   └── build_bloom.py      # Bloom filter builder
└── build/
    ├── spellcheck.prg      # Compiled program
    ├── bloom.dat           # Bloom filter data
    └── spellcheck.d64      # Complete disk image
```

## License

Public domain / MIT - use as you wish.

## References

- TWL06 Word List: https://norvig.com/ngrams/TWL06.txt
- LLVM-MOS: https://github.com/llvm-mos/llvm-mos-sdk
- Bloom Filters: https://en.wikipedia.org/wiki/Bloom_filter
