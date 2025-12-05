#!/usr/bin/env python3
"""Automatic update and deployment for cron jobs."""

import sys
import os
import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from config_manager import ConfigManager
from updaters import DISTRO_UPDATERS
from downloads import DownloadManager
from proxmox import ProxmoxTarget, detect_file_type


def check_auto_deploy_items(distro_dict: Dict) -> List[Tuple[str, str, str]]:
    """
    Check auto-deploy items for newer versions and return items to download/deploy.
    
    Args:
        download_dir: Download directory path
        distro_dict: Full distro dictionary with all ISOs
        
    Returns:
        List of (item_path, url) tuples to download and deploy
    """
    config = ConfigManager()
    auto_deploy_items = config.get_auto_deploy_items()
    
    if not auto_deploy_items:
        return []
    
    items_to_deploy = []
    
    print("\n" + "=" * 80)
    print(f"Checking {len(auto_deploy_items)} auto-deploy item(s) for updates...")
    print("=" * 80)
    
    for item_path in auto_deploy_items:
        print(f"\nChecking: {item_path}")
        path_parts = item_path.split('/')
        
        # Navigate to the item in distro_dict
        current_node = distro_dict
        for part in path_parts:
            if isinstance(current_node, dict) and part in current_node:
                current_node = current_node[part]
            else:
                print(f"  ✗ Item not found in current distro list")
                break
        
        # Extract URLs if this is a leaf node
        if isinstance(current_node, list):
            for entry in current_node:
                if ": " in entry:
                    name, url = entry.split(": ", 1)
                    items_to_deploy.append((item_path, url, name))
                    print(f"  ✓ Found: {name}")
        else:
            print(f"  ✗ Not a downloadable item")
    
    return items_to_deploy


def auto_update_distributions(download_dir: Path, deploy_to_proxmox: bool = True) -> Dict:
    """
    Automatically update configured distributions.
    
    Args:
        download_dir: Directory to download files to
        deploy_to_proxmox: Whether to automatically deploy to Proxmox
        
    Returns:
        Dict with update results
    """
    config = ConfigManager()
    
    distros_to_update = config.get_auto_update_distros()
    
    if not distros_to_update:
        print("=" * 80)
        print("No distributions configured for auto-update")
        print("=" * 80)
        print("\nTo configure auto-update:")
        print("  python3 distroget.py --configure")
        print("\nThen select option 2 to choose distributions for auto-update.")
        return {'status': 'no_distros', 'updates': []}
    
    # Auto-enable if distributions are configured but flag is disabled
    if not config.is_auto_update_enabled():
        print("Note: Auto-enabling auto-update (distributions are configured)")
        config.set_auto_update_enabled(True)
    
    print("=" * 80)
    print(f"Automatic Update - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"\nUpdating {len(distros_to_update)} distribution(s):")
    for distro in distros_to_update:
        print(f"  • {distro}")
    print()
    
    results = {
        'status': 'success',
        'timestamp': datetime.datetime.now().isoformat(),
        'updates': [],
        'downloads': [],
        'deployments': []
    }
    
    # Ensure download directory exists
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Update each distribution
    for distro_name in distros_to_update:
        print(f"\n{'=' * 80}")
        print(f"Processing: {distro_name}")
        print('=' * 80)
        
        if distro_name not in DISTRO_UPDATERS:
            print(f"✗ Unknown distribution: {distro_name}")
            results['updates'].append({
                'distro': distro_name,
                'status': 'unknown',
                'error': 'Distribution not found'
            })
            continue
        
        updater_class = DISTRO_UPDATERS[distro_name]
        
        try:
            # Get latest version
            print("Checking for latest version...")
            version = updater_class.get_latest_version()
            
            if not version:
                print("✗ Could not determine latest version")
                results['updates'].append({
                    'distro': distro_name,
                    'status': 'failed',
                    'error': 'Version check failed'
                })
                continue
            
            if isinstance(version, list):
                print(f"✓ Found versions: {', '.join(version)}")
            elif isinstance(version, dict):
                print(f"✓ Found version info: {version}")
            else:
                print(f"✓ Found version: {version}")
            
            # Generate download links
            print("Generating download links...")
            links = updater_class.generate_download_links(version)
            
            if not links:
                print("✗ Could not generate download links")
                results['updates'].append({
                    'distro': distro_name,
                    'status': 'failed',
                    'error': 'No download links'
                })
                continue
            
            # Extract URLs from various link structures
            urls_to_download = []
            
            if isinstance(links, dict):
                # Hierarchical structure (like Fedora)
                for key, value in links.items():
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, list):
                                for url in subvalue:
                                    if isinstance(url, str) and url.startswith('http'):
                                        urls_to_download.append(url)
                    elif isinstance(value, list):
                        for url in value:
                            if isinstance(url, str) and url.startswith('http'):
                                urls_to_download.append(url)
            elif isinstance(links, list):
                # Simple list structure
                for link in links:
                    if isinstance(link, str):
                        # Extract URL from markdown format
                        import re
                        match = re.search(r'\(([^)]+)\)', link)
                        if match:
                            urls_to_download.append(match.group(1))
                        elif link.startswith('http'):
                            urls_to_download.append(link)
            
            if not urls_to_download:
                print("✗ No valid download URLs found")
                results['updates'].append({
                    'distro': distro_name,
                    'status': 'failed',
                    'error': 'No valid URLs'
                })
                continue
            
            # Limit to first 3 files for cloud images (to avoid downloading all spins/flavors)
            if 'Cloud' in distro_name:
                urls_to_download = urls_to_download[:2]
            
            print(f"✓ Found {len(urls_to_download)} download(s)")
            
            # Download files
            downloaded_files = []
            
            for i, url in enumerate(urls_to_download, 1):
                filename = url.split('/')[-1]
                filepath = download_dir / filename
                
                # Skip if already downloaded
                if filepath.exists():
                    file_age_hours = (datetime.datetime.now().timestamp() - filepath.stat().st_mtime) / 3600
                    if file_age_hours < 24:  # Skip if less than 24 hours old
                        print(f"  [{i}/{len(urls_to_download)}] Skipping {filename} (already downloaded recently)")
                        downloaded_files.append(str(filepath))
                        continue
                
                print(f"  [{i}/{len(urls_to_download)}] Downloading {filename}...")
                
                # Use download manager
                manager = DownloadManager(str(download_dir))
                success = manager._download_file(url, str(filepath))
                
                if success:
                    print(f"    ✓ Downloaded ({format_size(filepath.stat().st_size)})")
                    downloaded_files.append(str(filepath))
                    
                    # Check for decompression
                    if filepath.suffix.lower() in ['.bz2', '.gz', '.zip']:
                        print(f"    Decompressing...")
                        decompressed = manager._decompress_if_needed(str(filepath))
                        if decompressed and decompressed != str(filepath):
                            print(f"    ✓ Decompressed to {Path(decompressed).name}")
                            downloaded_files[-1] = decompressed
                else:
                    print(f"    ✗ Download failed")
            
            results['updates'].append({
                'distro': distro_name,
                'status': 'success',
                'version': str(version),
                'files': len(downloaded_files)
            })
            
            results['downloads'].extend(downloaded_files)
            
            # Deploy to Proxmox if configured
            if deploy_to_proxmox and downloaded_files:
                print("\nDeploying to Proxmox...")
                deployed = deploy_files_to_proxmox(downloaded_files)
                results['deployments'].extend(deployed)
        
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            results['updates'].append({
                'distro': distro_name,
                'status': 'error',
                'error': str(e)
            })
    
    # Print summary
    print("\n" + "=" * 80)
    print("Update Summary")
    print("=" * 80)
    
    successful = sum(1 for u in results['updates'] if u['status'] == 'success')
    failed = sum(1 for u in results['updates'] if u['status'] in ['failed', 'error'])
    
    print(f"\nDistributions: {successful} successful, {failed} failed")
    print(f"Downloaded: {len(results['downloads'])} file(s)")
    print(f"Deployed: {len(results['deployments'])} file(s)")
    
    return results


def deploy_files_to_proxmox(files: List[str], interactive: bool = False) -> List[Dict]:
    """
    Deploy files to Proxmox using configured settings.
    
    Args:
        files: List of file paths to deploy
        interactive: Allow password prompts (False for cron/auto mode)
        
    Returns:
        List of deployment results
    """
    config = ConfigManager()
    pve_config = config.get_proxmox_config()
    
    hostname = pve_config.get('hostname')
    username = pve_config.get('username', 'root')
    
    if not hostname:
        print("✗ Proxmox not configured. Run: python3 distroget.py --configure")
        return []
    
    print(f"  Connecting to {hostname}...")
    
    # Initialize ProxmoxTarget without password
    pve = ProxmoxTarget(hostname, username)
    
    # Check SSH keys first
    if not pve.check_ssh_keys():
        if not interactive:
            print(f"✗ SSH keys not configured for {username}@{hostname}")
            print(f"  For automated deployment, set up SSH keys:")
            print(f"    ssh-copy-id {username}@{hostname}")
            print(f"  Or run interactively once to test password authentication.")
            return []
        else:
            # Interactive mode - prompt for password
            password = pve.prompt_password()
            if not password:
                print("✗ Password required but not provided")
                return []
            pve.password = password
    
    # Test connection
    success, message = pve.test_connection(interactive=interactive)
    if not success:
        print(f"✗ {message}")
        return []
    
    print(f"  ✓ Connected")
    
    # Deploy files
    deployments = []
    for filepath in files:
        file_type = detect_file_type(Path(filepath))
        storage = config.get_storage_for_type(file_type)
        
        if not storage:
            print(f"  ⚠ No storage configured for {file_type}, skipping {Path(filepath).name}")
            continue
        
        print(f"  Uploading {Path(filepath).name} to {storage}...")
        
        try:
            if pve.upload_file(Path(filepath), storage):
                print(f"    ✓ Deployed successfully")
                deployments.append({
                    'file': filepath,
                    'storage': storage,
                    'type': file_type,
                    'status': 'deployed'
                })
            else:
                print(f"    ✗ Upload failed")
        except Exception as e:
            print(f"    ✗ Error: {e}")
    
    return deployments


def format_size(bytes_size: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def main():
    """Main entry point for auto-update."""
    import argparse
    
    # Get default download dir from config
    config = ConfigManager()
    default_download_dir = config.get_auto_update_download_dir()
    
    parser = argparse.ArgumentParser(description='Automatic distribution updates')
    parser.add_argument('--download-dir', type=Path, 
                       default=Path(default_download_dir),
                       help=f'Download directory (default: {default_download_dir})')
    parser.add_argument('--no-deploy', action='store_true',
                       help='Skip Proxmox deployment')
    parser.add_argument('--deploy-to-proxmox', action='store_true',
                       help='Deploy to Proxmox (default when configured)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be updated without doing it')
    
    args = parser.parse_args()
    
    # Determine deployment: --deploy-to-proxmox OR (not --no-deploy)
    deploy = args.deploy_to_proxmox or (not args.no_deploy)
    
    if args.dry_run:
        config = ConfigManager()
        distros = config.get_auto_update_distros()
        enabled = config.is_auto_update_enabled()
        auto_deploy_items = config.get_auto_deploy_items()
        
        print("Dry Run - Auto-Update Configuration")
        print("=" * 80)
        print(f"Enabled: {enabled}")
        print(f"Distributions to update: {len(distros)}")
        for distro in distros:
            print(f"  • {distro}")
        print()
        print(f"Auto-deploy items: {len(auto_deploy_items)}")
        for item in auto_deploy_items:
            print(f"  • {item}")
        print()
        print(f"Download directory: {args.download_dir}")
        print(f"Deploy to Proxmox: {deploy}")
        return
    
    # Run auto-update
    results = auto_update_distributions(
        args.download_dir,
        deploy_to_proxmox=deploy
    )
    
    # Exit with appropriate code
    if results['status'] == 'success':
        failed = sum(1 for u in results['updates'] if u['status'] in ['failed', 'error'])
        sys.exit(0 if failed == 0 else 1)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
