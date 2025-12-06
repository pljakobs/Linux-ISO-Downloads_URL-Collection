#!/usr/bin/env python3
"""
Verify torrent support implementation.
"""

import sys


def main():
    print("=" * 60)
    print("Torrent Support Verification")
    print("=" * 60)
    print()
    
    # Check aria2c availability
    from torrent_downloader import TorrentDownloader, check_aria2c_installation
    
    available, message = check_aria2c_installation()
    
    if available:
        print("✅ aria2c is installed and available")
        print(f"   {message}")
    else:
        print("⚠️  aria2c is NOT installed")
        print()
        print(message)
    
    print()
    print("-" * 60)
    print("URL Detection Tests")
    print("-" * 60)
    
    test_urls = [
        ("http://example.com/ubuntu.torrent", True, "Torrent file"),
        ("https://example.com/FILE.TORRENT", True, "Torrent file (uppercase)"),
        ("magnet:?xt=urn:btih:123456", True, "Magnet link"),
        ("http://example.com/ubuntu.iso", False, "Regular ISO"),
        ("https://example.com/file.zip", False, "ZIP file"),
    ]
    
    all_pass = True
    for url, expected, description in test_urls:
        result = TorrentDownloader.is_torrent_url(url)
        status = "✅" if result == expected else "❌"
        all_pass = all_pass and (result == expected)
        print(f"{status} {description}: {url[:50]}...")
    
    print()
    print("-" * 60)
    print("Integration Test")
    print("-" * 60)
    
    # Check that downloads.py imports torrent_downloader
    try:
        import downloads
        if hasattr(downloads, 'TorrentDownloader'):
            print("✅ DownloadManager has torrent support integrated")
        else:
            print("⚠️  TorrentDownloader not imported in downloads.py")
    except ImportError as e:
        print(f"❌ Error importing downloads: {e}")
        all_pass = False
    
    print()
    print("-" * 60)
    print("Test Suite")
    print("-" * 60)
    
    import subprocess
    result = subprocess.run(
        ['python', '-m', 'pytest', 'tests/test_torrent_downloader.py', '-v', '--tb=short'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        # Count passed tests
        import re
        matches = re.findall(r'(\d+) passed', result.stdout)
        if matches:
            print(f"✅ All {matches[0]} tests passed")
        else:
            print("✅ Tests passed")
    else:
        print("❌ Some tests failed")
        print(result.stdout)
        all_pass = False
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    if all_pass:
        print("✅ Torrent support is fully implemented and tested")
        print()
        if not available:
            print("📋 Next step: Install aria2c to enable torrent downloads")
            print("   See TORRENT_SUPPORT.md for installation instructions")
        else:
            print("🎉 Ready to download torrents!")
        return 0
    else:
        print("❌ Some issues detected - review output above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
