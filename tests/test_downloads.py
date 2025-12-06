"""Tests for downloads.py"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import downloads


class TestDownloadManager:
    """Test suite for DownloadManager class."""
    
    def test_init(self, tmp_path):
        """Test DownloadManager initialization."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        assert manager.target_dir == target_dir
        assert manager.max_workers == 3
        assert manager.running is True
    
    def test_get_status_includes_is_remote(self, tmp_path):
        """Test that get_status() includes 'is_remote' key.
        
        This test catches the bug where DownloadManager.get_status()
        was missing the 'is_remote' key, causing KeyError in UI code.
        """
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        status = manager.get_status()
        
        # Critical: Must have 'is_remote' key
        assert 'is_remote' in status
        assert status['is_remote'] is False
    
    def test_get_status_structure(self, tmp_path):
        """Test that get_status() returns all expected keys."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        status = manager.get_status()
        
        # Verify all expected keys are present
        expected_keys = [
            'active',
            'completed',
            'completed_urls',
            'failed',
            'retry_counts',
            'queued',
            'downloaded_files',
            'is_remote'
        ]
        
        for key in expected_keys:
            assert key in status, f"Missing key '{key}' in status dict"
    
    def test_get_status_types(self, tmp_path):
        """Test that get_status() returns correct data types."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        status = manager.get_status()
        
        assert isinstance(status['active'], dict)
        assert isinstance(status['completed'], int)
        assert isinstance(status['completed_urls'], set)
        assert isinstance(status['failed'], int)
        assert isinstance(status['retry_counts'], dict)
        assert isinstance(status['queued'], int)
        assert isinstance(status['downloaded_files'], list)
        assert isinstance(status['is_remote'], bool)
    
    @patch('requests.get')
    def test_download_file_success(self, mock_get, tmp_path):
        """Test successful file download."""
        target_dir = tmp_path / "downloads"
        target_dir.mkdir()
        
        # Mock successful download
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content = lambda chunk_size: [b'test' * 256]
        mock_get.return_value = mock_response
        
        manager = downloads.DownloadManager(str(target_dir))
        manager._download_file('http://example.com/test.iso', 'test.iso')
        
        # Verify file was created
        downloaded_file = target_dir / 'test.iso'
        assert downloaded_file.exists()
    
    def test_start_creates_workers(self, tmp_path):
        """Test that start() creates worker threads."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir, max_workers=2)
        
        manager.start()
        
        assert len(manager.workers) == 2
        assert all(worker.is_alive() for worker in manager.workers)
        
        # Cleanup
        manager.stop()
    
    def test_add_download(self, tmp_path):
        """Test adding URL to download queue."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        url = "http://example.com/test.iso"
        manager.add_download(url)
        
        assert manager.download_queue.qsize() == 1
    
    def test_stop(self, tmp_path):
        """Test stopping download manager."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        manager.start()
        
        assert manager.running is True
        
        manager.stop()
        
        assert manager.running is False


class TestDownloadManagerIntegration:
    """Integration tests for DownloadManager with UI expectations."""
    
    def test_status_compatible_with_ui_code(self, tmp_path):
        """Test that status dict works with UI code pattern.
        
        This simulates the code in distroget.py line 812:
        if status['is_remote']:
        """
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        status = manager.get_status()
        
        # This should not raise KeyError
        try:
            if status['is_remote']:
                pass  # Remote handling
            else:
                pass  # Local handling
        except KeyError as e:
            pytest.fail(f"KeyError accessing status dict: {e}")
    
    def test_status_consistency_with_combined_manager(self, tmp_path):
        """Test that status keys match CombinedDownloadTransferManager.
        
        Both managers should return compatible status dicts.
        """
        from transfers import CombinedDownloadTransferManager
        
        # Create both managers
        local_dir = str(tmp_path / "downloads")
        local_manager = downloads.DownloadManager(local_dir)
        
        remote_manager = CombinedDownloadTransferManager(
            "192.168.1.100", "/tmp/uploads"
        )
        
        local_status = local_manager.get_status()
        remote_status = remote_manager.get_status()
        
        # Both should have 'is_remote' key
        assert 'is_remote' in local_status
        assert 'is_remote' in remote_status
        
        # Values should differ appropriately
        assert local_status['is_remote'] is False
        assert remote_status['is_remote'] is True


class TestHashVerificationIntegration:
    """Test hash verification integration in DownloadManager."""
    
    def test_get_status_includes_hash_verification(self, tmp_path):
        """Test that get_status() includes hash_verification dict."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        status = manager.get_status()
        
        assert 'hash_verification' in status
        assert isinstance(status['hash_verification'], dict)
    
    def test_get_status_includes_failed_verifications(self, tmp_path):
        """Test that get_status() includes failed_verifications list."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        status = manager.get_status()
        
        assert 'failed_verifications' in status
        assert isinstance(status['failed_verifications'], list)
    
    def test_get_failed_verifications(self, tmp_path):
        """Test get_failed_verifications() method."""
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        # Should return list of tuples
        failed = manager.get_failed_verifications()
        assert isinstance(failed, list)
    
    @patch('hash_verifier.HashVerifier.verify_file')
    def test_hash_verification_on_success(self, mock_verify, tmp_path):
        """Test hash verification is called and tracked on successful verification."""
        target_dir = tmp_path / "downloads"
        target_dir.mkdir()
        
        # Mock successful verification
        test_hash = "abc123def456789012345678901234567890123456789012345678901234"
        mock_verify.return_value = (True, "Hash verified successfully", test_hash)
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'content-length': '1024'}
            mock_response.iter_content = lambda chunk_size: [b'test' * 256]
            mock_get.return_value = mock_response
            
            manager = downloads.DownloadManager(str(target_dir))
            manager._download_file('http://example.com/test.iso', 'test.iso')
            
            # Check verification was tracked
            status = manager.get_status()
            downloaded_file = str(target_dir / 'test.iso')
            
            assert downloaded_file in status['hash_verification']
            success, message = status['hash_verification'][downloaded_file]
            assert success is True
            assert "verified" in message.lower()
    
    @patch('hash_verifier.HashVerifier.verify_file')
    def test_hash_verification_on_failure(self, mock_verify, tmp_path):
        """Test hash verification failure is tracked."""
        target_dir = tmp_path / "downloads"
        target_dir.mkdir()
        
        # Mock failed verification
        mock_verify.return_value = (False, "Hash mismatch", None)
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'content-length': '1024'}
            mock_response.iter_content = lambda chunk_size: [b'test' * 256]
            mock_get.return_value = mock_response
            
            manager = downloads.DownloadManager(str(target_dir))
            manager._download_file('http://example.com/test.iso', 'test.iso')
            
            # Check failure was tracked
            status = manager.get_status()
            failed = manager.get_failed_verifications()
            
            assert len(failed) > 0
            filepath, message = failed[0]
            assert 'test.iso' in filepath
            assert "mismatch" in message.lower()
    
    @patch('hash_verifier.HashVerifier.verify_file')
    def test_hash_verification_no_hash_available(self, mock_verify, tmp_path):
        """Test handling when no hash is available."""
        target_dir = tmp_path / "downloads"
        target_dir.mkdir()
        
        # Mock no hash available
        mock_verify.return_value = (None, "No hash file available", None)
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'content-length': '1024'}
            mock_response.iter_content = lambda chunk_size: [b'test' * 256]
            mock_get.return_value = mock_response
            
            manager = downloads.DownloadManager(str(target_dir))
            manager._download_file('http://example.com/test.iso', 'test.iso')
            
            # Should not be in failed list
            failed = manager.get_failed_verifications()
            assert len(failed) == 0
            
            # But should be tracked in hash_verification
            status = manager.get_status()
            downloaded_file = str(target_dir / 'test.iso')
            assert downloaded_file in status['hash_verification']
            success, _ = status['hash_verification'][downloaded_file]
            assert success is None
    
    def test_delete_failed_verifications(self, tmp_path):
        """Test deleting files with failed verification."""
        target_dir = tmp_path / "downloads"
        target_dir.mkdir()
        
        # Create test files
        test_file1 = target_dir / "failed1.iso"
        test_file2 = target_dir / "failed2.iso"
        test_file1.write_bytes(b"test1")
        test_file2.write_bytes(b"test2")
        
        manager = downloads.DownloadManager(str(target_dir))
        
        # Manually add to failed list and hash_verification dict
        manager.failed_verifications.append(str(test_file1))
        manager.failed_verifications.append(str(test_file2))
        manager.hash_verification[str(test_file1)] = (False, "Hash mismatch")
        manager.hash_verification[str(test_file2)] = (False, "Hash mismatch")
        
        assert test_file1.exists()
        assert test_file2.exists()
        
        # Delete failed files
        deleted = manager.delete_failed_verifications()
        
        assert len(deleted) == 2
        assert not test_file1.exists()
        assert not test_file2.exists()
        assert len(manager.failed_verifications) == 0
    
    def test_delete_failed_verifications_missing_file(self, tmp_path):
        """Test deleting failed verifications when file already missing."""
        target_dir = tmp_path / "downloads"
        target_dir.mkdir()
        
        manager = downloads.DownloadManager(str(target_dir))
        
        # Add non-existent file to failed list
        fake_file = str(target_dir / "nonexistent.iso")
        manager.failed_verifications.append(fake_file)
        manager.hash_verification[fake_file] = (False, "Hash mismatch")
        
        # Should not crash
        deleted = manager.delete_failed_verifications()
        
        # Should still clear the list even if file doesn't exist
        assert len(manager.failed_verifications) == 0
    
    def test_ui_can_check_verification_status(self, tmp_path):
        """Test that UI can check verification status per file.
        
        Simulates the TUI code checking verification status:
        verification = status.get('hash_verification', {}).get(filepath, (None, ''))
        """
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        # Add some mock verification data
        test_file = "/path/to/test.iso"
        manager.hash_verification[test_file] = (True, "Verified successfully")
        
        status = manager.get_status()
        
        # Simulate UI access pattern
        verification = status.get('hash_verification', {}).get(test_file, (None, ''))
        
        assert verification[0] is True
        assert "verified" in verification[1].lower()
    
    def test_verification_counts_for_ui(self, tmp_path):
        """Test counting verified/failed files for UI display.
        
        Simulates the TUI code counting verifications:
        verified_count = sum(1 for f in files if status['hash_verification'].get(f, (None,))[0] is True)
        """
        target_dir = str(tmp_path / "downloads")
        manager = downloads.DownloadManager(target_dir)
        
        # Add mock data
        files = ["/path/file1.iso", "/path/file2.iso", "/path/file3.iso"]
        manager.hash_verification[files[0]] = (True, "OK")
        manager.hash_verification[files[1]] = (False, "Failed")
        manager.hash_verification[files[2]] = (None, "No hash")
        
        status = manager.get_status()
        
        # Count like UI does
        verified_count = sum(1 for f in files 
                           if status['hash_verification'].get(f, (None,))[0] is True)
        failed_count = sum(1 for f in files 
                         if status['hash_verification'].get(f, (None,))[0] is False)
        
        assert verified_count == 1
        assert failed_count == 1
