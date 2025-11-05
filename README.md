# C64 Bloom Filter Spell Checker

A spell checker for the Commodore 64 using Bloom filters to check words against the SCOWL (Spell Checker Oriented Word Lists) dictionary from aspell.net.

## Features

- Customizable word lists using SCOWL parameters (size, spelling variants, special lists)
- Default: 123,676 words with US spelling, hacker terms, and Roman numerals
- 0.81% false positive rate (1 in 123 misspellings incorrectly pass)
- 0.00% false negative rate (correct words always pass)
- Fits on a single 1541 floppy disk (160 KB Bloom filter + 8 KB program)
- On-demand disk sector loading (no need to load entire filter into RAM)
- 5 hash functions (balance between accuracy and disk I/O)
- Mad geek sniping skills


## Download

[Download spellcheck.d64](https://johnwbyrd.github.io/bloomer/spellcheck.d64) - Latest build of d64 Commodore 1541 disk image from main branch.  Run this with your Commodore 64 emulator!

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
2. Download the SCOWL word list from aspell.net (cached locally)
3. Generate the Bloom filter (`bloom.dat`)
4. Create a .d64 disk image (`spellcheck.d64`) with both files

### Customizing the Word List

Edit `src/python/build_bloom.py` and modify the `SCOWL_CONFIG` dictionary:

```python
SCOWL_CONFIG = {
    'max_size': 60,          # Size: 10, 20, 35 (small), 40, 50 (medium), 55, 60 (default), 70 (large), 80 (huge), 95 (insane)
    'spelling': ['US'],      # List: US, GBs (British -ise), GBz (British -ize), CA (Canadian), AU (Australian)
    'max_variant': 0,        # Variants: 0 (none), 1 (common), 2 (acceptable), 3 (seldom-used)
    'diacritic': 'strip',    # Diacritics: strip, keep, both
    'special': ['hacker', 'roman-numerals'],  # Special lists: hacker, roman-numerals
    'encoding': 'utf-8',     # Encoding: utf-8, iso-8859-1
    'format': 'inline',      # Format: inline, tar.gz, zip
}
```

After changing the configuration, delete the cached word list and rebuild:
```bash
rm build/cache/scowl_wordlist.txt
cd build
make
```

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
- Size: 160,782 bytes (633 REL records × 254 bytes)
- Bits: 1,286,256
- Hash functions: 5 (FNV-1a, DJB2, SDBM, Jenkins, Murmur-inspired)
- False positive rate: 0.81% (formula: (1 - e^(-kn/m))^k)

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
│   ├── python/             # Python build tools
│   │   ├── build_bloom.py  # Bloom filter builder
│   │   └── inject_autoload.py # Web emulator auto-load injector
│   └── emulator/           # Viciious emulator build config
│       └── webpack.config.js
├── bloom_config.h          # Auto-generated configuration
└── build/
    ├── spellcheck.prg      # Compiled program
    ├── bloom.dat           # Bloom filter data
    └── spellcheck.d64      # Complete disk image
```

## License

Public domain / MIT - use as you wish, but don't claim you wrote it.

## References

- SCOWL Word Lists: http://wordlist.aspell.net/
- SCOWL Custom List Creator: http://app.aspell.net/create
- SCOWL Documentation: http://wordlist.aspell.net/scowl-readme/
- LLVM-MOS: https://github.com/llvm-mos/llvm-mos-sdk
- Bloom Filters: https://en.wikipedia.org/wiki/Bloom_filter
