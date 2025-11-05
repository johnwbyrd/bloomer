"""SCOWL word list downloader with caching."""
from pathlib import Path
from typing import Dict
import requests


class SCOWLDownloader:
    """Download SCOWL word lists from aspell.net with local caching."""

    BASE_URL = "http://app.aspell.net/create"

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_url(self, config: Dict[str, any]) -> str:
        """Build SCOWL download URL from configuration parameters."""
        params = []
        params.append(('max_size', config['max_size']))

        for spell in config['spelling']:
            params.append(('spelling', spell))

        params.append(('max_variant', config['max_variant']))
        params.append(('diacritic', config['diacritic']))

        for special in config['special']:
            params.append(('special', special))

        params.append(('download', 'wordlist'))
        params.append(('encoding', config['encoding']))
        params.append(('format', config['format']))

        query_string = '&'.join([f"{k}={v}" for k, v in params])
        return f"{self.BASE_URL}?{query_string}"

    def download(self, config: Dict[str, any], cache_file: Path) -> Path:
        """Download word list if not cached, return path to file."""
        if cache_file.exists():
            print(f"Using cached word list: {cache_file}")
            return cache_file

        url = self.build_url(config)
        print("Downloading SCOWL word list...")
        print(f"  Size: {config['max_size']}, "
              f"Spelling: {', '.join(config['spelling'])}")
        print(f"  Variants: {config['max_variant']}, "
              f"Diacritics: {config['diacritic']}")
        print(f"  Special: {', '.join(config['special'])}")
        print(f"URL: {url}")

        response = requests.get(url)
        response.raise_for_status()

        with open(cache_file, 'wb') as f:
            f.write(response.content)

        print(f"Word list downloaded and cached to {cache_file}")
        return cache_file
