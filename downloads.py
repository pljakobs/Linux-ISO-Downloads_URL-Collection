#!/usr/bin/env python3
"""
Download manager module for distroget.
Handles parallel downloads with progress tracking.
"""

import os
import queue
import threading
import time
import requests


class DownloadManager:
    """Manages parallel downloads in background threads."""
    
    def __init__(self, target_dir, max_workers=3):
        """
        Initialize the download manager.
        
        Args:
            target_dir: Local directory to save downloaded files
            max_workers: Maximum number of parallel download threads
        """
        self.target_dir = target_dir
        self.max_workers = max_workers
        self.download_queue = queue.Queue()
        self.active_downloads = {}
        self.completed = set()
        self.completed_urls = set()
        self.failed = set()
        self.retry_counts = {}  # Track retry attempts per URL
        self.max_retries = 3
        self.lock = threading.Lock()
        self.workers = []
        self.running = True
        self.downloaded_files = []  # Track successfully downloaded files
        
    def start(self):
        """Start download worker threads."""
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)
    
    def _worker(self):
        """Worker thread that processes downloads."""
        while self.running:
            try:
                url = self.download_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            filename = url.split('/')[-1]
            with self.lock:
                self.active_downloads[url] = {
                    'filename': filename,
                    'progress': 0,
                    'total': 0
                }
            
            try:
                self._download_file(url, filename)
                with self.lock:
                    self.completed.add(url)
                    self.completed_urls.add(url)
                    if url in self.active_downloads:
                        del self.active_downloads[url]
                    # Clear retry count on success
                    if url in self.retry_counts:
                        del self.retry_counts[url]
            except Exception as e:
                with self.lock:
                    # Get current retry count
                    retry_count = self.retry_counts.get(url, 0)
                    
                    if retry_count < self.max_retries:
                        # Retry the download
                        self.retry_counts[url] = retry_count + 1
                        # Re-queue with delay (exponential backoff)
                        time.sleep(2 ** retry_count)  # 1s, 2s, 4s delays
                        self.download_queue.put(url)
                    else:
                        # Max retries exceeded
                        self.failed.add(url)
                    
                    if url in self.active_downloads:
                        del self.active_downloads[url]
            finally:
                self.download_queue.task_done()
    
    def _download_file(self, url, filename):
        """Download a single file with progress tracking."""
        local_path = os.path.join(self.target_dir, filename)
        
        # Skip existing files
        if os.path.exists(local_path):
            with self.lock:
                self.completed.add(url)
                self.completed_urls.add(url)
                self.downloaded_files.append(local_path)
            return
        
        # Download the file
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))
        
        with open(local_path, 'wb') as f:
            downloaded = 0
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    with self.lock:
                        if url in self.active_downloads:
                            self.active_downloads[url]['progress'] = downloaded
                            self.active_downloads[url]['total'] = total
        
        # Track downloaded file
        with self.lock:
            self.downloaded_files.append(local_path)
    
    def add_download(self, url):
        """Add a URL to the download queue."""
        self.download_queue.put(url)
    
    def get_status(self):
        """Get current download status for progress display."""
        with self.lock:
            return {
                'active': dict(self.active_downloads),
                'completed': len(self.completed),
                'completed_urls': set(self.completed_urls),
                'failed': len(self.failed),
                'retry_counts': dict(self.retry_counts),
                'queued': self.download_queue.qsize(),
                'downloaded_files': list(self.downloaded_files)
            }
    
    def stop(self):
        """Stop all workers."""
        self.running = False
        for worker in self.workers:
            worker.join(timeout=1)
    
    def wait_for_completion(self):
        """Wait for all downloads to complete."""
        self.download_queue.join()
