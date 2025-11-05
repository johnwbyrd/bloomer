"""Hash function implementations for Bloom filter."""


def hash_fnv1a(word: str, seed: int = 0) -> int:
    """FNV-1a hash function."""
    hash_val = 2166136261 + seed
    for char in word:
        hash_val ^= ord(char)
        hash_val = (hash_val * 16777619) & 0xFFFFFFFF
    return hash_val


def hash_djb2(word: str, seed: int = 0) -> int:
    """DJB2 hash function."""
    hash_val = 5381 + seed
    for char in word:
        hash_val = ((hash_val << 5) + hash_val + ord(char)) & 0xFFFFFFFF
    return hash_val


def hash_sdbm(word: str, seed: int = 0) -> int:
    """SDBM hash function."""
    hash_val = seed
    for char in word:
        hash_val = (ord(char) + (hash_val << 6) + (hash_val << 16) - hash_val) & 0xFFFFFFFF
    return hash_val


def hash_jenkins(word: str, seed: int = 0) -> int:
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


def hash_murmur(word: str, seed: int = 0) -> int:
    """Simplified Murmur-inspired hash."""
    hash_val = seed + 0x9747b28c
    for char in word:
        hash_val ^= ord(char)
        hash_val = (hash_val * 0x5bd1e995) & 0xFFFFFFFF
        hash_val ^= (hash_val >> 15)
    return hash_val


ALL_HASH_FUNCTIONS = [
    hash_fnv1a,
    hash_djb2,
    hash_sdbm,
    hash_jenkins,
    hash_murmur
]
