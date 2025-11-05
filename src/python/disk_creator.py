"""D64 disk image creator."""
from pathlib import Path
import d64


class DiskImageCreator:
    """Create C64 .d64 disk images."""

    def create(self, prg_path: Path, bloom_path: Path, output_d64: Path):
        """Create .d64 disk image with program and Bloom filter."""
        print(f"Creating disk image: {output_d64}")
        output_d64.parent.mkdir(parents=True, exist_ok=True)

        d64.DiskImage.create('d64', output_d64, b'SPELLCHECK', b'SK')

        with d64.DiskImage(output_d64, mode='w') as img:
            self._add_program(img, prg_path)
            self._add_bloom_filter(img, bloom_path)

        self._print_directory(output_d64)
        return True

    def _add_program(self, img, prg_path: Path):
        """Add program file to disk image."""
        if prg_path.exists():
            print(f"Adding program: {prg_path} ({prg_path.stat().st_size} bytes)")
            p = img.path(b'SPELLCHECK')
            with p.open('w', ftype='prg') as f:
                with open(prg_path, 'rb') as src:
                    f.write(src.read())
        else:
            print(f"Warning: Program file {prg_path} not found")

    def _add_bloom_filter(self, img, bloom_path: Path):
        """Add Bloom filter as REL file to disk image."""
        print(f"Adding Bloom filter: {bloom_path} "
              f"({bloom_path.stat().st_size} bytes)")
        p = img.path(b'BLOOM.DAT')
        with p.open('w', ftype='rel', record_len=254) as f:
            with open(bloom_path, 'rb') as src:
                f.write(src.read())

    def _print_directory(self, output_d64: Path):
        """Print disk directory listing."""
        print(f"\nDisk image created: {output_d64}")
        with d64.DiskImage(output_d64) as img:
            for line in img.directory():
                print(line)
