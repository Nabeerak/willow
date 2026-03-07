"""
Unit Tests: T077 Sovereign Truth Hash Validation

Verifies:
- SHA-256 hash computation is correct
- Mismatch raises SovereignTruthIntegrityError
- SKIP_HASH_VALIDATION=true bypasses check
- Missing file raises FileNotFoundError
"""

import hashlib
import os
import tempfile
from pathlib import Path

import pytest

from src.core.sovereign_truth import (
    SovereignTruthIntegrityError,
    validate_sovereign_truths_hash,
)


@pytest.fixture
def temp_truths_file():
    """Create a temporary sovereign_truths.json file."""
    content = b'{"sovereign_truths": []}'
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(content)
        f.flush()
        yield Path(f.name), hashlib.sha256(content).hexdigest()
    os.unlink(f.name)


class TestHashValidation:
    def test_correct_hash_passes(self, temp_truths_file):
        """Matching hash passes without error."""
        path, expected_hash = temp_truths_file
        result = validate_sovereign_truths_hash(path, expected_hash=expected_hash)
        assert result == expected_hash

    def test_wrong_hash_raises(self, temp_truths_file, monkeypatch):
        """Mismatching hash raises SovereignTruthIntegrityError."""
        monkeypatch.delenv("SKIP_HASH_VALIDATION", raising=False)
        path, _ = temp_truths_file
        with pytest.raises(SovereignTruthIntegrityError, match="integrity check failed"):
            validate_sovereign_truths_hash(path, expected_hash="deadbeef" * 8)

    def test_missing_file_raises(self, monkeypatch):
        """Non-existent file raises FileNotFoundError."""
        monkeypatch.delenv("SKIP_HASH_VALIDATION", raising=False)
        with pytest.raises(FileNotFoundError):
            validate_sovereign_truths_hash("/tmp/nonexistent_truths.json", expected_hash="abc")

    def test_skip_env_bypasses(self, temp_truths_file, monkeypatch):
        """SKIP_HASH_VALIDATION=true bypasses hash check even with wrong expected."""
        path, _ = temp_truths_file
        monkeypatch.setenv("SKIP_HASH_VALIDATION", "true")
        # Should NOT raise even with wrong expected hash
        result = validate_sovereign_truths_hash(path, expected_hash="wrong")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest length

    def test_no_expected_hash_no_secret_manager(self, temp_truths_file, monkeypatch):
        """When no expected hash and no Secret Manager, logs warning and returns hash."""
        path, actual_hash = temp_truths_file
        monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("SKIP_HASH_VALIDATION", raising=False)
        result = validate_sovereign_truths_hash(path, expected_hash=None)
        assert result == actual_hash
