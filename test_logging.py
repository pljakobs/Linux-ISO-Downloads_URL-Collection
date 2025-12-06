#!/usr/bin/env python3
"""
Test logging functionality with torrent detection.
"""

import logging
from logger_config import setup_logging, get_log_file
from torrent_downloader import TorrentDownloader

# Setup logging
log_file = setup_logging(log_level=logging.DEBUG)
logger = logging.getLogger('distroget.test')

print(f"Logging to: {log_file}")
print(f"Testing torrent detection and aria2c availability...\n")

# Test torrent URL detection
test_urls = [
    "https://images-dl.endlessm.com/torrents/eos-eos3.9-amd64-amd64.211103-113242.base.iso.torrent",
    "https://example.com/file.iso",
    "magnet:?xt=urn:btih:test"
]

logger.info("Starting torrent detection tests")

for url in test_urls:
    is_torrent = TorrentDownloader.is_torrent_url(url)
    logger.info(f"URL: {url[:60]}... -> is_torrent: {is_torrent}")
    print(f"{'✓' if is_torrent else '✗'} {url[:60]}... -> torrent: {is_torrent}")

# Test aria2c availability
print(f"\nChecking aria2c availability...")
logger.info("Checking aria2c availability")
is_available = TorrentDownloader.is_available()
logger.info(f"aria2c available: {is_available}")
print(f"{'✓' if is_available else '✗'} aria2c available: {is_available}")

print(f"\n✓ Logging test complete. Check log file: {log_file}")
