
<img width="960" height="680" alt="bloomer-4" src="https://github.com/user-attachments/assets/93bc099b-7fda-4aed-8e08-3d89be3e72de" />

# Bloomer: A 123,676-Word Spell Checker for the Commodore 64

## This Is Impossible, So Don't Even Try It

We fit a complete professional-grade dictionary—**123,676 words**—onto a Commodore 64.

A computer from 1982 with **64KB of RAM** and a **1MHz processor** is now checking your spelling against the same SCOWL dictionary used by modern Linux spell checkers.

The SCOWL wordlist alone is 1.19MB. But the Commodore 1541 holds only 170KB of memory. And the poor Commodore 64 has only 64KB of RAM. **Do the math.**

## How?

**Bloom filters + 1541 disk drive as external memory.**

Think of it as a probabilistic hash table that lives on your floppy disk. Five different hash functions compute bit positions in real-time on that 1MHz 6510 processor, and the program reads only the exact disk sectors it needs—typically 2-3 sectors per word lookup. No loading bars. No "please wait." Just spell checking with a **0.81% false positive rate** and **zero false negatives**.

## The Absurdity of It All

- **123,676 words** - More than most people's active vocabulary
- **0.81% false positive rate** - 99.19% of misspellings get caught
- **0% false negative rate** - Correct words ALWAYS pass
- **Fits on one floppy disk** - 160KB Bloom filter + 8KB program
- **Real-time on 1MHz** - 5 hash functions computed instantly
- **Zero RAM footprint** - Entire dictionary stays on disk
- **Sorted disk access** - Minimizes 1541 head movement
- **REL file caching** - Smart sector buffering

When you type a word, the C64:
1. Computes 5 hash values (FNV-1a, DJB2, SDBM, Jenkins, Murmur)
2. Sorts the bit positions for optimal disk access
3. Reads 2-3 disk sectors on average
4. Returns your answer in a few seconds

All while displaying progress dots and color-coded results in glorious PETSCII.

## Download

**[Download spellcheck.d64](https://johnwbyrd.github.io/bloomer/spellcheck.d64)** - Latest build from main branch

Load it in VICE, or if you're truly l33t, write it to a real 1541 disk and run it on actual Commodore 64 hardware.

## Quick Start

```basic
LOAD"SPELLCHECK",8
RUN
```

Type a word. Get a color-coded answer. Question your assumptions about what "vintage computing limitations" really means.

## Requirements

### Runtime
- Commodore 64 (or VICE emulator)
- 1541 disk drive (or emulation thereof)

### Building From Source
- CMake 3.18+
- LLVM-MOS SDK with `mos-c64-clang`
- Python 3.8+ (for Bloom filter generation)
- VICE tools (c1541)

## Building

```bash
# Install dependencies
pip install -e .

# Get LLVM-MOS
wget https://github.com/llvm-mos/llvm-mos-sdk/releases/latest/download/llvm-mos-linux.tar.xz
tar xf llvm-mos-linux.tar.xz
sudo mv llvm-mos /opt/
export PATH="/opt/llvm-mos/bin:$PATH"

# Build
mkdir build && cd build
cmake .. && make
```

The build process:
1. Downloads the SCOWL word list (123,676 words)
2. Generates a 1.28-million-bit Bloom filter
3. Optimizes it for 1541 disk geometry
4. Compiles C64-native code with LLVM-MOS
5. Creates a bootable .d64 disk image

## Customizing the Dictionary

Want British spelling? Hacker jargon? Roman numerals? Edit `src/python/build_bloom.py`:

```python
SCOWL_CONFIG = {
    'max_size': 60,          # 10-95 (small to insane)
    'spelling': ['US'],      # US, GBs, GBz, CA, AU
    'max_variant': 0,        # 0-3 (none to seldom-used)
    'special': ['hacker', 'roman-numerals'],
}
```

Then rebuild. The entire dictionary regenerates with your preferences.

## The Technical Deep Dive

### Bloom Filter Mathematics

- **1,286,256 bits** organized as 633 × 254-byte REL records
- **5 hash functions** (k=5) for optimal false positive rate
- **10.4 bits per word** (m/n ratio)
- **38% bit density** (actual vs theoretical: spot on)

The false positive rate formula: `(1 - e^(-kn/m))^k = 0.0081`

Translation: Only **1 in 123 misspellings** sneaks through. And we empirically validated this with 100,000 random strings.

### Disk I/O Optimization

The 1541 drive head moves sequentially through the disk. We:
1. Sort bit positions before checking (left-to-right on disk)
2. Cache the current 254-byte REL record
3. Minimize redundant seeks

Result: **2-3 disk reads per word** instead of 5. The difference between "fast" and "glacial" on floppy hardware.

### Performance Profile

| Operation | Time | Notes |
|-----------|------|-------|
| Hash computation | <10ms | 5 functions on 1MHz CPU |
| Disk sector read | ~200ms | 1541 seek + read |
| Total per word | ~400-600ms | Cached reads help |
| User perception | "Instant" | Progress dots + color |

### Memory Footprint

```
C64 RAM (64KB):
- Program code: ~5KB
- Record buffer: 254 bytes
- Variables: <1KB
- Remaining: ~59KB free!

Disk (170KB):
- BLOOM.DAT: 160KB (REL file)
- SPELLCHECK: 8KB (PRG file)
- Directory: 2KB
```

## Project Structure

```
bloomer/
├── src/
│   ├── spellcheck.c             # C64 spell checker (522 lines of C)
│   └── python/                  # Build toolchain
│       ├── build_bloom.py       # Orchestrator
│       ├── bloom_filter.py      # Bloom filter implementation
│       ├── bloom_statistics.py  # FP rate validation
│       └── disk_creator.py      # D64 image creation
├── build/
│   ├── artifacts/
│   │   ├── spellcheck.prg       # Compiled 6502 code
│   │   └── spellcheck.d64       # Bootable disk image
│   └── generated/
│       ├── bloom.dat            # 160KB Bloom filter
│       └── bloom_config.h       # Auto-generated constants
└── CMakeLists.txt               # LLVM-MOS build config
```

## Usage

```basic
LOAD"SPELLCHECK",8
RUN
```

Type any word:
- Green circle + "OK" → Spelled correctly
- Red X + "NOT FOUND" → Not in dictionary

## License

Public domain / MIT. Use it, learn from it, improve it. Just don't claim you wrote it first.

## References & Acknowledgments

- **SCOWL** (Spell Checker Oriented Word Lists): http://wordlist.aspell.net/
- **Bloom, Burton H.** (1970): "Space/Time Trade-offs in Hash Coding with Allowable Errors"
- **LLVM-MOS**: https://github.com/llvm-mos/llvm-mos-sdk - Making modern C compilation for 6502 possible
- **Wikipedia: Bloom Filter**: https://en.wikipedia.org/wiki/Bloom_filter - For the curious
