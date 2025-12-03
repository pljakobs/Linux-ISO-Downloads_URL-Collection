#!/usr/bin/env python3
import curses
import json
import os
import requests
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

# URL of the GitHub raw text file
ISO_LIST_URL = "https://raw.githubusercontent.com/pljakobs/Linux-ISO-Downloads_URL-Collection/main/README.md"
REPO_HTTPS_URL = "https://github.com/pljakobs/Linux-ISO-Downloads_URL-Collection.git"
REPO_SSH_URL = "git@github.com:pljakobs/Linux-ISO-Downloads_URL-Collection.git"
REPO_FILE_PATH = "README.md"

# Global variable to store selections
selected_urls = []

# Config file location
CONFIG_FILE = Path.home() / ".config" / "distroget" / "config.json"

def load_config():
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config):
    """Save configuration to file."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save config: {e}")

def get_repo_url():
    """Get the repository URL based on user preference."""
    config = load_config()
    
    # Check if preference is already set
    if 'repo_url_type' in config:
        return REPO_SSH_URL if config['repo_url_type'] == 'ssh' else REPO_HTTPS_URL
    
    # Ask user for preference
    print("\nChoose repository access method:")
    print("1. HTTPS (username/password or token)")
    print("2. SSH (requires SSH key setup)")
    
    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice == '1':
            config['repo_url_type'] = 'https'
            save_config(config)
            return REPO_HTTPS_URL
        elif choice == '2':
            config['repo_url_type'] = 'ssh'
            save_config(config)
            return REPO_SSH_URL
        else:
            print("Invalid choice. Please enter 1 or 2.")

def fetch_distrowatch_versions():
    """Fetch latest versions from DistroWatch RSS."""
    try:
        import xml.etree.ElementTree as ET
        r = requests.get('https://distrowatch.com/news/dwd.xml', timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        
        versions = {}
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ''
            if title:
                # Parse "Distro Version" format
                parts = title.rsplit(' ', 1)
                if len(parts) == 2:
                    distro_name = parts[0]
                    version = parts[1]
                    versions[distro_name] = version
        return versions
    except Exception as e:
        print(f"Warning: Could not fetch DistroWatch versions: {e}")
        return {}

# Distro-specific updaters
class DistroUpdater:
    """Base class for distro-specific updaters."""
    
    @staticmethod
    def get_latest_version():
        """Get the latest version number."""
        raise NotImplementedError
    
    @staticmethod
    def generate_download_links(version):
        """Generate download links for a specific version."""
        raise NotImplementedError
    
    @staticmethod
    def update_section(content, version, links):
        """Update the distro's section in the markdown content."""
        raise NotImplementedError

class FedoraUpdater(DistroUpdater):
    """Updater for Fedora Workstation and Spins with multiple versions."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Fedora versions (latest stable + previous)."""
        try:
            import re
            # List the releases directory (following redirects)
            r = requests.get('https://download.fedoraproject.org/pub/fedora/linux/releases/', 
                           timeout=10, allow_redirects=True)
            r.raise_for_status()
            
            # Find all version numbers
            versions = re.findall(r'href="(\d+)/"', r.text)
            if versions:
                # Return the two highest version numbers
                sorted_versions = sorted([int(v) for v in versions], reverse=True)
                return [str(v) for v in sorted_versions[:2]]
        except Exception as e:
            print(f"    Error fetching Fedora versions: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(versions):
        """Generate hierarchical Fedora structure with multiple versions."""
        import re
        
        if not versions or not isinstance(versions, list):
            return []
        
        # Structure: {version: {'Workstation': [urls], 'Spins': [urls]}}
        structure = {}
        
        for version_num in versions:
            structure[version_num] = {'Workstation': [], 'Spins': []}
            
            # Get Workstation edition
            try:
                workstation_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Workstation/x86_64/iso"
                r = requests.get(workstation_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find Workstation ISO
                iso_pattern = re.compile(r'href="(Fedora-Workstation-Live[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                if matches:
                    structure[version_num]['Workstation'].append(f"{workstation_url}/{matches[0]}")
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Workstation: {e}")
            
            # Get all Spins
            try:
                spins_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Spins/x86_64/iso"
                r = requests.get(spins_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find all spin ISOs (deduplicate)
                iso_pattern = re.compile(r'href="(Fedora-[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                unique_isos = sorted(set(matches))
                
                for iso in unique_isos:
                    structure[version_num]['Spins'].append(f"{spins_url}/{iso}")
                    
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Spins: {e}")
        
        return structure
    
    @staticmethod
    def update_section(content, versions, structure):
        """Update Fedora section with hierarchical markdown."""
        import re
        
        # Find any existing Fedora section (Fedora or Fedora Workstation)
        pattern = r'## Fedora(?:\s+Workstation)?\s*\n(.*?)(?=\n##|\Z)'
        
        if structure:
            new_section = "## Fedora\n\n"
            
            for version in versions:
                if version not in structure:
                    continue
                
                version_data = structure[version]
                
                # Add Workstation subsection
                if version_data.get('Workstation'):
                    new_section += f"### Fedora {version} Workstation\n"
                    for url in version_data['Workstation']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
                
                # Add Spins subsection
                if version_data.get('Spins'):
                    new_section += f"### Fedora {version} Spins\n"
                    for url in version_data['Spins']:
                        filename = url.split('/')[-1]
                        # Extract spin name from filename
                        match = re.search(r'Fedora-([^-]+)-', filename)
                        spin_name = match.group(1) if match else filename
                        new_section += f"- [{spin_name}]({url})\n"
                    new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                # Add new section
                content = f"{content}\n{new_section}"
        
        return content

class DebianUpdater(DistroUpdater):
    """Updater for Debian with multiple desktop environments."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Debian stable version."""
        try:
            import re
            # The current-live directory contains the latest stable release
            r = requests.get('https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/', timeout=10)
            r.raise_for_status()
            
            # Extract version from filename like "debian-live-12.6.0-amd64-..."
            match = re.search(r'debian-live-(\d+\.\d+(?:\.\d+)?)-amd64', r.text)
            if match:
                full_version = match.group(1)
                # Return major version
                return full_version.split('.')[0]
        except Exception as e:
            print(f"    Error fetching Debian version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate hierarchical Debian structure with all desktop environments."""
        import re
        
        structure = {}
        base_url = "https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid"
        
        try:
            r = requests.get(base_url + "/", timeout=10)
            r.raise_for_status()
            
            # Find all live ISO files
            iso_pattern = re.compile(r'href="(debian-live-[^"]+\.iso)"')
            matches = set(iso_pattern.findall(r.text))
            
            # Categorize by desktop environment
            for iso in sorted(matches):
                iso_lower = iso.lower()
                de_name = None
                
                if 'cinnamon' in iso_lower:
                    de_name = 'Cinnamon'
                elif 'gnome' in iso_lower:
                    de_name = 'GNOME'
                elif 'kde' in iso_lower:
                    de_name = 'KDE Plasma'
                elif 'xfce' in iso_lower:
                    de_name = 'Xfce'
                elif 'lxde' in iso_lower:
                    de_name = 'LXDE'
                elif 'lxqt' in iso_lower:
                    de_name = 'LXQt'
                elif 'mate' in iso_lower:
                    de_name = 'MATE'
                
                if de_name:
                    if de_name not in structure:
                        structure[de_name] = []
                    structure[de_name].append(f"{base_url}/{iso}")
        
        except Exception as e:
            print(f"    Error fetching Debian ISOs: {e}")
        
        return structure
    
    @staticmethod
    def update_section(content, version, structure):
        """Update Debian section with hierarchical desktop environments."""
        import re
        
        pattern = r'## Debian\s*\n(.*?)(?=\n##|\Z)'
        
        if structure:
            new_section = f"## Debian\n\n"
            
            # Add each desktop environment as a subsection
            for de_name in sorted(structure.keys()):
                new_section += f"### Debian {version} {de_name}\n"
                for url in structure[de_name]:
                    filename = url.split('/')[-1]
                    new_section += f"- [{filename}]({url})\n"
                new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                content = f"{content}\n{new_section}"
        
        return content

class UbuntuUpdater(DistroUpdater):
    """Updater for Ubuntu with multiple flavors."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Ubuntu LTS version."""
        try:
            import re
            r = requests.get('https://releases.ubuntu.com/', timeout=10)
            r.raise_for_status()
            
            # Find all version directories
            versions = re.findall(r'href="(\d+\.\d+)/"', r.text)
            if versions:
                # Filter for LTS versions (.04)
                lts_versions = [v for v in versions if v.endswith('.04')]
                if lts_versions:
                    lts_versions.sort(key=lambda x: tuple(map(int, x.split('.'))))
                    return lts_versions[-1]
        except Exception as e:
            print(f"    Error fetching Ubuntu version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate hierarchical Ubuntu structure with all flavors."""
        if not version:
            return {}
        
        import re
        structure = {}
        
        # Define Ubuntu flavors and their base URLs
        flavors = {
            'Ubuntu': f'https://releases.ubuntu.com/{version}/',
            'Kubuntu': f'https://cdimage.ubuntu.com/kubuntu/releases/{version}/release/',
            'Xubuntu': f'https://cdimage.ubuntu.com/xubuntu/releases/{version}/release/',
            'Lubuntu': f'https://cdimage.ubuntu.com/lubuntu/releases/{version}/release/',
            'Ubuntu MATE': f'https://cdimage.ubuntu.com/ubuntu-mate/releases/{version}/release/',
            'Ubuntu Budgie': f'https://cdimage.ubuntu.com/ubuntu-budgie/releases/{version}/release/',
        }
        
        for flavor, url in flavors.items():
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    # Find desktop ISO
                    iso_pattern = re.compile(r'href="([^"]*desktop-amd64\.iso)"')
                    matches = iso_pattern.findall(r.text)
                    if matches:
                        structure[flavor] = [f"{url}{matches[0]}"]
            except Exception:
                pass
        
        return structure
    
    @staticmethod
    def update_section(content, version, structure):
        """Update Ubuntu section with hierarchical flavors."""
        import re
        
        pattern = r'## Ubuntu\s*\n(.*?)(?=\n##|\Z)'
        
        if structure:
            new_section = "## Ubuntu\n\n"
            
            for flavor in sorted(structure.keys()):
                new_section += f"### {flavor} {version}\n"
                for url in structure[flavor]:
                    filename = url.split('/')[-1]
                    new_section += f"- [{filename}]({url})\n"
                new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                content = f"{content}\n{new_section}"
        
        return content

# Registry of updaters
class OpenSUSEUpdater(DistroUpdater):
    """Updater for openSUSE."""
    
    @staticmethod
    def get_latest_version():
        """Get latest openSUSE versions."""
        try:
            import re
            # Try to detect Leap version from download directory
            r = requests.get('https://download.opensuse.org/distribution/leap/', timeout=10, allow_redirects=True)
            r.raise_for_status()
            
            # Find version directories
            versions = re.findall(r'href="(\d+\.\d+)/"', r.text)
            if versions:
                # Get the highest version
                latest_leap = max(versions, key=lambda x: tuple(map(int, x.split('.'))))
                return {'Leap': latest_leap, 'Tumbleweed': 'latest'}
        except Exception as e:
            print(f"    Error fetching openSUSE version: {e}")
        
        # Fallback to known latest version
        return {'Leap': '16.0', 'Tumbleweed': 'latest'}
    
    @staticmethod
    def generate_download_links(versions):
        """Generate openSUSE download links."""
        if not versions or not isinstance(versions, dict):
            return {}
        
        structure = {}
        
        # Leap
        if 'Leap' in versions:
            leap_version = versions['Leap']
            structure['Leap'] = [
                f"https://download.opensuse.org/distribution/leap/{leap_version}/iso/openSUSE-Leap-{leap_version}-DVD-x86_64-Media.iso"
            ]
        
        # Tumbleweed
        if 'Tumbleweed' in versions:
            structure['Tumbleweed'] = [
                "https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-DVD-x86_64-Current.iso"
            ]
        
        return structure
    
    @staticmethod
    def update_section(content, versions, structure):
        """Update openSUSE section."""
        import re
        
        pattern = r'## openSUSE\s*\n(.*?)(?=\n##|\Z)'
        
        if structure:
            new_section = "## openSUSE\n\n"
            
            if 'Leap' in structure and 'Leap' in versions:
                new_section += f"### openSUSE Leap {versions['Leap']}\n"
                for url in structure['Leap']:
                    filename = url.split('/')[-1]
                    new_section += f"- [{filename}]({url})\n"
                new_section += "\n"
            
            if 'Tumbleweed' in structure:
                new_section += "### openSUSE Tumbleweed\n"
                for url in structure['Tumbleweed']:
                    filename = url.split('/')[-1]
                    new_section += f"- [{filename}]({url})\n"
                new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                content = f"{content}\n{new_section}"
        
        return content

# Registry of updaters
DISTRO_UPDATERS = {
    'Fedora': FedoraUpdater,
    'Debian': DebianUpdater,
    'Ubuntu': UbuntuUpdater,
    'openSUSE': OpenSUSEUpdater,
}

def update_iso_list_file(local_repo_path):
    """Update the ISO list file with latest versions from various sources."""
    file_path = Path(local_repo_path) / REPO_FILE_PATH
    if not file_path.exists():
        print(f"File {file_path} not found.")
        return False
    
    # Read current content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    # Update each distro
    for distro_name, updater_class in DISTRO_UPDATERS.items():
        try:
            print(f"Updating {distro_name}...")
            version = updater_class.get_latest_version()
            
            if version:
                # Handle both single version and list of versions
                if isinstance(version, list):
                    print(f"  Found versions: {', '.join(version)}")
                else:
                    print(f"  Found version: {version}")
                
                links = updater_class.generate_download_links(version)
                
                if links:
                    # Count links differently for hierarchical structures
                    if isinstance(links, dict):
                        total_links = sum(len(v) if isinstance(v, list) else sum(len(sv) for sv in v.values() if isinstance(sv, list)) 
                                        for v in links.values())
                        print(f"  Generated {total_links} download link(s)")
                    else:
                        print(f"  Generated {len(links)} download link(s)")
                    
                    content = updater_class.update_section(content, version, links)
                    
                    if isinstance(version, list):
                        changes_made.append(f"{distro_name} {', '.join(version)}")
                    else:
                        changes_made.append(f"{distro_name} {version}")
                else:
                    print("  Could not generate download links")
            else:
                print("  Could not determine latest version")
        except Exception as e:
            print(f"  Error updating {distro_name}: {e}")
            import traceback
            traceback.print_exc()
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nUpdated: {', '.join(changes_made)}")
        return True
    else:
        print("\nNo changes needed.")
        return False

def update_repository():
    """Clone/update the repository and commit changes."""
    import subprocess
    import tempfile
    
    # Get the repository URL based on user preference
    repo_url = get_repo_url()
    
    # Use a temporary directory for the repo
    temp_dir = Path(tempfile.gettempdir()) / 'distroget_repo'
    
    try:
        if temp_dir.exists():
            # Pull latest changes
            print(f"Updating existing repository at {temp_dir}...")
            subprocess.run(['git', '-C', str(temp_dir), 'pull'], check=True, capture_output=True)
        else:
            # Clone the repository
            print(f"Cloning repository to {temp_dir}...")
            print(f"Using: {repo_url}...")
            subprocess.run(['git', 'clone', repo_url, str(temp_dir)], check=True, capture_output=True)
        
        # Update the file
        if update_iso_list_file(temp_dir):
            # Commit changes
            subprocess.run(['git', '-C', str(temp_dir), 'add', REPO_FILE_PATH], check=True)
            subprocess.run(
                ['git', '-C', str(temp_dir), 'commit', '-m', 'Auto-update distro versions'],
                check=True
            )
            
            print("\nChanges committed. Push to GitHub? (y/n): ", end='')
            response = input().strip().lower()
            if response == 'y':
                print("Pushing to GitHub...")
                result = subprocess.run(['git', '-C', str(temp_dir), 'push'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print("✓ Changes pushed to GitHub!")
                    print("\nRestarting script to fetch updated ISO list...")
                    # Wait a moment for GitHub to process
                    import time
                    time.sleep(2)
                else:
                    print(f"✗ Push failed: {result.stderr}")
                    print(f"You can manually push from: {temp_dir}")
            else:
                print("Changes not pushed. You can manually push later from:", temp_dir)
        
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        print(f"You may need to set up authentication or check the repository at {temp_dir}")
    except Exception as e:
        print(f"Error updating repository: {e}")

def download_iso(url, target_dir, is_remote=False, remote_host=None, remote_path=None):
    filename = os.path.basename(urlparse(url).path)
    
    if is_remote:
        # Download to temp location first
        import tempfile
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, filename)
    else:
        local_path = os.path.join(target_dir, filename)
        if os.path.exists(local_path):
            print(f"Skipping {filename}, already exists.")
            return
    
    try:
        # Download the file
        r = requests.get(url, stream=True)
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))
        with open(local_path, 'wb') as f:
            downloaded = 0
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    done = int(50 * downloaded / total) if total else 0
                    sys.stdout.write(f"\rDownloading {filename}: [{'#'*done}{'.'*(50-done)}]")
                    sys.stdout.flush()
        print(f"\nDownloaded {filename}")
        
        # If remote, scp the file
        if is_remote:
            remote_file = f"{remote_host}:{remote_path}/{filename}"
            print(f"Transferring to {remote_file}...")
            import subprocess
            result = subprocess.run(['scp', local_path, remote_file], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Successfully transferred {filename} to {remote_host}")
                os.remove(local_path)  # Clean up temp file
            else:
                print(f"Error transferring {filename}: {result.stderr}")
    except Exception as e:
        print(f"\nError downloading {url}: {e}")

def fetch_iso_list():
    """Fetch ISO list from local repo if available, otherwise from GitHub."""
    import tempfile
    import subprocess
    import shutil
    
    # Check if git is available
    git_available = shutil.which('git') is not None
    
    # Try local repository first
    temp_dir = Path(tempfile.gettempdir()) / 'distroget_repo'
    local_file = temp_dir / REPO_FILE_PATH
    
    if git_available:
        try:
            if temp_dir.exists() and local_file.exists():
                # Update existing repo
                subprocess.run(['git', '-C', str(temp_dir), 'fetch'], 
                             capture_output=True, timeout=5, check=False)
                subprocess.run(['git', '-C', str(temp_dir), 'pull'], 
                             capture_output=True, timeout=5, check=False)
                print("Using local repository (updated)")
            else:
                # Clone the repository
                print("Cloning repository for local use...")
                repo_url = get_repo_url()
                subprocess.run(['git', 'clone', repo_url, str(temp_dir)], 
                             capture_output=True, timeout=30, check=True)
                print("Repository cloned successfully")
            
            # Read from local file
            with open(local_file, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
        except Exception as e:
            print(f"Warning: Git operation failed ({e}), fetching from GitHub...")
            lines = None
    else:
        print("Git not available, fetching from GitHub...")
        lines = None
    
    # Fall back to GitHub if git operations failed
    if lines is None:
        try:
            r = requests.get(ISO_LIST_URL, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            print("Fetched from GitHub")
        except Exception as e:
            print(f"Error fetching ISO list: {e}")
            sys.exit(1)
    
    # Parse the markdown content into a hierarchical structure
    try:
        distro_dict = {}
        path_stack = []  # Track current path: [distro, subcategory, subsubcategory, ...]
        current_dict = distro_dict
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
            
            # Determine heading level
            if stripped.startswith("#### "):
                # Level 4: sub-subcategory (e.g., specific spin)
                heading = stripped[5:].strip()
                level = 4
            elif stripped.startswith("### "):
                # Level 3: subcategory (e.g., Workstation, Server, Spins)
                heading = stripped[4:].strip()
                level = 3
            elif stripped.startswith("## "):
                # Level 2: main distro (e.g., Fedora)
                heading = stripped[3:].strip()
                level = 2
            else:
                heading = None
                level = 0
            
            if heading:
                # Navigate to correct level in hierarchy
                if level == 2:
                    # Top-level distro
                    path_stack = [heading]
                    current_dict = distro_dict
                    if heading not in current_dict:
                        current_dict[heading] = {}
                    current_dict = current_dict[heading]
                elif level == 3:
                    # Subcategory under distro
                    if len(path_stack) >= 1:
                        path_stack = path_stack[:1] + [heading]
                    else:
                        path_stack = [heading]
                    
                    # Navigate to parent
                    current_dict = distro_dict
                    if path_stack[0] in current_dict:
                        current_dict = current_dict[path_stack[0]]
                        if heading not in current_dict:
                            current_dict[heading] = {}
                        current_dict = current_dict[heading]
                elif level == 4:
                    # Sub-subcategory
                    if len(path_stack) >= 2:
                        path_stack = path_stack[:2] + [heading]
                    
                    # Navigate to parent
                    current_dict = distro_dict
                    for p in path_stack[:-1]:
                        if p in current_dict:
                            current_dict = current_dict[p]
                    
                    if heading not in current_dict:
                        current_dict[heading] = {}
                    current_dict = current_dict[heading]
            
            # List item with URL (- [Name](URL))
            elif stripped.startswith("- ["):
                # Parse markdown link format: [Name](URL)
                import re
                match = re.match(r'- \[([^\]]+)\]\(([^\)]+)\)', stripped)
                if match:
                    name = match.group(1)
                    url = match.group(2)
                    entry = f"{name}: {url}"
                    
                    # Add to current level
                    if not isinstance(current_dict, list):
                        # Convert dict to list if we're adding items
                        if not current_dict:  # Empty dict
                            # Navigate back and replace with list
                            parent_dict = distro_dict
                            for p in path_stack[:-1]:
                                parent_dict = parent_dict[p]
                            parent_dict[path_stack[-1]] = [entry]
                            current_dict = parent_dict[path_stack[-1]]
                        else:
                            # Has subcategories, add to special "_items" key
                            if "_items" not in current_dict:
                                current_dict["_items"] = []
                            current_dict["_items"].append(entry)
                    else:
                        current_dict.append(entry)
        
        return distro_dict
    except Exception as e:
        print(f"Error parsing ISO list: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Curses menu
def curses_menu(stdscr, distro_dict):
    import time
    
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
    current_row = 0
    scroll_offset = 0
    path_stack = []
    menu_stack = [sorted(distro_dict.keys(), key=str.lower)]  # start with sorted top-level distros (case-insensitive)
    row_stack = []  # Track cursor position for each level
    selected_items = set()
    target_directory = None
    search_mode = False
    search_buffer = ""
    last_key_time = 0
    search_timeout = 3.0  # seconds
    needs_redraw = True  # Track when screen needs redrawing

    while True:
        current_menu = menu_stack[-1]
        height, width = stdscr.getmaxyx()
        
        # Clear search buffer if timeout exceeded
        if search_mode:
            current_time = time.time()
            if search_buffer and (current_time - last_key_time) > search_timeout:
                search_buffer = ""
                search_mode = False
                needs_redraw = True
        
        # Only clear and redraw if needed
        if needs_redraw:
            stdscr.clear()
            needs_redraw = False
        
        # Calculate visible area
        header_lines = 3
        visible_lines = height - header_lines - 1  # Leave space for header and bottom
        
        # Count selected ISOs (leaf nodes only)
        iso_count = sum(1 for path in selected_items if '/' in path and not any(other.startswith(path + '/') for other in selected_items))
        
        # Header line with hint about search
        dest_info = f" | Dest: {target_directory}" if target_directory else ""
        header = f"Navigate: ↑↓, Select: SPACE, Enter/→: Enter, ←/ESC: Back, /: Search, A: All, D: Set Dir, Q: Quit | Selected: {iso_count}{dest_info}"
        stdscr.addstr(0, 0, header[:width-1])
        
        path_display = f"Path: {'/'.join(path_stack) if path_stack else 'root'}"
        if search_mode and search_buffer:
            path_display += f" | Search: {search_buffer}"
        elif search_mode:
            path_display += " | Search: _"
        stdscr.addstr(1, 0, path_display[:width-1])
        
        if not current_menu:
            stdscr.addstr(3, 0, "No items available. Press Q to quit or Enter to go back."[:width-1])
        else:
            # Adjust scroll offset to keep current row visible
            if current_row < scroll_offset:
                scroll_offset = current_row
            elif current_row >= scroll_offset + visible_lines:
                scroll_offset = current_row - visible_lines + 1
            
            # Display visible items
            for idx in range(scroll_offset, min(scroll_offset + visible_lines, len(current_menu))):
                item = current_menu[idx]
                item_path = "/".join(path_stack + [item])
                
                # Determine checkbox state
                if item_path in selected_items:
                    prefix = "[x]"
                elif path_stack == []:  # Top-level distro
                    # Check if any child items are selected
                    has_selected = any(sel.startswith(item + "/") for sel in selected_items)
                    prefix = "[o]" if has_selected else "[ ]"
                else:
                    prefix = "[ ]"
                
                display_line = f"{prefix} {item}"[:width-1]
                screen_row = idx - scroll_offset + header_lines
                
                if idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(screen_row, 0, display_line)
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(screen_row, 0, display_line)
        
        stdscr.timeout(100)  # 100ms timeout for getch to allow search timeout checking
        key = stdscr.getch()
        
        if key == -1:  # No key pressed (timeout)
            needs_redraw = False
            continue
        
        needs_redraw = True  # Key was pressed, redraw on next iteration
        
        if not current_menu:
            # Handle empty menu case
            if key in [curses.KEY_ENTER, ord('\n')]:
                if len(menu_stack) > 1:
                    path_stack.pop()
                    menu_stack.pop()
                    current_row = 0
            elif key in [ord('q'), ord('Q')]:
                break
            continue
        
        # Handle search mode
        if search_mode:
            if key == 27:  # ESC - exit search mode
                search_mode = False
                search_buffer = ""
                current_row = 0
                scroll_offset = 0
            elif key in [curses.KEY_ENTER, ord('\n')]:
                # Exit search mode and stay on current selection
                search_mode = False
                search_buffer = ""
            elif key in [curses.KEY_BACKSPACE, 127, 8]:  # Backspace
                if search_buffer:
                    search_buffer = search_buffer[:-1]
                    last_key_time = time.time()
                    # Re-search with shorter buffer
                    if search_buffer:
                        for idx, item in enumerate(current_menu):
                            if item.lower().startswith(search_buffer):
                                current_row = idx
                                break
                else:
                    search_mode = False
            elif 32 <= key <= 126 and key not in [ord('/')]:
                # Add character to search
                search_buffer += chr(key).lower()
                last_key_time = time.time()
                
                # Find first matching item
                for idx, item in enumerate(current_menu):
                    if item.lower().startswith(search_buffer):
                        current_row = idx
                        break
            continue
        
        # Normal navigation mode
        if key == ord('/') and path_stack == []:  # Start search mode (only at top level)
            search_mode = True
            search_buffer = ""
            last_key_time = time.time()
        elif key in [curses.KEY_UP, ord('k')]:
            current_row = (current_row - 1) % len(current_menu)
        elif key in [curses.KEY_DOWN, ord('j')]:
            current_row = (current_row + 1) % len(current_menu)
        elif key == ord(' '):
            item_path = "/".join(path_stack + [current_menu[current_row]])
            if item_path in selected_items:
                selected_items.remove(item_path)
            else:
                selected_items.add(item_path)
        elif key in [ord('a'), ord('A')]:
            # Select all items in current menu
            for item in current_menu:
                item_path = "/".join(path_stack + [item])
                selected_items.add(item_path)
        elif key in [ord('d'), ord('D')]:
            # Set target directory
            curses.endwin()
            target_directory = input("\nEnter target directory (or hostname:/path for remote): ").strip()
            stdscr = curses.initscr()
            curses.curs_set(0)
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        elif key in [curses.KEY_ENTER, ord('\n'), curses.KEY_RIGHT, ord('l')]:
            selected = current_menu[current_row]
            
            # Navigate to the selected item
            current_node = distro_dict
            for p in path_stack:
                current_node = current_node[p]
            
            # Check if selected item has children
            if isinstance(current_node, dict):
                next_node = current_node.get(selected)
                if next_node and (isinstance(next_node, dict) or isinstance(next_node, list)):
                    # Has children - navigate into it
                    row_stack.append(current_row)
                    path_stack.append(selected)
                    
                    # Build next menu
                    if isinstance(next_node, dict):
                        menu_stack.append(sorted(next_node.keys(), key=str.lower))
                    else:
                        menu_stack.append(next_node)
                    
                    current_row = 0
                    scroll_offset = 0
                else:
                    # Leaf node or item - toggle selection
                    item_path = "/".join(path_stack + [selected])
                    if item_path in selected_items:
                        selected_items.remove(item_path)
                    else:
                        selected_items.add(item_path)
            else:
                # In a list - toggle selection
                item_path = "/".join(path_stack + [selected])
                if item_path in selected_items:
                    selected_items.remove(item_path)
                else:
                    selected_items.add(item_path)
        elif key in [27, curses.KEY_LEFT, ord('h')]:  # 27 is ESC
            # Clear search buffer or go back
            if search_buffer:
                search_buffer = ""
                current_row = 0
                scroll_offset = 0
            elif len(menu_stack) > 1:
                path_stack.pop()
                menu_stack.pop()
                current_row = row_stack.pop() if row_stack else 0
                scroll_offset = 0
        elif key in [ord('q'), ord('Q')]:
            break
    # Return selected items mapped to actual URLs
    final_urls = []
    
    def extract_urls_from_node(node):
        """Recursively extract all URLs from a node."""
        urls = []
        if isinstance(node, list):
            # List of items - extract URLs
            for entry in node:
                if ": " in entry:
                    url = entry.split(": ", 1)[1]
                    urls.append(url)
        elif isinstance(node, dict):
            # Dictionary - recurse into children
            for key, value in node.items():
                if key != "_items":  # Skip special _items key
                    urls.extend(extract_urls_from_node(value))
            # Also check _items
            if "_items" in node:
                urls.extend(extract_urls_from_node(node["_items"]))
        return urls
    
    for sel in selected_items:
        parts = sel.split("/")
        
        # Navigate to the selected node
        current_node = distro_dict
        for part in parts:
            if isinstance(current_node, dict) and part in current_node:
                current_node = current_node[part]
            elif isinstance(current_node, list):
                # Match item in list
                for entry in current_node:
                    if entry.startswith(part):
                        if ": " in entry:
                            url = entry.split(": ", 1)[1]
                            final_urls.append(url)
                        break
                current_node = None
                break
            else:
                current_node = None
                break
        
        # Extract URLs from the final node
        if current_node:
            final_urls.extend(extract_urls_from_node(current_node))
    return final_urls, target_directory

def main():
    config = load_config()
    print("Fetching distros...")
    distro_dict = fetch_iso_list()
    selected_urls, target_dir = curses.wrapper(curses_menu, distro_dict)
    if not selected_urls:
        print("No ISOs selected, exiting.")
        sys.exit(0)
    
    # Ask for target directory if not set in UI
    if not target_dir:
        default_dir = config.get('target_directory', '')
        prompt = f"Enter target directory (or hostname:/path for remote) [{default_dir}]: " if default_dir else "Enter target directory (or hostname:/path for remote): "
        target_dir = input(prompt).strip()
        if not target_dir and default_dir:
            target_dir = default_dir
    
    # Save target directory to config
    config['target_directory'] = target_dir
    save_config(config)
    
    # Check if target is remote
    is_remote = ':' in target_dir and not target_dir.startswith('/')
    if is_remote:
        remote_host, remote_path = target_dir.split(':', 1)
        print(f"Downloading {len(selected_urls)} ISOs and transferring to {remote_host}:{remote_path} ...")
        # Ensure remote directory exists
        import subprocess
        subprocess.run(['ssh', remote_host, f'mkdir -p {remote_path}'], check=False)
        for url in selected_urls:
            download_iso(url, None, is_remote=True, remote_host=remote_host, remote_path=remote_path)
    else:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        print(f"Downloading {len(selected_urls)} ISOs to {target_dir} ...")
        for url in selected_urls:
            download_iso(url, target_dir)
    
    print("All downloads completed.")

if __name__ == "__main__":
    # Check for --update-repo flag
    if len(sys.argv) > 1 and sys.argv[1] == '--update-repo':
        update_repository()
    else:
        main()

