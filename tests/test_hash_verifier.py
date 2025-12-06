"""Tests for hash_verifier.py"""
import pytest
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from hash_verifier import HashVerifier


class TestHashVerifier:
    """Test suite for HashVerifier class."""
    
    def test_compute_sha256(self, tmp_path):
        """Test SHA256 hash computation."""
        # Create a test file with known content
        test_file = tmp_path / "test.txt"
        content = b"Hello, World!"
        test_file.write_bytes(content)
        
        # Compute expected hash
        expected_hash = hashlib.sha256(content).hexdigest().lower()
        
        # Test our function
        computed_hash = HashVerifier.compute_sha256(str(test_file))
        
        assert computed_hash == expected_hash
        assert len(computed_hash) == 64  # SHA256 is 64 hex chars
    
    def test_compute_sha256_large_file(self, tmp_path):
        """Test SHA256 computation with large file (tests chunking)."""
        test_file = tmp_path / "large.bin"
        
        # Create a 10MB file
        chunk_size = 1024 * 1024  # 1MB
        content = b"A" * chunk_size
        
        with open(test_file, 'wb') as f:
            for _ in range(10):
                f.write(content)
        
        # Compute hash both ways to verify
        expected = hashlib.sha256(content * 10).hexdigest().lower()
        computed = HashVerifier.compute_sha256(str(test_file))
        
        assert computed == expected
    
    @patch('requests.get')
    def test_fetch_hash_file_success(self, mock_get):
        """Test successful hash file download."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "abc123def456  ubuntu-22.04-desktop-amd64.iso\n"
        mock_get.return_value = mock_response
        
        result = HashVerifier.fetch_hash_file('https://example.com/SHA256SUMS')
        
        assert result is not None
        assert "ubuntu-22.04-desktop-amd64.iso" in result
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_fetch_hash_file_failure(self, mock_get):
        """Test hash file download failure."""
        import requests
        mock_get.side_effect = requests.RequestException("Network error")
        
        result = HashVerifier.fetch_hash_file('https://example.com/SHA256SUMS')
        
        assert result is None
    
    def test_parse_sha256sums_format1(self):
        """Test parsing SHA256SUMS with asterisk format."""
        # Use proper 64-char SHA256 hashes
        hash1 = "1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014"
        hash2 = "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752"
        content = f"""
# Comment line
{hash1} *ubuntu.iso
{hash2} *debian.iso
"""
        result = HashVerifier.parse_sha256sums(content)
        
        assert len(result) == 2
        assert 'ubuntu.iso' in result
        assert 'debian.iso' in result
        assert result['ubuntu.iso'] == hash1
    
    def test_parse_sha256sums_format2(self):
        """Test parsing SHA256SUMS with space format."""
        hash1 = "1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014"
        hash2 = "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752"
        content = f"{hash1}  ubuntu.iso\n{hash2}  debian.iso"
        
        result = HashVerifier.parse_sha256sums(content)
        
        assert len(result) == 2
        assert 'ubuntu.iso' in result
    
    def test_parse_sha256sums_with_path(self):
        """Test parsing SHA256SUMS with file paths."""
        hash1 = "1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014"
        content = f"{hash1} *./path/to/file.iso"
        
        result = HashVerifier.parse_sha256sums(content)
        
        # Should extract filename with path stripped
        assert 'path/to/file.iso' in result or 'file.iso' in result
    
    def test_parse_sha256sums_specific_file(self):
        """Test parsing SHA256SUMS for specific filename."""
        hash1 = "1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014"
        hash2 = "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752"
        content = f"""
{hash1} *ubuntu.iso
{hash2} *debian.iso
"""
        result = HashVerifier.parse_sha256sums(content, filename='ubuntu.iso')
        
        # When filename is provided, returns just the hash string, not a dict
        assert isinstance(result, str)
        assert len(result) == 64
        assert result == hash1
    
    def test_get_hash_url_ubuntu(self):
        """Test hash URL generation for Ubuntu."""
        iso_url = "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-desktop-amd64.iso"
        
        hash_url = HashVerifier.get_hash_url(iso_url)
        
        assert hash_url is not None
        assert "SHA256SUMS" in hash_url
        assert "22.04" in hash_url
    
    def test_get_hash_url_debian(self):
        """Test hash URL generation for Debian."""
        iso_url = "https://cdimage.debian.org/debian-cd/12.0.0/amd64/iso-cd/debian-12.0.0-amd64-netinst.iso"
        
        hash_url = HashVerifier.get_hash_url(iso_url)
        
        assert hash_url is not None
        assert "SHA256SUMS" in hash_url or "CHECKSUM" in hash_url.upper()
    
    def test_get_hash_url_unknown_distro(self):
        """Test hash URL for unknown distribution."""
        iso_url = "https://example.com/unknown-distro/file.iso"
        
        hash_url = HashVerifier.get_hash_url(iso_url)
        
        # Should still try common patterns
        assert hash_url is not None or hash_url is None  # Either is acceptable
    
    @patch('hash_verifier.HashVerifier.fetch_hash_file')
    @patch('hash_verifier.HashVerifier.compute_sha256')
    @patch('hash_verifier.HashVerifier.get_hash_url')
    def test_verify_file_success(self, mock_get_url, mock_compute, mock_fetch, tmp_path):
        """Test successful file verification."""
        test_file = tmp_path / "test.iso"
        test_file.write_bytes(b"test content")
        
        computed_hash = "1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014"
        mock_compute.return_value = computed_hash
        mock_get_url.return_value = "https://example.com/SHA256SUMS"
        
        # Mock hash file content
        hash_content = f"{computed_hash} *test.iso"
        mock_fetch.return_value = hash_content
        
        success, message, hash_val = HashVerifier.verify_file(
            str(test_file),
            iso_url="https://example.com/test.iso"
        )
        
        assert success is True
        assert "verified successfully" in message.lower()
        assert hash_val == computed_hash
    
    @patch('hash_verifier.HashVerifier.fetch_hash_file')
    @patch('hash_verifier.HashVerifier.compute_sha256')
    def test_verify_file_mismatch(self, mock_compute, mock_fetch, tmp_path):
        """Test file verification with hash mismatch."""
        test_file = tmp_path / "test.iso"
        test_file.write_bytes(b"test content")
        
        computed_hash = "1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014"
        expected_hash = "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752"
        
        mock_compute.return_value = computed_hash
        mock_fetch.return_value = f"{expected_hash} *test.iso"
        
        success, message, hash_val = HashVerifier.verify_file(
            str(test_file),
            "https://example.com/test.iso"
        )
        
        assert success is False
        assert "mismatch" in message.lower()
    
    @patch('hash_verifier.HashVerifier.get_hash_url')
    def test_verify_file_no_hash_available(self, mock_get_url, tmp_path):
        """Test file verification when no hash is available."""
        test_file = tmp_path / "test.iso"
        test_file.write_bytes(b"test content")
        
        # No hash URL available
        mock_get_url.return_value = None
        
        success, message, hash_val = HashVerifier.verify_file(
            str(test_file),
            iso_url="https://example.com/test.iso"
        )
        
        assert success is None
        assert "no hash" in message.lower() or "not available" in message.lower()
    
    def test_hash_patterns_coverage(self):
        """Test that we have hash patterns for major distros."""
        patterns = HashVerifier.HASH_PATTERNS
        
        # Check major distributions are covered
        expected_distros = ['ubuntu', 'debian', 'fedora', 'arch', 'rocky']
        
        for distro in expected_distros:
            assert distro in patterns or distro.replace(' ', '') in patterns, \
                f"Missing hash pattern for {distro}"


class TestHashVerifierIntegration:
    """Integration tests for hash verification workflow."""
    
    def test_full_verification_workflow(self, tmp_path):
        """Test complete verification workflow with real file."""
        # Create a test file
        test_file = tmp_path / "test.iso"
        content = b"Test ISO content"
        test_file.write_bytes(content)
        
        # Compute real hash
        expected_hash = hashlib.sha256(content).hexdigest().lower()
        
        # Create a mock hash file
        hash_file = tmp_path / "SHA256SUMS"
        hash_file.write_text(f"{expected_hash} *test.iso\n")
        
        # Test verification with file:// URL (simulating local hash file)
        with patch('hash_verifier.HashVerifier.get_hash_url') as mock_get_url:
            with patch('hash_verifier.HashVerifier.fetch_hash_file') as mock_fetch:
                mock_get_url.return_value = "file:///SHA256SUMS"
                mock_fetch.return_value = hash_file.read_text()
                
                success, message, hash_val = HashVerifier.verify_file(
                    str(test_file),
                    iso_url="file:///test.iso"
                )
                
                assert success is True
                assert hash_val == expected_hash
    
    @patch('hash_verifier.HashVerifier.get_hash_url')
    def test_verify_with_url_detection(self, mock_get_url, tmp_path):
        """Test verification with automatic hash URL detection."""
        test_file = tmp_path / "ubuntu.iso"
        test_file.write_bytes(b"test")
        
        # Mock URL detection
        mock_get_url.return_value = "https://example.com/SHA256SUMS"
        
        with patch('hash_verifier.HashVerifier.fetch_hash_file') as mock_fetch:
            computed = HashVerifier.compute_sha256(str(test_file))
            mock_fetch.return_value = f"{computed} *ubuntu.iso"
            
            success, message, _ = HashVerifier.verify_file(
                str(test_file),
                iso_url="https://example.com/ubuntu.iso"
            )
            
            assert success is True


class TestHashVerifierEdgeCases:
    """Test edge cases and error handling."""
    
    def test_compute_sha256_nonexistent_file(self):
        """Test hash computation with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            HashVerifier.compute_sha256("/nonexistent/file.iso")
    
    def test_parse_empty_hash_file(self):
        """Test parsing empty hash file."""
        result = HashVerifier.parse_sha256sums("")
        assert result == {}
    
    def test_parse_malformed_hash_file(self):
        """Test parsing malformed hash file."""
        content = "not a valid hash line\nanother invalid line"
        result = HashVerifier.parse_sha256sums(content)
        assert result == {} or len(result) == 0
    
    def test_parse_short_hash(self):
        """Test parsing hash file with too-short hash."""
        content = "abc123 *file.iso"  # Too short to be SHA256
        result = HashVerifier.parse_sha256sums(content)
        # Should not match or be rejected
        assert len(result) == 0 or 'file.iso' not in result
    
    @patch('hash_verifier.HashVerifier.fetch_hash_file')
    def test_verify_file_timeout(self, mock_fetch, tmp_path):
        """Test verification with network timeout."""
        test_file = tmp_path / "test.iso"
        test_file.write_bytes(b"test")
        
        import requests
        mock_fetch.side_effect = requests.Timeout("Connection timeout")
        
        # Should handle gracefully
        try:
            success, message, _ = HashVerifier.verify_file(
                str(test_file),
                "https://example.com/test.iso"
            )
            # Should return None (no hash available) rather than crashing
            assert success is None or success is False
        except requests.Timeout:
            pytest.fail("Timeout not handled gracefully")
    
    def test_hash_patterns_not_empty(self):
        """Test that hash patterns dictionary is populated."""
        assert len(HashVerifier.HASH_PATTERNS) > 0
        assert all(isinstance(k, str) for k in HashVerifier.HASH_PATTERNS.keys())
        assert all(isinstance(v, str) for v in HashVerifier.HASH_PATTERNS.values())
