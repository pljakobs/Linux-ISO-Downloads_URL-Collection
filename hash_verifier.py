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
    # Note: Order matters for detection - more specific patterns should come first
    HASH_PATTERNS = {
        'ubuntu': '{base_url}/SHA256SUMS',
        'debian': '{base_url}/SHA256SUMS',  # Fixed: was SHA256SUMS.txt
        'rocky': '{base_url}/CHECKSUM',
        'fedora': '{base_url}/Fedora-*-CHECKSUM',  # Removed duplicate 'api' entry
        'archlinux': '{base_url}/sha256sums.txt',  # Must check before 'arch' substring
        'opensuse': '{iso_url}.sha256',
        'mint': '{base_url}/sha256sum.txt',
        'manjaro': '{iso_url}-sha256.sum',  # Fixed: was {iso_url}.sha256
        'popos': '{base_url}/SHA256SUMS',
        'pop-os': '{base_url}/SHA256SUMS',
        'kali': '{base_url}/SHA256SUMS',
        'endeavouros': '{iso_url}.sha512sum',  # Fixed: uses per-file sha512sum
        'zorin': '{base_url}/sha256sum.txt',
        'mx': '{iso_url}.sha256',  # Fixed: uses per-file SHA256, not md5.txt
        'alpine': '{iso_url}.sha256',  # Fixed: uses per-file .sha256
    }

    # Ordered list for distro detection (more specific patterns first)
    # This prevents 'arch' matching 'archive.kali.org' or 'archlinux'
    DISTRO_DETECTION_ORDER = [
        'archlinux',  # Must come before 'arch' would match
        'endeavouros',
        'opensuse',
        'linuxmint', 'mint',
        'manjaro',
        'pop-os', 'popos',
        'kali',
        'alpine',
        'ubuntu',
        'debian',
        'fedora',
        'rocky',
        'zorin',
        'mx',
    ]
    
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
    def compute_sha512(filepath: str) -> str:
        """
        Compute SHA512 hash of a file.

        Args:
            filepath: Path to the file

        Returns:
            Lowercase hex string of SHA512 hash
        """
        sha512 = hashlib.sha512()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192 * 1024), b''):  # 8MB chunks
                sha512.update(chunk)
        return sha512.hexdigest().lower()

    @staticmethod
    def compute_hash(filepath: str, algorithm: str = 'sha256') -> str:
        """
        Compute hash of a file using specified algorithm.

        Args:
            filepath: Path to the file
            algorithm: Hash algorithm ('md5', 'sha256', 'sha512')

        Returns:
            Lowercase hex string of hash
        """
        if algorithm == 'sha512':
            return HashVerifier.compute_sha512(filepath)
        elif algorithm == 'md5':
            md5 = hashlib.md5()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192 * 1024), b''):
                    md5.update(chunk)
            return md5.hexdigest().lower()
        else:
            return HashVerifier.compute_sha256(filepath)
    
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
    def parse_hash_file(content: str, filename: Optional[str] = None) -> Dict[str, str]:
        """
        Parse hash file in various formats (SHA256SUMS, SHA512SUMS, MD5SUMS, etc.).

        Supports multiple hash lengths:
            - MD5: 32 hex characters
            - SHA256: 64 hex characters
            - SHA512: 128 hex characters

        Format examples:
            <hash> *<filename>
            <hash>  <filename>
            <hash> (<filename>)
            SHA256 (<filename>) = <hash>  (BSD-style, used by Fedora)

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
            # Format 1: hash *filename or hash  filename (MD5/SHA256/SHA512)
            # Matches 32, 64, or 128 hex chars
            match = re.match(r'([a-fA-F0-9]{32}(?:[a-fA-F0-9]{32})?(?:[a-fA-F0-9]{64})?)\s+\*?(.+)$', line)
            if not match:
                # Format 2: hash (filename)
                match = re.match(r'([a-fA-F0-9]{32}(?:[a-fA-F0-9]{32})?(?:[a-fA-F0-9]{64})?)\s+\((.+)\)$', line)
            if not match:
                # Format 3: BSD-style - SHA256 (filename) = hash (used by Fedora)
                match = re.match(r'(?:SHA256|SHA512|MD5)\s+\((.+)\)\s+=\s+([a-fA-F0-9]+)$', line)
                if match:
                    # Swap groups for BSD format (filename first, then hash)
                    fname, hash_val = match.groups()
                    fname = fname.strip().lstrip('./')
                    hashes[fname] = hash_val.lower()
                    continue

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

    # Alias for backwards compatibility
    parse_sha256sums = parse_hash_file
    
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
            # Use ordered detection to avoid substring collisions
            # e.g., 'arch' in 'archive.kali.org' or 'archlinux'
            for d in HashVerifier.DISTRO_DETECTION_ORDER:
                if d in url_lower:
                    distro = d
                    break

        if not distro or distro not in HashVerifier.HASH_PATTERNS:
            # Try common patterns - actually attempt each one
            base_url = iso_url.rsplit('/', 1)[0]
            common_patterns = ['SHA256SUMS', 'sha256sum.txt', 'CHECKSUM']
            for common in common_patterns:
                test_url = f"{base_url}/{common}"
                try:
                    r = requests.head(test_url, timeout=5, allow_redirects=True)
                    if r.status_code == 200:
                        return test_url
                except requests.RequestException:
                    continue
            # If none found, return the most common one as fallback
            return f"{base_url}/SHA256SUMS"

        pattern = HashVerifier.HASH_PATTERNS.get(distro)
        if not pattern:
            return None

        # Handle per-file hash patterns (contain {iso_url})
        if '{iso_url}' in pattern:
            # For manjaro, need to transform the URL
            # manjaro-xfce-23.0.iso -> manjaro-xfce-23.0-sha256.sum
            if distro == 'manjaro':
                # Remove .iso extension and add -sha256.sum
                if iso_url.lower().endswith('.iso'):
                    return iso_url[:-4] + '-sha256.sum'
                return iso_url + '-sha256.sum'
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
            except requests.RequestException:
                pass
            return None

        return pattern.format(base_url=base_url)
    
    @staticmethod
    def _detect_hash_algorithm(hash_str: str) -> str:
        """Detect hash algorithm based on hash length."""
        length = len(hash_str.strip())
        if length == 32:
            return 'md5'
        elif length == 64:
            return 'sha256'
        elif length == 128:
            return 'sha512'
        else:
            return 'sha256'  # Default fallback

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
            expected_hash: Expected hash (optional, algorithm auto-detected)
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

        # Priority 1: Use provided expected hash (from Fedora API)
        if fedora_hash:
            expected_hash = fedora_hash

        # Priority 2: Try to fetch hash file if URL provided and no hash yet
        if not expected_hash and iso_url:
            hash_url = HashVerifier.get_hash_url(iso_url)
            if hash_url:
                hash_content = HashVerifier.fetch_hash_file(hash_url)
                if hash_content:
                    expected_hash = HashVerifier.parse_hash_file(hash_content, filename)

        # No hash available
        if not expected_hash:
            # Compute SHA256 for display purposes
            try:
                computed = HashVerifier.compute_sha256(filepath)
            except Exception as e:
                return None, f"No hash available (error computing: {e})", ""
            return None, f"No hash available (computed SHA256: {computed[:16]}...)", computed

        # Normalize expected hash
        expected_hash = expected_hash.lower().strip()

        # Detect algorithm based on hash length and compute appropriate hash
        algorithm = HashVerifier._detect_hash_algorithm(expected_hash)

        try:
            computed = HashVerifier.compute_hash(filepath, algorithm)
        except Exception as e:
            return False, f"Error computing {algorithm.upper()} hash: {e}", ""

        # Compare
        if computed == expected_hash:
            return True, f"✓ Hash verified successfully ({algorithm.upper()})", computed
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
