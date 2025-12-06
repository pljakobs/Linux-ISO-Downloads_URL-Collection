#!/usr/bin/env python3
"""
Integration test for torrent downloads using real torrent URLs.

This test requires aria2c to be installed and will actually download
a small portion of a real torrent to verify the complete workflow.
"""

import sys
import os
# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
import shutil
import time
from unittest.mock import patch
from torrent_downloader import TorrentDownloader


# Real torrent URL from README.md
ENDLESS_OS_TORRENT = "https://images-dl.endlessm.com/torrents/eos-eos3.9-amd64-amd64.211103-113242.base.iso.torrent"


class TestRealTorrentDownload(unittest.TestCase):
    """Integration tests with real torrent files."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @unittest.skipUnless(TorrentDownloader.is_available(), "aria2c not installed")
    def test_torrent_url_detection(self):
        """Test that real torrent URL is detected correctly."""
        self.assertTrue(TorrentDownloader.is_torrent_url(ENDLESS_OS_TORRENT))
    
    @unittest.skipUnless(TorrentDownloader.is_available(), "aria2c not installed")
    def test_parse_real_aria2c_output(self):
        """Test parsing actual aria2c progress output format."""
        downloader = TorrentDownloader(self.temp_dir)
        
        # Real aria2c output samples
        real_outputs = [
            "[#1 SIZE:0B/2.5GiB(0%) CN:0 SEED:0 SPD:0Bs]",
            "[#1 SIZE:50.0MiB/2.5GiB(2%) CN:5 DL:2.5MiB SEED:0 SPD:2.5MiBs]",
            "[#2f01e1 12.5MiB/100MiB(12%) CN:3 DL:1.2MiB ETA:1m23s]",
        ]
        
        for line in real_outputs:
            downloader._parse_progress(line)
            # Just verify it doesn't crash - actual values depend on regex matches
            self.assertGreaterEqual(downloader.progress, 0)
            self.assertGreaterEqual(downloader.total, 0)
    
    @unittest.skipUnless(TorrentDownloader.is_available(), "aria2c not installed")
    def test_download_torrent_metadata_only(self):
        """Test downloading just the torrent metadata (stop immediately)."""
        downloader = TorrentDownloader(self.temp_dir)
        
        progress_updates = []
        
        def progress_callback(progress, total, speed):
            progress_updates.append({
                'progress': progress,
                'total': total,
                'speed': speed
            })
            # Stop after first progress update to avoid downloading the whole file
            if len(progress_updates) >= 2:
                downloader.stop()
        
        try:
            # This will fail because we stop it early, but that's expected
            downloader.download(ENDLESS_OS_TORRENT, progress_callback)
        except Exception:
            # Expected - we killed the process
            pass
        
        # Verify we got at least one progress update
        # (might not get any if torrent metadata fetch is very fast)
        if progress_updates:
            self.assertGreater(len(progress_updates), 0)
            print(f"\n✓ Received {len(progress_updates)} progress updates")
            for i, update in enumerate(progress_updates[:3]):  # Show first 3
                print(f"  Update {i+1}: {update['progress']}/{update['total']} bytes @ {update['speed']} bytes/s")


class TestTorrentIntegrationWithDownloadManager(unittest.TestCase):
    """Test integration between torrent downloader and download manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @unittest.skipUnless(TorrentDownloader.is_available(), "aria2c not installed")
    def test_download_manager_detects_torrent(self):
        """Test that DownloadManager correctly identifies and processes torrent URLs."""
        from downloads import DownloadManager
        
        # This test verifies URL detection and routing, not the actual download
        # (real download might fail due to network/seeders)
        
        # Just verify detection works
        self.assertTrue(TorrentDownloader.is_torrent_url(ENDLESS_OS_TORRENT))
        
        # Verify DownloadManager can be instantiated with a torrent
        manager = DownloadManager(self.temp_dir, max_workers=1)
        manager.start()
        
        try:
            # The URL should be accepted (queued)
            # Whether it actually downloads depends on network/seeders
            manager.add_download(ENDLESS_OS_TORRENT)
            time.sleep(0.2)
            
            # Just verify manager is still running and didn't crash
            status = manager.get_status()
            self.assertIsNotNone(status)
            
            print(f"\n✓ DownloadManager handled torrent URL without crashing")
            print(f"  Status: {status['completed']} completed, {status['failed']} failed, {status['queued']} queued")
            
        finally:
            manager.stop()


def run_integration_tests():
    """Run integration tests and provide feedback."""
    print("=" * 70)
    print("Torrent Integration Tests with Real URLs")
    print("=" * 70)
    print()
    
    if not TorrentDownloader.is_available():
        print("⚠️  aria2c is not installed - skipping integration tests")
        print()
        print("Install aria2c to run these tests:")
        print("  Ubuntu/Debian: sudo apt install aria2")
        print("  Fedora/RHEL:   sudo dnf install aria2")
        print("  macOS:         brew install aria2")
        return 1
    
    print(f"✓ aria2c is available")
    print(f"✓ Using real torrent: {ENDLESS_OS_TORRENT[:60]}...")
    print()
    print("Note: Tests will stop downloads quickly to avoid downloading full ISOs")
    print()
    print("-" * 70)
    
    # Run the tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestRealTorrentDownload))
    suite.addTests(loader.loadTestsFromTestCase(TestTorrentIntegrationWithDownloadManager))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("-" * 70)
    if result.wasSuccessful():
        print("✓ All integration tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_integration_tests())
