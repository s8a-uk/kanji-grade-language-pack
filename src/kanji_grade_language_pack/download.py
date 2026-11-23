"""Downloads checked against a known hash."""
import hashlib
import urllib.request

USER_AGENT = "kanji-grade-language-pack"


class HashMismatch(Exception):
    pass


def download_unchecked(url: str) -> bytes:
    """The bytes at url, for a document that has no known hash (the start of a chain of hashes)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def download(url: str, algorithm: str, expected: str) -> bytes:
    """The bytes at url, if their hash (hashlib algorithm name) is expected; else HashMismatch."""
    data = download_unchecked(url)
    got = hashlib.new(algorithm, data).hexdigest()
    if got != expected:
        raise HashMismatch(f"{algorithm} of {url}: expected {expected}, got {got}")
    return data
