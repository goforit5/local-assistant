"""Unit tests for hash_utils."""

import io

import pytest

from lib.shared.local_assistant_shared.utils.hash_utils import (
    calculate_sha256,
    calculate_sha256_stream,
    calculate_sha256_string,
    short_hash,
)


def test_calculate_sha256_basic():
    """Test SHA-256 calculation for basic byte data."""
    data = b"Hello, World!"
    hash_val = calculate_sha256(data)

    # Should return 64-character hex string
    assert len(hash_val) == 64
    assert hash_val == "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"


def test_calculate_sha256_empty():
    """Test SHA-256 calculation for empty data."""
    data = b""
    hash_val = calculate_sha256(data)

    assert len(hash_val) == 64
    assert hash_val == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_calculate_sha256_deterministic():
    """Test that same input produces same hash."""
    data = b"Test data for consistency"

    hash1 = calculate_sha256(data)
    hash2 = calculate_sha256(data)

    assert hash1 == hash2


def test_calculate_sha256_different_inputs():
    """Test that different inputs produce different hashes."""
    hash1 = calculate_sha256(b"Data 1")
    hash2 = calculate_sha256(b"Data 2")

    assert hash1 != hash2


def test_calculate_sha256_stream():
    """Test SHA-256 calculation for file stream."""
    data = b"This is test data for streaming hash calculation"
    stream = io.BytesIO(data)

    hash_val = calculate_sha256_stream(stream)

    # Should match hash of raw data
    expected_hash = calculate_sha256(data)
    assert hash_val == expected_hash


def test_calculate_sha256_stream_large_data():
    """Test SHA-256 calculation for large data (multiple chunks)."""
    # Create 100KB of data
    data = b"x" * 100_000
    stream = io.BytesIO(data)

    hash_val = calculate_sha256_stream(stream, chunk_size=8192)

    # Should match hash of raw data
    expected_hash = calculate_sha256(data)
    assert hash_val == expected_hash


def test_calculate_sha256_string():
    """Test SHA-256 calculation for string data."""
    text = "Hello, World!"
    hash_val = calculate_sha256_string(text)

    # Should match hash of UTF-8 encoded bytes
    expected_hash = calculate_sha256(text.encode("utf-8"))
    assert hash_val == expected_hash


def test_calculate_sha256_string_unicode():
    """Test SHA-256 calculation for Unicode strings."""
    text = "Hello, 世界! 🌍"
    hash_val = calculate_sha256_string(text)

    # Should be 64-character hex string
    assert len(hash_val) == 64

    # Should match hash of UTF-8 encoded bytes
    expected_hash = calculate_sha256(text.encode("utf-8"))
    assert hash_val == expected_hash


def test_short_hash_default_length():
    """Test short hash with default 8-character length."""
    full_hash = calculate_sha256(b"test data")
    short = short_hash(full_hash)

    assert len(short) == 8
    assert short == full_hash[:8]


def test_short_hash_custom_length():
    """Test short hash with custom length."""
    full_hash = calculate_sha256(b"test data")
    short = short_hash(full_hash, length=12)

    assert len(short) == 12
    assert short == full_hash[:12]


def test_short_hash_collision_probability():
    """Test that short hashes provide reasonable uniqueness."""
    # Generate 1000 different hashes
    hashes = [calculate_sha256(f"data_{i}".encode()) for i in range(1000)]
    short_hashes = [short_hash(h, 8) for h in hashes]

    # Should have no collisions in 1000 samples (very high probability)
    assert len(set(short_hashes)) == 1000
