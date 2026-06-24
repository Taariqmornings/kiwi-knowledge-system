"""Tests for the archive service (path traversal protection, scan, etc)."""
import pytest

from app.services.archive_service import ArchiveService


class TestPathTraversal:
    """Tests for path traversal protection in _is_safe_path and _validate_entry_path."""

    def test_is_safe_path_valid(self):
        """Normal absolute paths are safe."""
        assert ArchiveService._is_safe_path(r"C:\Users\test\file.zim") is True
        assert ArchiveService._is_safe_path("/home/user/file.zim") is True

    def test_is_safe_path_null_byte(self):
        """Paths with null bytes are rejected."""
        assert ArchiveService._is_safe_path("/home/user/file\x00.zim") is False

    def test_is_safe_path_traversal(self):
        """Paths with directory traversal are rejected."""
        assert ArchiveService._is_safe_path("/home/user/../../../etc/passwd") is False
        assert ArchiveService._is_safe_path("/home/user/..\\..\\..\\windows\\system32") is False

    def test_is_safe_path_relative(self):
        """Relative paths are rejected."""
        assert ArchiveService._is_safe_path("relative/path.zim") is False
        assert ArchiveService._is_safe_path("file.zim") is False

    def test_validate_entry_path_normal(self):
        """Normal entry paths return cleaned path string."""
        result = ArchiveService._validate_entry_path("A/sample_article.html")
        assert result == "A/sample_article.html"

    def test_validate_entry_path_backtrack(self):
        """Entry paths with ../ raise ValueError."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            ArchiveService._validate_entry_path("A/../../../etc/passwd")

    def test_validate_entry_path_encoded_backtrack(self):
        """Entry paths with encoded traversal raise ValueError."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            ArchiveService._validate_entry_path("A/%2e%2e/something")

    def test_validate_entry_path_absolute(self):
        """Entry paths starting with / raise ValueError."""
        with pytest.raises(ValueError, match="Absolute entry path"):
            ArchiveService._validate_entry_path("/etc/passwd")


def test_scan_nonexistent_directory(db_session):
    """Scanning a non-existent directory returns empty list."""
    result = ArchiveService.scan_directory(db_session, r"C:\nonexistent_path_xyz\zim_files")
    assert result == []
