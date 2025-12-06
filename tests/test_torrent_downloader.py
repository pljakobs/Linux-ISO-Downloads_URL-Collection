#!/usr/bin/env python3
"""Tests for torrent downloader module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import subprocess
import tempfile
import os
from torrent_downloader import TorrentDownloader, check_aria2c_installation


class TestTorrentDownloader(unittest.TestCase):
    """Test cases for TorrentDownloader class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = TorrentDownloader(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """Test downloader initialization."""
        self.assertEqual(self.downloader.target_dir, self.temp_dir)
        self.assertEqual(self.downloader.progress, 0)
        self.assertEqual(self.downloader.total, 0)
        self.assertIsNone(self.downloader.process)
    
    def test_is_torrent_url_torrent_file(self):
        """Test detection of .torrent URLs."""
        self.assertTrue(TorrentDownloader.is_torrent_url(
            'http://example.com/file.torrent'
        ))
        self.assertTrue(TorrentDownloader.is_torrent_url(
            'https://example.com/FILE.TORRENT'
        ))
    
    def test_is_torrent_url_magnet(self):
        """Test detection of magnet links."""
        self.assertTrue(TorrentDownloader.is_torrent_url(
            'magnet:?xt=urn:btih:123456789'
        ))
        self.assertTrue(TorrentDownloader.is_torrent_url(
            'MAGNET:?xt=urn:btih:abcdef'
        ))
    
    def test_is_torrent_url_regular_url(self):
        """Test that regular URLs are not detected as torrents."""
        self.assertFalse(TorrentDownloader.is_torrent_url(
            'http://example.com/file.iso'
        ))
        self.assertFalse(TorrentDownloader.is_torrent_url(
            'https://example.com/file.zip'
        ))
    
    @patch('shutil.which')
    def test_is_available_when_installed(self, mock_which):
        """Test availability check when aria2c is installed."""
        mock_which.return_value = '/usr/bin/aria2c'
        # Clear cache
        TorrentDownloader._aria2c_available = None
        
        self.assertTrue(TorrentDownloader.is_available())
        mock_which.assert_called_with('aria2c')
    
    @patch('shutil.which')
    def test_is_available_when_not_installed(self, mock_which):
        """Test availability check when aria2c is not installed."""
        mock_which.return_value = None
        # Clear cache
        TorrentDownloader._aria2c_available = None
        
        self.assertFalse(TorrentDownloader.is_available())
    
    @patch('shutil.which')
    def test_is_available_caching(self, mock_which):
        """Test that availability check is cached."""
        mock_which.return_value = '/usr/bin/aria2c'
        # Clear cache
        TorrentDownloader._aria2c_available = None
        
        # First call
        TorrentDownloader.is_available()
        # Second call should use cache
        TorrentDownloader.is_available()
        
        # Should only call which once
        self.assertEqual(mock_which.call_count, 1)
    
    def test_parse_progress_percentage(self):
        """Test parsing progress percentage from aria2c output."""
        line = "[#123456 7.5MiB/100MiB(7%) CN:5 DL:2.5MiB]"
        self.downloader._parse_progress(line)
        self.assertEqual(self.downloader.progress_percent, 7)
    
    def test_parse_progress_size(self):
        """Test parsing download size from aria2c output."""
        line = "[#123456 7.5MiB/100MiB(7%) CN:5 DL:2.5MiB]"
        self.downloader._parse_progress(line)
        
        # Check sizes are converted to bytes
        self.assertEqual(self.downloader.progress, int(7.5 * 1024 * 1024))
        self.assertEqual(self.downloader.total, int(100 * 1024 * 1024))
    
    def test_parse_progress_connections(self):
        """Test parsing connection count from aria2c output."""
        line = "[#123456 7.5MiB/100MiB(7%) CN:5 DL:2.5MiB]"
        self.downloader._parse_progress(line)
        self.assertEqual(self.downloader.connections, 5)
    
    def test_to_bytes_conversions(self):
        """Test byte conversion for different units."""
        self.assertEqual(TorrentDownloader._to_bytes(1, 'B'), 1)
        self.assertEqual(TorrentDownloader._to_bytes(1, 'KiB'), 1024)
        self.assertEqual(TorrentDownloader._to_bytes(1, 'MiB'), 1024**2)
        self.assertEqual(TorrentDownloader._to_bytes(1, 'GiB'), 1024**3)
        self.assertEqual(TorrentDownloader._to_bytes(2.5, 'MiB'), int(2.5 * 1024**2))
    
    def test_extract_filename_torrent(self):
        """Test filename extraction from .torrent URL."""
        url = 'http://example.com/ubuntu-24.04.torrent'
        filename = TorrentDownloader._extract_filename(url)
        self.assertEqual(filename, 'ubuntu-24.04')
    
    def test_extract_filename_magnet_with_name(self):
        """Test filename extraction from magnet link with name."""
        url = 'magnet:?xt=urn:btih:123&dn=ubuntu-24.04.iso'
        filename = TorrentDownloader._extract_filename(url)
        self.assertEqual(filename, 'ubuntu-24.04.iso')
    
    def test_extract_filename_magnet_without_name(self):
        """Test filename extraction from magnet link without name."""
        url = 'magnet:?xt=urn:btih:123456789'
        filename = TorrentDownloader._extract_filename(url)
        self.assertEqual(filename, 'download')
    
    @patch('subprocess.Popen')
    @patch.object(TorrentDownloader, 'is_available', return_value=False)
    def test_download_aria2c_not_available(self, mock_available, mock_popen):
        """Test download raises error when aria2c is not available."""
        with self.assertRaises(RuntimeError) as cm:
            self.downloader.download('http://example.com/file.torrent')
        
        self.assertIn('aria2c is not installed', str(cm.exception))
        mock_popen.assert_not_called()
    
    @patch('subprocess.Popen')
    @patch.object(TorrentDownloader, 'is_available', return_value=True)
    def test_download_command_format(self, mock_available, mock_popen):
        """Test that download uses correct aria2c command."""
        # Mock process
        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        # Create a test file to simulate download
        test_file = os.path.join(self.temp_dir, 'test.torrent')
        with open(test_file, 'w') as f:
            f.write('test')
        
        url = 'http://example.com/test.torrent'
        
        try:
            self.downloader.download(url)
        except FileNotFoundError:
            # Expected - file not actually downloaded in test
            pass
        
        # Check command format
        call_args = mock_popen.call_args[0][0]
        self.assertEqual(call_args[0], 'aria2c')
        self.assertIn('--dir', call_args)
        self.assertIn(self.temp_dir, call_args)
        self.assertIn('--seed-time=0', call_args)
        self.assertIn(url, call_args)
    
    def test_stop_kills_process(self):
        """Test that stop() terminates the process."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        self.downloader.process = mock_process
        
        self.downloader.stop()
        
        mock_process.terminate.assert_called_once()


class TestCheckAria2cInstallation(unittest.TestCase):
    """Test cases for aria2c installation check."""
    
    @patch('subprocess.run')
    @patch.object(TorrentDownloader, 'is_available', return_value=True)
    def test_check_installation_available(self, mock_available, mock_run):
        """Test installation check when aria2c is available."""
        mock_run.return_value = MagicMock(
            stdout='aria2 version 1.36.0'
        )
        
        available, message = check_aria2c_installation()
        
        self.assertTrue(available)
        self.assertIn('aria2c is available', message)
        self.assertIn('1.36.0', message)
    
    @patch.object(TorrentDownloader, 'is_available', return_value=False)
    def test_check_installation_not_available(self, mock_available):
        """Test installation check when aria2c is not available."""
        available, message = check_aria2c_installation()
        
        self.assertFalse(available)
        self.assertIn('not installed', message)
        self.assertIn('apt install', message)
        self.assertIn('dnf install', message)


if __name__ == '__main__':
    unittest.main()
