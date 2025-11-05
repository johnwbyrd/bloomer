"""C header file generator for Bloom filter configuration."""
from pathlib import Path
from typing import Dict
from bloom_config import BloomConfig


class CHeaderGenerator:
    """Generate C header files with Bloom filter configuration."""

    def generate(self, config: BloomConfig, word_count: int,
                fp_rate: float, scowl_config: Dict[str, any],
                output_path: Path):
        """Generate and write C header file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        spelling_str = ', '.join(scowl_config['spelling'])
        dict_desc = f"SCOWL size {scowl_config['max_size']} ({spelling_str})"

        header_content = f"""/* Auto-generated Bloom filter configuration */
#ifndef BLOOM_CONFIG_H
#define BLOOM_CONFIG_H

#define BLOOM_SIZE_BYTES {config.size_bytes}UL
#define BLOOM_SIZE_BITS {config.size_bits}UL
#define NUM_HASH_FUNCTIONS {config.num_hash_functions}
#define NUM_RECORDS {config.num_records}
#define DICT_INFO "Commodore 64 Bloom filter spell checker\\n\\n" \\
              "https://www.github.com/johnwbyrd/bloomer\\n\\n" \\
              "Dictionary: {word_count} words\\n" \\
              "Source: {dict_desc}\\n\\n" \\
              "Correct words always pass, and\\n" \\
              "misspelled words pass only {fp_rate:06.2f}%%\\n" \\
              "of the time.\\n\\n" \\
              "Let's check spelling!\\n\\n"

#endif /* BLOOM_CONFIG_H */
"""

        with open(output_path, 'w') as f:
            f.write(header_content)

        print(f"Generated configuration header: {output_path}")
