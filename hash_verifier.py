#!/usr/bin/env python3
"""Hash verification module for downloaded ISO files."""

import hashlib
import re
import requests
from pathlib import Path
from typing import Tuple, Optional, Dict


class HashVerifier:
    """Verify downloaded files against published checksums."""
    
    # Distro-specific hash file patterns
    HASH_PATTERNS = {
        'ubuntu': '{base_url}/SHA256SUMS',
        'debian': '{base_url}/SHA256SUMS.txt',
        'rocky': '{base_url}/CHECKSUM',
        'fedora': 'api',  # Use releases.json
        'arch': '{iso_url}.sig',
        'archlinux': '{base_url}/sha256sums.txt',
        'opensuse': '{iso_url}.sha256',
        'mint': '{base_url}/sha256sum.txt',
        'manjaro': '{iso_url}.sha256',
        'popos': '{base_url}/SHA256SUMS',
        'pop-os': '{base_url}/SHA256SUMS',
        'kali': '{base_url}/SHA256SUMS',
        'endeavouros': '{base_url}/sha256sum.txt',
        'zorin': '{base_url}/sha256sum.txt',
        'mx': '{base_url}/md5.txt',  # MX uses MD5
        'alpine': '{base_url}/sha256sum.txt',
        'fedora': '{base_url}/Fedora-*-CHECKSUM',
    }
    
    @staticmethod
    def compute_sha256(filepath: str) -> str:
        """
        Compute SHA256 hash of a file.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Lowercase hex string of SHA256 hash
        """
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192 * 1024), b''):  # 8MB chunks
                sha256.update(chunk)
        return sha256.hexdigest().lower()
    
    @staticmethod
    def fetch_hash_file(url: str, timeout: int = 30) -> Optional[str]:
        """
        Download and return hash file content.
        
        Args:
            url: URL to the hash file
            timeout: Request timeout in seconds
            
        Returns:
            Hash file content or None on error
        """
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"    Warning: Could not fetch hash file from {url}: {e}")
            return None
    
    @staticmethod
    def parse_sha256sums(content: str, filename: Optional[str] = None) -> Dict[str, str]:
        """
        Parse SHA256SUMS format files.
        
        Format examples:
            <hash> *<filename>
            <hash>  <filename>
            <hash> (<filename>)
        
        Args:
            content: Content of the hash file
            filename: If provided, return only hash for this file
            
        Returns:
            Dict of filename -> hash, or single hash if filename specified
        """
        lines = content.strip().split('\n')
        hashes = {}
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Try different formats
            # Format 1: hash *filename or hash  filename
            match = re.match(r'([a-fA-F0-9]{64})\s+\*?(.+)$', line)
            if not match:
                # Format 2: hash (filename)
                match = re.match(r'([a-fA-F0-9]{64})\s+\((.+)\)$', line)
            
            if match:
                hash_val, fname = match.groups()
                fname = fname.strip().lstrip('./')
                hashes[fname] = hash_val.lower()
        
        if filename:
            # Try exact match first
            if filename in hashes:
                return hashes[filename]
            # Try basename match
            basename = Path(filename).name
            if basename in hashes:
                return hashes[basename]
            # Try case-insensitive match
            for fname, hash_val in hashes.items():
                if fname.lower() == basename.lower():
                    return hash_val
            return None
        
        return hashes
    
    @staticmethod
    def get_hash_url(iso_url: str, distro: Optional[str] = None) -> Optional[str]:
        """
        Determine hash file URL from ISO URL.
        
        Args:
            iso_url: URL to the ISO file
            distro: Distribution name (auto-detected if None)
            
        Returns:
            URL to hash file or None if unknown
        """
        # Auto-detect distro if not provided
        if not distro:
            url_lower = iso_url.lower()
            for d in HashVerifier.HASH_PATTERNS.keys():
                if d in url_lower:
                    distro = d
                    break
        
        if not distro or distro not in HashVerifier.HASH_PATTERNS:
            # Try common patterns
            base_url = iso_url.rsplit('/', 1)[0]
            for common in ['SHA256SUMS', 'sha256sum.txt', 'CHECKSUM']:
                return f"{base_url}/{common}"
            return None
        
        pattern = HashVerifier.HASH_PATTERNS.get(distro)
        if not pattern or pattern == 'api':
            return None
        
        if '{iso_url}' in pattern:
            return pattern.format(iso_url=iso_url)
        
        # For base_url patterns, extract directory
        base_url = iso_url.rsplit('/', 1)[0]
        
        # Handle wildcards (for Fedora CHECKSUM files)
        if '*' in pattern:
            # Try to fetch directory listing and find matching file
            try:
                r = requests.get(base_url + '/', timeout=10)
                if r.status_code == 200:
                    # Look for CHECKSUM file
                    checksum_match = re.search(r'href="([^"]*CHECKSUM[^"]*)"', r.text, re.IGNORECASE)
                    if checksum_match:
                        return f"{base_url}/{checksum_match.group(1)}"
            except:
                pass
            return None
        
        return pattern.format(base_url=base_url)
    
    @staticmethod
    def verify_file(
        filepath: str,
        expected_hash: Optional[str] = None,
        iso_url: Optional[str] = None,
        fedora_hash: Optional[str] = None
    ) -> Tuple[Optional[bool], str, str]:
        """
        Verify file integrity against checksums.
        
        Args:
            filepath: Path to downloaded file
            expected_hash: Expected SHA256 hash (optional)
            iso_url: Original download URL (for auto-fetching hash)
            fedora_hash: Fedora API hash (if available)
        
        Returns:
            Tuple of (success: bool|None, message: str, computed_hash: str)
            - success=True: Hash verified successfully
            - success=False: Hash verification failed
            - success=None: No hash available for verification
        """
        file_path = Path(filepath)
        if not file_path.exists():
            return False, "File not found", ""
        
        filename = file_path.name
        
        # Compute actual hash
        try:
            computed = HashVerifier.compute_sha256(filepath)
        except Exception as e:
            return False, f"Error computing hash: {e}", ""
        
        # Priority 1: Use provided expected hash (from Fedora API)
        if fedora_hash:
            expected_hash = fedora_hash
        
        # Priority 2: Try to fetch hash file if URL provided and no hash yet
        if not expected_hash and iso_url:
            hash_url = HashVerifier.get_hash_url(iso_url)
            if hash_url:
                hash_content = HashVerifier.fetch_hash_file(hash_url)
                if hash_content:
                    expected_hash = HashVerifier.parse_sha256sums(hash_content, filename)
        
        # No hash available
        if not expected_hash:
            return None, f"No hash available (computed: {computed[:16]}...)", computed
        
        # Normalize hashes
        expected_hash = expected_hash.lower().strip()
        computed = computed.lower().strip()
        
        # Compare
        if computed == expected_hash:
            return True, "✓ Hash verified successfully", computed
        else:
            return False, f"✗ Hash mismatch! Expected: {expected_hash[:16]}..., Got: {computed[:16]}...", computed
    
    @staticmethod
    def verify_file_simple(filepath: str, iso_url: str) -> bool:
        """
        Simple verification that returns just True/False/None.
        
        Args:
            filepath: Path to downloaded file
            iso_url: Original download URL
            
        Returns:
            True if verified, False if failed, None if no hash available
        """
        success, _, _ = HashVerifier.verify_file(filepath, iso_url=iso_url)
        return success


if __name__ == '__main__':
    # Test the verifier
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hash_verifier.py <filepath> [iso_url]")
        sys.exit(1)
    
    filepath = sys.argv[1]
    iso_url = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Verifying: {filepath}")
    if iso_url:
        print(f"URL: {iso_url}")
    
    success, message, computed = HashVerifier.verify_file(filepath, iso_url=iso_url)
    
    print(f"\nResult: {message}")
    print(f"Computed hash: {computed}")
    
    if success is True:
        sys.exit(0)
    elif success is False:
        sys.exit(1)
    else:
        sys.exit(2)
