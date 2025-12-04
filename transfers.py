#!/usr/bin/env python3
"""
Transfer manager module for distroget.
Handles remote file transfers via SCP/SSH with progress tracking.
"""

import os
import subprocess
import shutil
import tempfile
import threading


class TransferManager:
    """Manages transfers to remote hosts via SCP."""
    
    def __init__(self, remote_host, remote_path, ssh_password=None):
        """
        Initialize the transfer manager.
        
        Args:
            remote_host: SSH hostname or user@hostname
            remote_path: Remote directory path to upload files to
            ssh_password: Optional SSH password (requires sshpass)
        """
        self.remote_host = remote_host
        self.remote_path = remote_path
        self.ssh_password = ssh_password
        self.temp_dir = tempfile.mkdtemp(prefix='distroget_')
        self.transfer_status = "pending"  # pending, transferring, completed, failed
        self.transfer_progress = {}  # Track individual file transfers
        self.files_to_transfer = []
        self.lock = threading.Lock()
    
    def get_temp_dir(self):
        """Get the temporary directory for staging downloads."""
        return self.temp_dir
    
    def add_file(self, filepath):
        """Add a file to the transfer queue."""
        with self.lock:
            if filepath not in self.files_to_transfer:
                self.files_to_transfer.append(filepath)
    
    def get_status(self):
        """Get current transfer status for progress display."""
        with self.lock:
            return {
                'transfer_status': self.transfer_status,
                'transfer_progress': dict(self.transfer_progress),
                'files_to_transfer': list(self.files_to_transfer)
            }
    
    def bulk_transfer(self):
        """Transfer all files to remote host in one SCP operation."""
        if not self.files_to_transfer:
            return True
        
        # Update status
        with self.lock:
            self.transfer_status = "transferring"
        
        print(f"\n\n{'='*60}")
        print(f"Transferring {len(self.files_to_transfer)} file(s) to {self.remote_host}:{self.remote_path}")
        print(f"{'='*60}")
        
        # Show list of files being transferred
        for filepath in self.files_to_transfer:
            filename = os.path.basename(filepath)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"  • {filename} ({size_mb:.1f} MB)")
        
        print(f"\nTransferring files...\n")
        
        # Build scp command with all files
        # Using -p to preserve timestamps, -C for compression, -v for verbose
        if self.ssh_password:
            scp_cmd = ['sshpass', '-p', self.ssh_password, 'scp', '-p', '-C', '-v'] + \
                      self.files_to_transfer + [f"{self.remote_host}:{self.remote_path}/"]
        else:
            scp_cmd = ['scp', '-p', '-C', '-v'] + self.files_to_transfer + \
                      [f"{self.remote_host}:{self.remote_path}/"]
        
        try:
            # Run with interactive TTY (or non-interactive with sshpass)
            result = subprocess.run(scp_cmd, check=False)
            
            if result.returncode == 0:
                with self.lock:
                    self.transfer_status = "completed"
                print(f"\n{'='*60}")
                print(f"✓ Successfully transferred all files to {self.remote_host}")
                print(f"{'='*60}\n")
                # Clean up temp files
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                return True
            else:
                with self.lock:
                    self.transfer_status = "failed"
                print(f"\n{'='*60}")
                print(f"✗ Transfer failed with exit code {result.returncode}")
                print(f"{'='*60}")
                print(f"\nFiles are still available locally in: {self.temp_dir}")
                if self.ssh_password:
                    print("You can manually transfer them with:")
                    print(f"  sshpass -p 'YOUR_PASSWORD' scp {self.temp_dir}/* {self.remote_host}:{self.remote_path}/")
                else:
                    print("You can manually transfer them with:")
                    print(f"  scp {self.temp_dir}/* {self.remote_host}:{self.remote_path}/")
                return False
        except Exception as e:
            with self.lock:
                self.transfer_status = "failed"
            print(f"\n✗ Transfer error: {e}")
            print(f"Files are still available locally in: {self.temp_dir}")
            return False
    
    def test_connection(self):
        """Test SSH connection to remote host."""
        # Test SSH connection (non-interactive, quick test)
        test_result = subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 
             self.remote_host, 'echo "SSH OK"'], 
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        return test_result.returncode == 0
    
    def test_connection_with_password(self):
        """Test SSH connection with password (requires sshpass)."""
        if not self.ssh_password:
            return False
        
        if not shutil.which('sshpass'):
            return False
        
        test_with_pw = subprocess.run(
            ['sshpass', '-p', self.ssh_password, 'ssh', '-o', 'ConnectTimeout=5',
             self.remote_host, 'echo "SSH OK"'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return test_with_pw.returncode == 0
    
    def create_remote_directory(self):
        """Create the remote directory if it doesn't exist."""
        if self.ssh_password:
            mkdir_result = subprocess.run(
                ['sshpass', '-p', self.ssh_password, 'ssh', self.remote_host, 
                 f'mkdir -p {self.remote_path}'],
                capture_output=True,
                text=True
            )
        else:
            mkdir_result = subprocess.run(
                ['ssh', self.remote_host, f'mkdir -p {self.remote_path}'],
                capture_output=True,
                text=True
            )
        
        return mkdir_result.returncode == 0
    
    def cleanup(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)


class CombinedDownloadTransferManager:
    """Combined manager that handles downloads and remote transfers."""
    
    def __init__(self, remote_host, remote_path, ssh_password=None, max_workers=3):
        """
        Initialize combined download and transfer manager.
        
        Args:
            remote_host: SSH hostname or user@hostname
            remote_path: Remote directory path to upload files to
            ssh_password: Optional SSH password (requires sshpass)
            max_workers: Maximum number of parallel download threads
        """
        from downloads import DownloadManager
        
        self.transfer_manager = TransferManager(remote_host, remote_path, ssh_password)
        self.download_manager = DownloadManager(
            self.transfer_manager.get_temp_dir(),
            max_workers=max_workers
        )
        self.is_remote = True
        
    def start(self):
        """Start download workers."""
        self.download_manager.start()
    
    def add_download(self, url):
        """Add a URL to the download queue."""
        self.download_manager.add_download(url)
    
    def get_status(self):
        """Get combined status for downloads and transfers."""
        download_status = self.download_manager.get_status()
        transfer_status = self.transfer_manager.get_status()
        
        # Update transfer manager with downloaded files
        for filepath in download_status['downloaded_files']:
            self.transfer_manager.add_file(filepath)
        
        return {
            **download_status,
            'is_remote': self.is_remote,
            'transfer_status': transfer_status['transfer_status'],
            'transfer_progress': transfer_status['transfer_progress'],
            'downloaded_files': download_status['downloaded_files']
        }
    
    def stop(self):
        """Stop download workers."""
        self.download_manager.stop()
    
    def wait_and_transfer(self):
        """Wait for downloads to complete and transfer files."""
        # Wait for all downloads to complete
        self.download_manager.wait_for_completion()
        self.download_manager.stop()
        
        # Transfer files to remote host
        return self.transfer_manager.bulk_transfer()
    
    @property
    def download_queue(self):
        """Access to download queue for compatibility."""
        return self.download_manager.download_queue
