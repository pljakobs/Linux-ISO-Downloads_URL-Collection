#!/usr/bin/env python3
"""
Torrent download module for distroget.
Handles torrent downloads via aria2c when available.
"""

import os
import subprocess
import re
import shutil
import logging
from threading import Lock

# Set up logger
logger = logging.getLogger('distroget.torrent')


class TorrentDownloader:
    """Handles torrent downloads using aria2c."""
    
    # Class-level cache for aria2c availability
    _aria2c_available = None
    _check_lock = Lock()
    
    def __init__(self, target_dir):
        """
        Initialize the torrent downloader.
        
        Args:
            target_dir: Directory to save downloaded files
        """
        self.target_dir = target_dir
        self.progress = 0  # Downloaded bytes
        self.total = 0  # Total bytes
        self.progress_percent = 0  # Progress percentage
        self.download_speed = 0
        self.upload_speed = 0
        self.connections = 0
        self.process = None
        
    @classmethod
    def is_available(cls):
        """
        Check if aria2c is available on the system.
        Uses caching to avoid repeated checks.
        
        Returns:
            bool: True if aria2c is available
        """
        with cls._check_lock:
            if cls._aria2c_available is None:
                cls._aria2c_available = shutil.which('aria2c') is not None
            return cls._aria2c_available
    
    @staticmethod
    def is_torrent_url(url):
        """
        Check if URL is a torrent file or magnet link.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL is for a torrent
        """
        url_lower = url.lower()
        return url_lower.endswith('.torrent') or url_lower.startswith('magnet:')
    
    def download(self, url, progress_callback=None):
        """
        Download a torrent file.
        
        Args:
            url: Torrent URL or magnet link
            progress_callback: Optional callback function(progress, total, speed)
            
        Returns:
            str: Path to downloaded file
            
        Raises:
            RuntimeError: If aria2c is not available
            subprocess.CalledProcessError: If download fails
        """
        logger.info(f"Starting torrent download: {url}")
        
        if not self.is_available():
            logger.error("aria2c is not available")
            raise RuntimeError("aria2c is not installed. Install it to enable torrent downloads.")
        
        # aria2c options:
        # --dir: Output directory
        # --seed-time=0: Don't seed after download (we're not a torrent client)
        # --summary-interval=1: Update progress every second
        # --console-log-level=notice: Moderate logging
        # --max-connection-per-server=5: Reasonable connection limit
        # --split=5: Split download into 5 parts
        # --file-allocation=none: Don't pre-allocate file (faster start)
        cmd = [
            'aria2c',
            '--dir', self.target_dir,
            '--seed-time=0',
            '--summary-interval=1',
            '--console-log-level=notice',
            '--max-connection-per-server=5',
            '--split=5',
            '--file-allocation=none',
            '--check-certificate=true',
            url
        ]
        
        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Parse output for progress
            for line in self.process.stdout:
                logger.debug(f"aria2c output: {line.strip()}")
                self._parse_progress(line)
                
                if progress_callback:
                    progress_callback(self.progress, self.total, self.download_speed)
            
            # Wait for completion
            return_code = self.process.wait()
            
            if return_code != 0:
                logger.error(f"aria2c failed with return code {return_code}")
                raise subprocess.CalledProcessError(return_code, cmd)
            
            logger.info(f"Torrent download completed successfully")
            
            # Find the downloaded file
            filename = self._extract_filename(url)
            filepath = os.path.join(self.target_dir, filename)
            
            if os.path.exists(filepath):
                return filepath
            else:
                # aria2c might have changed the filename
                # Look for recently created files in target_dir
                raise FileNotFoundError(f"Downloaded file not found: {filepath}")
                
        except Exception as e:
            logger.exception(f"Torrent download failed: {e}")
            if self.process:
                self.process.kill()
            raise
    
    def _parse_progress(self, line):
        """
        Parse aria2c output line to extract progress information.
        
        Example line:
        [#123456 7.5MiB/100MiB(7%) CN:5 DL:2.5MiB ETA:30s]
        
        Args:
            line: Output line from aria2c
        """
        # Parse percentage
        if match := re.search(r'\((\d+)%\)', line):
            self.progress_percent = int(match.group(1))
        
        # Parse downloaded/total size
        if match := re.search(r'(\d+(?:\.\d+)?)(MiB|GiB|KiB)/(\d+(?:\.\d+)?)(MiB|GiB|KiB)', line):
            downloaded = float(match.group(1))
            downloaded_unit = match.group(2)
            total = float(match.group(3))
            total_unit = match.group(4)
            
            # Convert to bytes
            self.progress = self._to_bytes(downloaded, downloaded_unit)
            self.total = self._to_bytes(total, total_unit)
        
        # Parse download speed
        if match := re.search(r'DL:(\d+(?:\.\d+)?)(MiB|GiB|KiB)', line):
            speed = float(match.group(1))
            unit = match.group(2)
            self.download_speed = self._to_bytes(speed, unit)
        
        # Parse connections
        if match := re.search(r'CN:(\d+)', line):
            self.connections = int(match.group(1))
    
    @staticmethod
    def _to_bytes(value, unit):
        """Convert size with unit to bytes."""
        units = {
            'B': 1,
            'KiB': 1024,
            'MiB': 1024**2,
            'GiB': 1024**3
        }
        return int(value * units.get(unit, 1))
    
    @staticmethod
    def _extract_filename(url):
        """
        Extract filename from torrent URL.
        For magnet links, aria2c will determine the name.
        
        Args:
            url: Torrent URL or magnet link
            
        Returns:
            str: Extracted filename or generic name for magnet links
        """
        if url.startswith('magnet:'):
            # For magnet links, try to extract name from dn parameter
            if match := re.search(r'[&?]dn=([^&]+)', url):
                return match.group(1)
            return 'download'  # aria2c will determine actual name
        else:
            # For .torrent files, use the filename
            return url.split('/')[-1].replace('.torrent', '')
    
    def stop(self):
        """Stop the download process."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def check_aria2c_installation():
    """
    Check if aria2c is installed and provide installation instructions.
    
    Returns:
        tuple: (is_available, message)
    """
    available = TorrentDownloader.is_available()
    
    if available:
        try:
            result = subprocess.run(
                ['aria2c', '--version'],
                capture_output=True,
                text=True,
                timeout=2
            )
            version = result.stdout.split('\n')[0] if result.stdout else 'unknown version'
            return True, f"aria2c is available: {version}"
        except Exception:
            return True, "aria2c is available"
    else:
        message = """
aria2c is not installed. To enable torrent downloads:

Ubuntu/Debian:  sudo apt install aria2
Fedora/RHEL:    sudo dnf install aria2
openSUSE:       sudo zypper install aria2
Arch Linux:     sudo pacman -S aria2
macOS:          brew install aria2
        """.strip()
        return False, message
