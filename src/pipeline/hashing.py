import hashlib
from pathlib import Path
from typing import Dict, Union

DEFAULT_CHUNK_SIZE: int = 65536  # 64 KB streaming buffer size


def compute_hashes(
    file_path: Union[str, Path], chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Dict[str, str]:
    """
    Computes MD5 and SHA-256 hashes for a file by streaming in fixed chunks.
    Ensures multi-GB evidence files are never loaded completely into RAM.

    :param file_path: Path to file to hash.
    :param chunk_size: Buffer size for chunked reads.
    :return: Dictionary containing 'md5' and 'sha256' hex strings.
    :raises FileNotFoundError: If file does not exist.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Evidence file not found: {path}")

    md5_hasher = hashlib.md5()
    sha256_hasher = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            md5_hasher.update(chunk)
            sha256_hasher.update(chunk)

    return {
        "md5": md5_hasher.hexdigest(),
        "sha256": sha256_hasher.hexdigest(),
    }


def compute_bytes_hashes(data: bytes) -> Dict[str, str]:
    """
    Computes MD5 and SHA-256 hashes for an in-memory byte sequence.

    :param data: Byte sequence.
    :return: Dictionary containing 'md5' and 'sha256' hex strings.
    """
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
