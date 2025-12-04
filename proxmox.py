#!/usr/bin/env python3
"""Proxmox VE deployment module for distroget."""

import os
import re
import subprocess
import json
from typing import Dict, List, Optional, Tuple


class ProxmoxTarget:
    """Represents a Proxmox VE target server."""
    
    def __init__(self, hostname: str, username: str = 'root', password: Optional[str] = None):
        """
        Initialize Proxmox target.
        
        Args:
            hostname: PVE hostname or IP
            username: SSH username (default: root)
            password: SSH password (optional, will prompt if not provided)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self._storages = None
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test SSH connection to Proxmox server.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Set password in environment if provided
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no', 
                       '-o', 'ConnectTimeout=5', f'{self.username}@{self.hostname}', 
                       'pvesm', 'status']
            else:
                cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
                       f'{self.username}@{self.hostname}', 'pvesm', 'status']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
            
            if result.returncode == 0:
                return True, "Connection successful"
            else:
                return False, f"Connection failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except FileNotFoundError:
            return False, "sshpass not found (install with: apt install sshpass)"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def discover_storages(self) -> List[Dict[str, str]]:
        """
        Discover available storage on Proxmox server.
        
        Returns:
            List of storage dictionaries with 'name', 'type', 'content', 'enabled' keys
        """
        if self._storages is not None:
            return self._storages
        
        try:
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 'pvesm', 'status']
            else:
                cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 'pvesm', 'status']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
            
            if result.returncode != 0:
                return []
            
            storages = []
            lines = result.stdout.strip().split('\n')
            
            # Skip header line
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    storage = {
                        'name': parts[0],
                        'type': parts[1],
                        'status': parts[2],
                        'total': parts[3] if len(parts) > 3 else '0',
                        'used': parts[4] if len(parts) > 4 else '0',
                        'available': parts[5] if len(parts) > 5 else '0',
                        'enabled': parts[2].lower() in ['active', 'available']
                    }
                    storages.append(storage)
            
            # Get content types for each storage
            for storage in storages:
                storage['content'] = self._get_storage_content(storage['name'])
            
            self._storages = storages
            return storages
        
        except Exception as e:
            print(f"Error discovering storages: {e}")
            return []
    
    def _get_storage_content(self, storage_name: str) -> List[str]:
        """
        Get content types supported by a storage.
        
        Args:
            storage_name: Name of the storage
            
        Returns:
            List of content types (e.g., ['iso', 'vztmpl', 'backup'])
        """
        try:
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'cat /etc/pve/storage.cfg | grep -A 10 "^{storage_name}"']
            else:
                cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'cat /etc/pve/storage.cfg | grep -A 10 "^{storage_name}"']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=5)
            
            if result.returncode == 0:
                # Look for "content" line
                match = re.search(r'content\s+(.+)', result.stdout)
                if match:
                    return [c.strip() for c in match.group(1).split(',')]
            
            # Default content types based on storage type
            return ['iso', 'vztmpl']
        
        except Exception:
            return ['iso', 'vztmpl']
    
    def get_storage_path(self, storage_name: str) -> Optional[str]:
        """
        Get the filesystem path for a storage.
        
        Args:
            storage_name: Name of the storage
            
        Returns:
            Path string or None if not found
        """
        try:
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'pvesm path {storage_name}:vztmpl/dummy 2>/dev/null || pvesm path {storage_name}:iso/dummy 2>/dev/null']
            else:
                cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'pvesm path {storage_name}:vztmpl/dummy 2>/dev/null || pvesm path {storage_name}:iso/dummy 2>/dev/null']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=5)
            
            if result.returncode == 0 and result.stdout:
                # Extract base path from dummy path
                path = result.stdout.strip()
                if '/vztmpl/' in path:
                    return path.split('/vztmpl/')[0]
                elif '/iso/' in path:
                    return path.split('/iso/')[0]
            
            # Fallback: try to get from storage config
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'cat /etc/pve/storage.cfg | grep -A 5 "^{storage_name}"']
            else:
                cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'cat /etc/pve/storage.cfg | grep -A 5 "^{storage_name}"']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=5)
            
            if result.returncode == 0:
                match = re.search(r'path\s+(.+)', result.stdout)
                if match:
                    return match.group(1).strip()
            
            return None
        
        except Exception as e:
            print(f"Error getting storage path: {e}")
            return None
    
    def upload_file(self, local_path: str, storage_name: str, content_type: str = 'iso',
                   progress_callback=None) -> Tuple[bool, str]:
        """
        Upload a file to Proxmox storage.
        
        Args:
            local_path: Local file path
            storage_name: Target storage name
            content_type: Content type ('iso', 'vztmpl', 'snippets')
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not os.path.exists(local_path):
            return False, f"Local file not found: {local_path}"
        
        # Get storage path
        base_path = self.get_storage_path(storage_name)
        if not base_path:
            return False, f"Could not determine path for storage: {storage_name}"
        
        # Determine subdirectory based on content type
        if content_type == 'iso':
            subdir = 'template/iso'
        elif content_type == 'vztmpl':
            subdir = 'template/cache'
        elif content_type == 'snippets':
            subdir = 'snippets'
        else:
            subdir = content_type
        
        remote_dir = f"{base_path}/{subdir}"
        filename = os.path.basename(local_path)
        remote_path = f"{remote_dir}/{filename}"
        
        try:
            # Create directory if it doesn't exist
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                mkdir_cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                            f'{self.username}@{self.hostname}', 
                            f'mkdir -p {remote_dir}']
            else:
                mkdir_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                            f'{self.username}@{self.hostname}', 
                            f'mkdir -p {remote_dir}']
            
            subprocess.run(mkdir_cmd, env=env, timeout=10, check=True)
            
            # Upload file using rsync with progress
            if self.password:
                # Use sshpass with rsync
                env['SSHPASS'] = self.password
                rsync_cmd = [
                    'rsync', '-avz', '--progress',
                    '-e', 'sshpass -e ssh -o StrictHostKeyChecking=no',
                    local_path,
                    f'{self.username}@{self.hostname}:{remote_path}'
                ]
            else:
                rsync_cmd = [
                    'rsync', '-avz', '--progress',
                    '-e', 'ssh -o StrictHostKeyChecking=no',
                    local_path,
                    f'{self.username}@{self.hostname}:{remote_path}'
                ]
            
            if progress_callback:
                # Run with progress monitoring
                process = subprocess.Popen(
                    rsync_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env
                )
                
                for line in process.stdout:
                    # Parse rsync progress
                    match = re.search(r'(\d+)%', line)
                    if match:
                        progress = int(match.group(1))
                        progress_callback(progress, filename)
                
                process.wait()
                if process.returncode != 0:
                    return False, f"Upload failed with code {process.returncode}"
            else:
                result = subprocess.run(rsync_cmd, capture_output=True, text=True, env=env, timeout=3600)
                if result.returncode != 0:
                    return False, f"Upload failed: {result.stderr}"
            
            # Set proper permissions
            if self.password:
                env['SSHPASS'] = self.password
                chmod_cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                            f'{self.username}@{self.hostname}', 
                            f'chmod 644 {remote_path}']
            else:
                chmod_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                            f'{self.username}@{self.hostname}', 
                            f'chmod 644 {remote_path}']
            
            subprocess.run(chmod_cmd, env=env, timeout=5)
            
            return True, f"Uploaded to {storage_name}:{subdir}/{filename}"
        
        except subprocess.TimeoutExpired:
            return False, "Upload timeout"
        except Exception as e:
            return False, f"Upload error: {str(e)}"
    
    def list_files(self, storage_name: str, content_type: str = 'iso') -> List[str]:
        """
        List files in a Proxmox storage.
        
        Args:
            storage_name: Storage name
            content_type: Content type to list
            
        Returns:
            List of filenames
        """
        try:
            env = os.environ.copy()
            if self.password:
                env['SSHPASS'] = self.password
                cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'pvesm list {storage_name} --content {content_type}']
            else:
                cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                       f'{self.username}@{self.hostname}', 
                       f'pvesm list {storage_name} --content {content_type}']
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
            
            if result.returncode == 0:
                files = []
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if parts:
                        # Extract filename from volid (format: storage:content/filename)
                        volid = parts[0]
                        if '/' in volid:
                            filename = volid.split('/')[-1]
                            files.append(filename)
                return files
            
            return []
        
        except Exception as e:
            print(f"Error listing files: {e}")
            return []


def detect_file_type(filename: str) -> str:
    """
    Detect content type based on file extension.
    
    Args:
        filename: File name or path
        
    Returns:
        Content type string ('iso', 'vztmpl', or 'snippets')
    """
    filename_lower = filename.lower()
    
    if filename_lower.endswith(('.iso',)):
        return 'iso'
    elif filename_lower.endswith(('.qcow2', '.img', '.raw')):
        return 'iso'  # Cloud images go to ISO storage in Proxmox
    elif filename_lower.endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
        return 'vztmpl'
    elif filename_lower.endswith(('.yaml', '.yml')):
        return 'snippets'
    else:
        return 'iso'  # Default to ISO


def format_size(bytes_size: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def select_storage_interactive(proxmox: ProxmoxTarget, content_type: str = 'iso') -> Optional[str]:
    """
    Interactively select a storage from available storages.
    
    Args:
        proxmox: ProxmoxTarget instance
        content_type: Desired content type
        
    Returns:
        Selected storage name or None
    """
    storages = proxmox.discover_storages()
    
    if not storages:
        print("No storages found on Proxmox server")
        return None
    
    # Filter storages that support the content type
    compatible = [s for s in storages if s['enabled'] and content_type in s.get('content', [])]
    
    if not compatible:
        print(f"No enabled storages found that support '{content_type}' content")
        print("\nAll storages:")
        for i, storage in enumerate(storages, 1):
            status = "✓" if storage['enabled'] else "✗"
            content = ', '.join(storage.get('content', ['unknown']))
            print(f"  {i}. {status} {storage['name']} ({storage['type']}) - {content}")
        return None
    
    print(f"\nAvailable storages for {content_type}:")
    print("-" * 80)
    for i, storage in enumerate(compatible, 1):
        total = storage.get('total', '0')
        used = storage.get('used', '0')
        available = storage.get('available', '0')
        content = ', '.join(storage.get('content', []))
        print(f"{i}. {storage['name']}")
        print(f"   Type: {storage['type']}")
        print(f"   Content: {content}")
        print(f"   Space: {available} available")
        print()
    
    while True:
        try:
            choice = input(f"Select storage (1-{len(compatible)}) or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(compatible):
                return compatible[idx]['name']
            else:
                print(f"Please enter a number between 1 and {len(compatible)}")
        except ValueError:
            print("Invalid input")
        except KeyboardInterrupt:
            print("\nCancelled")
            return None


if __name__ == '__main__':
    # Example usage
    import sys
    import getpass
    
    if len(sys.argv) < 2:
        print("Usage: python3 proxmox.py <hostname> [username]")
        print("Example: python3 proxmox.py pve.local root")
        sys.exit(1)
    
    hostname = sys.argv[1]
    username = sys.argv[2] if len(sys.argv) > 2 else 'root'
    
    # Get password
    password = getpass.getpass(f"Password for {username}@{hostname}: ")
    
    # Create Proxmox target
    pve = ProxmoxTarget(hostname, username, password)
    
    # Test connection
    print("Testing connection...")
    success, message = pve.test_connection()
    print(f"  {message}")
    
    if not success:
        sys.exit(1)
    
    # Discover storages
    print("\nDiscovering storages...")
    storages = pve.discover_storages()
    
    print(f"\nFound {len(storages)} storage(s):")
    for storage in storages:
        status = "✓" if storage['enabled'] else "✗"
        content = ', '.join(storage.get('content', []))
        print(f"  {status} {storage['name']} ({storage['type']}) - {content}")
