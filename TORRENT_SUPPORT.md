# Torrent Download Support

## Overview

distroget now supports downloading ISO files via BitTorrent when `.torrent` files or magnet links are provided. This can significantly speed up downloads for popular distributions that offer torrent downloads.

## Implementation

Torrent support is implemented through **aria2c**, a lightweight command-line download utility that supports:
- HTTP/HTTPS
- FTP  
- BitTorrent
- Metalink

### Key Features

✅ **Zero Python dependencies** - Uses external `aria2c` binary
✅ **Automatic detection** - Detects `.torrent` URLs and magnet links automatically
✅ **Progress tracking** - Real-time progress updates in the UI
✅ **Graceful fallback** - Falls back to HTTP if aria2c is not available
✅ **Integrated with existing download manager** - Works seamlessly with the current download system

## Installation

### Install aria2c

**Ubuntu/Debian:**
```bash
sudo apt install aria2
```

**Fedora/RHEL:**
```bash
sudo dnf install aria2
```

**openSUSE:**
```bash
sudo zypper install aria2
```

**Arch Linux:**
```bash
sudo pacman -S aria2
```

**macOS:**
```bash
brew install aria2
```

## Usage

### In the UI

Torrent downloads work automatically in distroget:

1. If a distro provides a `.torrent` URL, it will be detected
2. If `aria2c` is installed, the torrent will be downloaded
3. Progress is shown in the download panel just like HTTP downloads
4. If `aria2c` is not installed, an error message is shown

### Checking aria2c Availability

```python
from torrent_downloader import TorrentDownloader, check_aria2c_installation

# Check if aria2c is available
if TorrentDownloader.is_available():
    print("Torrent downloads are supported!")
else:
    available, message = check_aria2c_installation()
    print(message)  # Shows installation instructions
```

### Direct Usage

```python
from torrent_downloader import TorrentDownloader

# Create downloader
downloader = TorrentDownloader('/path/to/download/dir')

# Download a torrent
def progress_callback(progress, total, speed):
    print(f"Progress: {progress}/{total} bytes @ {speed} bytes/s")

downloader.download('http://example.com/ubuntu.torrent', progress_callback)
```

## Architecture

### Module Structure

```
torrent_downloader.py
├── TorrentDownloader       # Main downloader class
│   ├── is_available()      # Check if aria2c is installed (cached)
│   ├── is_torrent_url()    # Detect .torrent URLs and magnet links
│   ├── download()          # Download torrent with progress tracking
│   ├── _parse_progress()   # Parse aria2c output for progress
│   └── stop()              # Stop download process
└── check_aria2c_installation() # Check installation and provide instructions
```

### Integration with DownloadManager

The `DownloadManager` in `downloads.py` automatically detects torrent URLs:

```python
def _download_file(self, url, filename):
    # Check if this is a torrent
    if TorrentDownloader.is_torrent_url(url):
        if TorrentDownloader.is_available():
            return self._download_torrent(url, filename)
        else:
            raise RuntimeError("aria2c not installed")
    
    # Fall back to HTTP download
    ...
```

### Progress Tracking

aria2c outputs progress information in this format:
```
[#123456 7.5MiB/100MiB(7%) CN:5 DL:2.5MiB ETA:30s]
```

The `_parse_progress()` method extracts:
- **Progress percentage**: `7%`
- **Downloaded/Total size**: `7.5MiB/100MiB` → converted to bytes
- **Download speed**: `2.5MiB` → converted to bytes/s
- **Connection count**: `CN:5` → 5 active connections

## Configuration

aria2c is invoked with these options:

```bash
aria2c \
  --dir /download/path \           # Output directory
  --seed-time=0 \                  # Don't seed after download
  --summary-interval=1 \           # Update progress every second
  --console-log-level=notice \     # Moderate logging
  --max-connection-per-server=5 \  # Limit connections
  --split=5 \                      # Split download into 5 parts
  --file-allocation=none \         # Faster start (no pre-allocation)
  --check-certificate=true \       # Verify SSL certificates
  <url>
```

## Testing

Run torrent downloader tests:

```bash
python -m pytest tests/test_torrent_downloader.py -v
```

Test coverage includes:
- ✅ URL detection (.torrent and magnet links)
- ✅ aria2c availability checking (with caching)
- ✅ Progress parsing from aria2c output
- ✅ Filename extraction from URLs
- ✅ Error handling when aria2c is not available
- ✅ Process management (start/stop)

## Example Distros with Torrent Support

Several distributions provide torrent downloads:

- **Endless OS**: `https://images-dl.endlessm.com/torrents/*.torrent`
- **Ubuntu**: Some mirrors provide `.torrent` files
- **Linux Mint**: Torrent files available on download page
- **Manjaro**: Provides torrent links for all ISOs

## Advantages of Torrent Downloads

1. **Faster downloads**: Distributed download from multiple peers
2. **Resilient**: Can resume interrupted downloads
3. **Bandwidth efficient**: Reduces load on official mirrors
4. **Verification**: Built-in integrity checking via piece hashes

## Limitations

- Requires `aria2c` to be installed separately
- Torrent downloads don't seed after completion (by design)
- Progress tracking depends on aria2c output format
- Some corporate firewalls may block torrent traffic

## Future Enhancements

Potential improvements:

1. **Optional seeding**: Add configuration to seed after download
2. **DHT support**: Enable DHT for magnet links without trackers
3. **Bandwidth limits**: Add download/upload speed limits
4. **Torrent creation**: Create .torrent files for local ISOs
5. **Tracker management**: Configurable tracker lists

## Security Considerations

- ✅ SSL certificate verification enabled by default
- ✅ Downloads only to specified directory (no path traversal)
- ✅ Process isolation via subprocess
- ✅ Timeout handling to prevent hanging downloads
- ✅ No seeding after download (reduces exposure)

## Troubleshooting

### aria2c not found

```
Error: aria2c is not installed
```

**Solution**: Install aria2 using your package manager (see Installation section)

### Torrent download fails

```
Error: Torrent download failed: <reason>
```

**Possible causes**:
- No seeders available
- Firewall blocking BitTorrent ports
- Invalid torrent file or magnet link

**Solution**: Try HTTP download instead or check firewall settings

### Slow torrent downloads

**Possible causes**:
- Few seeders
- ISP throttling BitTorrent traffic
- Connection limits too low

**Solution**: 
- Wait for more seeders
- Use VPN if ISP throttles torrents
- Adjust aria2c connection settings
