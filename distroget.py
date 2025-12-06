#!/usr/bin/env python3
import urwid
import json
import os
import requests
import sys
import time
import logging
from pathlib import Path
from urllib.parse import urlparse
from updaters import DISTRO_UPDATERS
from downloads import DownloadManager
from transfers import TransferManager, CombinedDownloadTransferManager
from proxmox import ProxmoxTarget, detect_file_type, select_storage_interactive
from config_manager import ConfigManager
from logger_config import setup_logging, get_log_file
import datetime

# Set up logging
logger = logging.getLogger('distroget.main')

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
    config_manager = ConfigManager()
    return config_manager.config

def save_config(config_dict):
    """Save configuration to file."""
    config_manager = ConfigManager()
    config_manager.config = config_dict
    config_manager.save()

def add_to_location_history(location):
    """Add a location to history, keeping max 10 recent unique locations."""
    config_manager = ConfigManager()
    config_manager.add_to_location_history(location)

def show_location_popup(stdscr):
    """Show a curses popup to select from location history or enter new."""
    config = load_config()
    history = config.get('location_history', [])
    
    # Build menu items
    menu_items = ['< Enter new location >']
    if history:
        menu_items.extend(history)
    
    # Calculate popup dimensions
    max_y, max_x = stdscr.getmaxyx()
    height = min(max_y - 4, len(menu_items) + 4)
    width = min(max_x - 4, max(50, max(len(item) for item in menu_items) + 4))
    start_y = (max_y - height) // 2
    start_x = (max_x - width) // 2
    
    # Create popup window
    popup = curses.newwin(height, width, start_y, start_x)
    popup.keypad(True)
    
    current_row = 0
    scroll_offset = 0
    
    while True:
        popup.clear()
        popup.border()
        
        # Title
        title = " Select Download Location "
        title_x = max(1, (width - len(title)) // 2)
        popup.addstr(0, title_x, title, curses.color_pair(1) | curses.A_BOLD)
        
        # Calculate visible items
        visible_height = height - 4
        visible_items = menu_items[scroll_offset:scroll_offset + visible_height]
        
        # Draw menu items
        for idx, item in enumerate(visible_items):
            y = idx + 2
            actual_idx = scroll_offset + idx
            
            # Truncate long items
            display_item = item[:width - 4]
            
            if actual_idx == current_row:
                popup.addstr(y, 2, display_item, curses.color_pair(1))
            else:
                popup.addstr(y, 2, display_item)
        
        # Show scroll indicators
        if scroll_offset > 0:
            popup.addstr(1, width - 3, "^", curses.color_pair(3))
        if scroll_offset + visible_height < len(menu_items):
            popup.addstr(height - 2, width - 3, "v", curses.color_pair(3))
        
        # Instructions (shortened to fit)
        instructions = "Enter:Select ESC:Cancel"
        if len(instructions) < width - 4:
            popup.addstr(height - 1, 2, instructions, curses.A_DIM)
        
        popup.refresh()
        
        key = popup.getch()
        
        if key == curses.KEY_UP:
            if current_row > 0:
                current_row -= 1
                if current_row < scroll_offset:
                    scroll_offset = current_row
        elif key == curses.KEY_DOWN:
            if current_row < len(menu_items) - 1:
                current_row += 1
                if current_row >= scroll_offset + visible_height:
                    scroll_offset = current_row - visible_height + 1
        elif key in [curses.KEY_ENTER, ord('\n')]:
            if current_row == 0:
                # Enter new location
                return None
            else:
                # Return selected history item
                return menu_items[current_row]
        elif key == 27:  # ESC
            return False  # Cancelled
    
    return None

def show_password_popup(stdscr, prompt="Enter SSH password:"):
    """Show a curses popup to enter password."""
    max_y, max_x = stdscr.getmaxyx()
    height = 7
    width = min(max_x - 4, 60)
    start_y = (max_y - height) // 2
    start_x = (max_x - width) // 2
    
    # Create popup window
    popup = curses.newwin(height, width, start_y, start_x)
    popup.keypad(True)
    
    password = ""
    
    while True:
        popup.clear()
        popup.border()
        
        # Title
        title = " SSH Authentication "
        title_x = max(1, (width - len(title)) // 2)
        popup.addstr(0, title_x, title, curses.color_pair(1) | curses.A_BOLD)
        
        # Prompt
        popup.addstr(2, 2, prompt[:width - 4])
        
        # Password field (show asterisks)
        password_display = "*" * len(password)
        popup.addstr(3, 2, password_display[:width - 4])
        
        # Instructions
        popup.addstr(5, 2, "Enter:Submit ESC:Cancel", curses.A_DIM)
        
        popup.refresh()
        
        key = popup.getch()
        
        if key in [curses.KEY_ENTER, ord('\n')]:
            return password
        elif key == 27:  # ESC
            return None
        elif key in [curses.KEY_BACKSPACE, 127, 8]:
            if password:
                password = password[:-1]
        elif 32 <= key <= 126:
            password += chr(key)
    
    return None

def show_failed_verification_popup(stdscr, download_manager):
    """Show a popup for files that failed hash verification and allow deletion."""
    failed_files = download_manager.get_failed_verifications()
    
    if not failed_files:
        return
    
    max_y, max_x = stdscr.getmaxyx()
    height = min(len(failed_files) + 10, max_y - 4)
    width = min(max_x - 4, 80)
    start_y = (max_y - height) // 2
    start_x = (max_x - width) // 2
    
    # Create popup window
    popup = curses.newwin(height, width, start_y, start_x)
    popup.keypad(True)
    
    while True:
        popup.clear()
        popup.border()
        
        # Title
        title = " Hash Verification Failed "
        title_x = max(1, (width - len(title)) // 2)
        popup.attron(curses.color_pair(4) | curses.A_BOLD)
        popup.addstr(0, title_x, title)
        popup.attroff(curses.color_pair(4) | curses.A_BOLD)
        
        # Warning message
        popup.addstr(2, 2, "The following files failed hash verification:", curses.color_pair(4))
        popup.addstr(3, 2, "These files may be corrupted or incomplete.", curses.A_DIM)
        
        # List failed files
        y_pos = 5
        for i, (filepath, message) in enumerate(failed_files[:height - 12]):
            filename = os.path.basename(filepath)[:width - 6]
            popup.attron(curses.color_pair(4))
            popup.addstr(y_pos + i, 3, f"✗ {filename}")
            popup.attroff(curses.color_pair(4))
        
        if len(failed_files) > height - 12:
            popup.addstr(y_pos + height - 12, 3, f"... and {len(failed_files) - (height - 12)} more")
        
        # Options
        options_y = height - 5
        popup.addstr(options_y, 2, "What would you like to do?", curses.A_BOLD)
        popup.addstr(options_y + 1, 3, "[D] Delete all failed files")
        popup.addstr(options_y + 2, 3, "[K] Keep files (ignore verification)")
        popup.addstr(options_y + 3, 2, "Press D or K to choose", curses.A_DIM)
        
        popup.refresh()
        
        key = popup.getch()
        
        if key in [ord('d'), ord('D')]:
            # Confirm deletion
            popup.clear()
            popup.border()
            popup.addstr(0, title_x, title, curses.color_pair(4) | curses.A_BOLD)
            popup.addstr(height // 2 - 1, 2, "Delete all failed files?", curses.A_BOLD)
            popup.addstr(height // 2 + 1, 2, "[Y] Yes, delete them")
            popup.addstr(height // 2 + 2, 2, "[N] No, go back")
            popup.refresh()
            
            confirm_key = popup.getch()
            if confirm_key in [ord('y'), ord('Y')]:
                # Perform deletion
                deleted = download_manager.delete_failed_verifications()
                
                # Show confirmation
                popup.clear()
                popup.border()
                popup.addstr(0, title_x, " Deletion Complete ", curses.color_pair(2) | curses.A_BOLD)
                popup.addstr(height // 2, 2, f"Deleted {len(deleted)} file(s)", curses.color_pair(2))
                popup.addstr(height // 2 + 2, 2, "Press any key to continue...", curses.A_DIM)
                popup.refresh()
                popup.getch()
                return
            # else go back to main menu (continue loop)
        elif key in [ord('k'), ord('K'), 27]:  # K or ESC
            return

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

def validate_url(url, timeout=5):
    """Check if a URL exists using HEAD request."""
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


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
    
    # Update auto-update status section at the top
    auto_update_section = "## Auto-Updated Distributions\n\n"
    auto_update_section += "The following distributions are automatically updated with the latest versions:\n\n"
    for distro_name in sorted(DISTRO_UPDATERS.keys()):
        auto_update_section += f"- ✓ {distro_name}\n"
    auto_update_section += f"\n*Last update check: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n\n"
    auto_update_section += "---\n\n"
    
    # Check if auto-update section exists
    if "## Auto-Updated Distributions" in content:
        # Update existing section
        import re
        pattern = r'## Auto-Updated Distributions.*?(?=\n##[^#]|\Z)'
        content = re.sub(pattern, auto_update_section.rstrip() + '\n\n', content, flags=re.DOTALL)
    else:
        # Add section after any leading comments/title but before first ## header
        import re
        match = re.search(r'^(.*?)(## [^#])', content, re.DOTALL)
        if match:
            content = match.group(1) + auto_update_section + match.group(2) + content[match.end():]
        else:
            # No headers found, add at the beginning
            content = auto_update_section + content
    
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
                    # Validate URLs
                    print("  Validating URLs...")
                    validated = 0
                    total = 0
                    
                    # Extract URLs from links structure
                    urls_to_check = []
                    if isinstance(links, dict):
                        for key, value in links.items():
                            if isinstance(value, list):
                                for url in value:
                                    if isinstance(url, str) and url.startswith('http'):
                                        urls_to_check.append(url)
                                    elif isinstance(url, str):
                                        # Extract URL from markdown format
                                        import re
                                        match = re.search(r'\(([^)]+)\)', url)
                                        if match:
                                            urls_to_check.append(match.group(1))
                    elif isinstance(links, list):
                        for link in links:
                            # Extract URL from markdown format
                            import re
                            match = re.search(r'\(([^)]+)\)', link)
                            if match:
                                urls_to_check.append(match.group(1))
                    
                    # Validate a sample of URLs (up to 3 to avoid too many requests)
                    sample_urls = urls_to_check[:min(3, len(urls_to_check))]
                    for url in sample_urls:
                        if validate_url(url):
                            validated += 1
                        total += 1
                    
                    if total > 0:
                        print(f"  Validated {validated}/{total} URLs (sample)")
                    
                    # Count links differently for hierarchical structures
                    if isinstance(links, dict):
                        total_links = sum(len(v) if isinstance(v, list) else sum(len(sv) for sv in v.values() if isinstance(sv, list)) 
                                        for v in links.values())
                        print(f"  Generated {total_links} download link(s)")
                    else:
                        print(f"  Generated {len(links)} download link(s)")
                    
                    # Add metadata: auto-update marker and timestamp
                    current_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                    content = updater_class.update_section(content, version, links, 
                                                          metadata={'auto_updated': True, 'last_updated': current_time})
                    
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
        skip_section = False  # Track if we're in a section to skip
        
        # Sections to skip (not actual distros)
        SKIP_SECTIONS = {
            'Auto-Updated Distributions',
            'Contributions',
            'Contributing',
            'License',
            'About',
            'Credits'
        }
        
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
                # Check if this is a section to skip
                if level == 2 and heading in SKIP_SECTIONS:
                    skip_section = True
                    continue
                elif level == 2:
                    skip_section = False
                
                # Skip content in skipped sections
                if skip_section:
                    continue
                
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
                # Skip content in skipped sections
                if skip_section:
                    continue
                
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

def extract_urls_for_path(distro_dict, item_path):
    """Extract URLs for a specific item path."""
    path_parts = item_path.split('/')
    current_node = distro_dict
    
    for part in path_parts:
        if isinstance(current_node, dict):
            if part in current_node:
                current_node = current_node[part]
            else:
                return []
        else:
            return []
    
    return extract_urls_from_node(current_node)

# ============================================================================
# Urwid UI Components
# ============================================================================

class SelectableText(urwid.Text):
    """Text widget that can be selected."""
    
    def selectable(self):
        return True
    
    def keypress(self, size, key):
        return key


class DistroCheckBox(urwid.CheckBox):
    """Enhanced checkbox for distro selection."""
    
    def __init__(self, label, state=False, path="", has_children=False, item_name="", indent=0):
        super().__init__(label, state=state)
        self.path = path
        self.has_children = has_children
        self.is_auto_deploy = False
        self.item_name = item_name
        self.indent = indent
    
    def set_auto_deploy(self, value):
        self.is_auto_deploy = value
        self._invalidate()


class DownloadStatusWidget(urwid.WidgetWrap):
    """Widget to display download status with progress."""
    
    def __init__(self, filename, total=0):
        self.filename = filename
        self.total = total
        self.progress = 0
        self.status = "queued"
        
        self.text = urwid.Text("")
        self.progress_bar = urwid.ProgressBar('pg_normal', 'pg_complete', 0, total or 100)
        
        pile = urwid.Pile([
            urwid.Text(('filename', filename)),
            self.progress_bar,
            self.text
        ])
        
        super().__init__(pile)
        self.update_display()
    
    def update_display(self):
        """Update the display based on current status."""
        if self.status == "active":
            if self.total > 0:
                pct = int(100 * self.progress / self.total)
                self.progress_bar.set_completion(self.progress)
                self.text.set_text(f"⬇ Downloading... {pct}%")
            else:
                self.text.set_text("⬇ Downloading...")
        elif self.status == "completed":
            self.progress_bar.set_completion(self.total or 100)
            self.text.set_text(('success', "✓ Completed"))
        elif self.status == "failed":
            self.text.set_text(('error', "✗ Failed"))
        elif self.status == "verifying":
            self.text.set_text(('warning', "⚙ Verifying hash..."))
        elif self.status == "verified":
            self.text.set_text(('success', "✓ Verified"))
        elif self.status == "verify_failed":
            self.text.set_text(('error', "✗ Hash verification failed"))
        else:
            self.text.set_text("⋯ Queued")
    
    def update_progress(self, progress, total, status="active"):
        """Update progress values."""
        self.progress = progress
        self.total = total
        self.status = status
        self.update_display()


class DistroGetUI:
    """Main urwid UI for distroget."""
    
    palette = [
        ('header', 'white,bold', 'dark blue'),
        ('footer', 'white', 'dark blue'),
        ('selected', 'black', 'light gray'),
        ('focus', 'black', 'yellow'),
        ('checked', 'light green,bold', 'default'),
        ('filename', 'light cyan', 'default'),
        ('success', 'light green', 'default'),
        ('error', 'light red', 'default'),
        ('warning', 'yellow', 'default'),
        ('pg_normal', 'white', 'dark blue'),
        ('pg_complete', 'white', 'light green'),
        ('auto_deploy', 'light magenta', 'default'),
    ]
    
    def __init__(self, distro_dict):
        self.distro_dict = distro_dict
        self.config_mgr = ConfigManager()
        self.selected_items = set()
        self.downloaded_items = set()
        self.auto_deploy_items = set(self.config_mgr.get_auto_deploy_items())
        self.target_directory = None
        self.download_manager = None
        self.path_stack = []
        self.current_menu = sorted(distro_dict.keys(), key=str.lower)
        self.search_mode = False
        self.search_results = []
        self.expanded_items = set()  # Track which items are expanded
        self.terminal_width = 80  # Default, will be updated
        self.left_panel_width = 48  # 60% of 80
        self.terminal_width = 80  # Default, will be updated
        self.left_panel_width = 48  # 60% of 80
        
        # Create UI components
        self.create_menu()
        self.create_download_panel()
        self.create_layout()
        
        # Setup main loop
        self.loop = urwid.MainLoop(
            self.main_frame,
            palette=self.palette,
            unhandled_input=self.handle_input
        )
        
        # Schedule periodic updates for downloads
        self.update_alarm = None
        self.schedule_update()
    
    def create_menu(self):
        """Create the left menu panel."""
        self.menu_items = []
        self.menu_walker = urwid.SimpleFocusListWalker(self.menu_items)
        self.menu_listbox = urwid.ListBox(self.menu_walker)
        
        self.update_menu()
        
        # Wrap in a line box
        self.menu_box = urwid.LineBox(
            self.menu_listbox,
            title="ISO Selection"
        )
    
    def create_download_panel(self):
        """Create the right download status panel."""
        self.download_widgets = {}
        self.download_walker = urwid.SimpleFocusListWalker([
            urwid.Text("No downloads active")
        ])
        self.download_listbox = urwid.ListBox(self.download_walker)
        
        self.download_box = urwid.LineBox(
            self.download_listbox,
            title="Downloads"
        )
    
    def create_layout(self):
        """Create the main layout."""
        # Get terminal size
        try:
            import shutil
            term_size = shutil.get_terminal_size()
            self.terminal_width = term_size.columns
        except:
            self.terminal_width = 80
        
        # Calculate left panel width (60% of screen minus borders and padding)
        self.left_panel_width = int(self.terminal_width * 0.6) - 6  # Account for borders, checkbox, padding
        
        # Header
        path_text = f"Path: {'/'.join(self.path_stack) if self.path_stack else 'root'}"
        selected_text = f"Selected: {len(self.selected_items)}"
        dest_text = f"Dest: {self.target_directory or 'Not set'}"
        
        self.header = urwid.AttrMap(
            urwid.Text(f"{path_text} | {selected_text} | {dest_text}"),
            'header'
        )
        
        # Footer
        help_text = "↑↓:Navigate ←→:Collapse/Expand Enter:Toggle SPACE:Select C:ClearAll /:Search D:Dir Q:Quit"
        self.footer = urwid.AttrMap(urwid.Text(help_text), 'footer')
        
        # Main columns (60/40 split)
        self.columns = urwid.Columns([
            ('weight', 60, self.menu_box),
            ('weight', 40, self.download_box)
        ])
        
        # Wrap columns in a custom widget that intercepts arrow keys
        self.main_widget = urwid.WidgetWrap(self.columns)
        
        # Main frame
        self.main_frame = urwid.Frame(
            self.main_widget,
            header=self.header,
            footer=self.footer
        )
        
        # Override keypress to intercept navigation keys
        original_keypress = self.main_frame.keypress
        
        def custom_keypress(size, key):
            # Intercept arrow keys before they reach the widgets
            if key in ('right', 'l', 'left', 'h', 'esc'):
                # Let our handler process it
                result = self.handle_input(key)
                if result:
                    return None  # Key was handled
            # Let the frame handle other keys
            return original_keypress(size, key)
        
        self.main_frame.keypress = custom_keypress
    
    def update_menu(self):
        """Update menu items with tree-view style (indented children)."""
        self.menu_walker.clear()
        
        def add_items_recursively(items, path_prefix, indent_level=0):
            """Recursively add items with proper indentation."""
            if isinstance(items, dict):
                # Sort keys for consistent ordering
                sorted_keys = sorted(items.keys(), key=str.lower)
                for item in sorted_keys:
                    if item == "_items":  # Skip special items key
                        continue
                    
                    item_path = "/".join(path_prefix + [item])
                    child_node = items[item]
                    
                    # Check if this is a leaf or has children
                    has_children = isinstance(child_node, dict) or isinstance(child_node, list)
                    is_selected = item_path in self.selected_items
                    is_auto = item_path in self.auto_deploy_items
                    is_expanded = item_path in self.expanded_items
                    
                    # Check for partial selection (some but not all children selected)
                    partial_selection = False
                    if has_children and not is_selected:
                        # Count selected children
                        selected_children = [s for s in self.selected_items if s.startswith(item_path + "/")]
                        if selected_children:
                            partial_selection = True
                    
                    # Create indent and markers
                    indent_str = "  " * indent_level
                    folder_marker = "▼ " if (has_children and is_expanded) else ("▶ " if has_children else "  ")
                    auto_marker = "[a]" if is_auto else "   "
                    
                    # Clip long labels to prevent wrapping based on actual panel width
                    full_label = f"{indent_str}{auto_marker} {folder_marker}{item}"
                    max_width = max(self.left_panel_width - 4, 30)  # Ensure minimum width
                    label = full_label[:max_width] if len(full_label) > max_width else full_label
                    
                    # Create checkbox with proper state (including partial)
                    if partial_selection:
                        # Use special state for partial selection
                        checkbox = urwid.CheckBox(label, state=False, has_mixed=True)
                        # Store our custom attributes
                        checkbox.path = item_path
                        checkbox.has_children = has_children
                        checkbox.is_auto_deploy = False
                        checkbox.item_name = item
                        checkbox.indent = indent_level
                        # Override the display to show [o]
                        checkbox._label.set_text(label.replace("[ ]", "[o]"))
                    else:
                        checkbox = DistroCheckBox(
                            label,
                            state=is_selected,
                            path=item_path,
                            has_children=has_children,
                            item_name=item,
                            indent=indent_level
                        )
                        checkbox.set_auto_deploy(is_auto)
                    
                    # Connect signal for checkbox changes
                    urwid.connect_signal(checkbox, 'change', 
                                        lambda cb, state, path=item_path: self.on_checkbox_changed(cb, state, path))
                    
                    self.menu_walker.append(checkbox)
                    
                    # If expanded, show children
                    if is_expanded and has_children:
                        if isinstance(child_node, dict):
                            # Recursively show nested folders and their contents
                            add_items_recursively(child_node, path_prefix + [item], indent_level + 1)
                        elif isinstance(child_node, list):
                            # List of URLs - show them indented
                            for url_item in child_node:
                                url_path = item_path + "/" + url_item
                                is_url_selected = url_path in self.selected_items
                                
                                indent_str = "  " * (indent_level + 1)
                                full_url_label = f"{indent_str}    {url_item}"
                                max_width = max(self.left_panel_width - 4, 30)
                                url_label = full_url_label[:max_width] if len(full_url_label) > max_width else full_url_label
                                
                                url_checkbox = DistroCheckBox(
                                    url_label,
                                    state=is_url_selected,
                                    path=url_path,
                                    has_children=False,
                                    item_name=url_item,
                                    indent=indent_level + 1
                                )
                                
                                urwid.connect_signal(url_checkbox, 'change',
                                                    lambda cb, state, path=url_path: self.on_checkbox_changed(cb, state, path))
                                
                                self.menu_walker.append(url_checkbox)
            elif isinstance(items, list):
                # Direct list of URLs
                for url_item in items:
                    url_path = "/".join(path_prefix + [url_item])
                    is_url_selected = url_path in self.selected_items
                    
                    indent_str = "  " * indent_level
                    full_url_label = f"{indent_str}    {url_item}"
                    max_width = max(self.left_panel_width - 4, 30)
                    url_label = full_url_label[:max_width] if len(full_url_label) > max_width else full_url_label
                    
                    url_checkbox = DistroCheckBox(
                        url_label,
                        state=is_url_selected,
                        path=url_path,
                        has_children=False,
                        item_name=url_item,
                        indent=indent_level
                    )
                    
                    urwid.connect_signal(url_checkbox, 'change',
                                        lambda cb, state, path=url_path: self.on_checkbox_changed(cb, state, path))
                    
                    self.menu_walker.append(url_checkbox)
        
        # Start building from root
        add_items_recursively(self.distro_dict, [])
    
    def on_checkbox_changed(self, checkbox, new_state, item_path):
        """Handle checkbox state changes."""
        try:
            if new_state:
                self.selected_items.add(item_path)
                
                # Queue for download if manager is active
                if self.download_manager:
                    urls = extract_urls_for_path(self.distro_dict, item_path)
                    for url in urls:
                        if url not in self.downloaded_items:
                            logger.info(f"Queueing download: {url}")
                            self.download_manager.add_download(url)
                            self.downloaded_items.add(url)
            else:
                self.selected_items.discard(item_path)
            self.update_header()
        except Exception as e:
            self.show_error_dialog(
                "Download Queue Error",
                "Failed to queue item for download.",
                f"Item: {item_path}\nError: {e}"
            )
    
    def update_header(self):
        """Update the header with current info."""
        # Count leaf selections only
        iso_count = sum(1 for path in self.selected_items 
                       if '/' in path and not any(other.startswith(path + '/') 
                                                  for other in self.selected_items))
        selected_text = f"Selected: {iso_count}"
        dest_text = f"Dest: {self.target_directory or 'Not set'}"
        expanded_count = len(self.expanded_items)
        expand_text = f"Expanded: {expanded_count}" if expanded_count > 0 else "Tree View"
        
        self.header.original_widget.set_text(f"{expand_text} | {selected_text} | {dest_text}")
    
    def update_download_panel(self):
        """Update download status display."""
        if not self.download_manager:
            return
        
        try:
            status = self.download_manager.get_status()
        except Exception as e:
            self.download_walker.clear()
            self.download_walker.append(urwid.Text(('error', f"Error fetching status: {e}")))
            return
        
        # Clear and rebuild
        self.download_walker.clear()
        
        # Summary line
        summary = f"Total: {status['completed'] + status['failed'] + status['queued']} | "
        summary += f"Done: {status['completed']} | Failed: {status['failed']}"
        if status['queued'] > 0:
            summary += f" | Queued: {status['queued']}"
        
        self.download_walker.append(urwid.Text(('header', summary)))
        self.download_walker.append(urwid.Divider())
        
        # Active downloads
        if status['active']:
            self.download_walker.append(urwid.Text(('warning', "Active Downloads:")))
            for url, info in status['active'].items():
                if url not in self.download_widgets:
                    self.download_widgets[url] = DownloadStatusWidget(
                        info['filename'],
                        info.get('total', 0)
                    )
                
                widget = self.download_widgets[url]
                widget.update_progress(
                    info.get('progress', 0),
                    info.get('total', 0),
                    'active'
                )
                self.download_walker.append(widget)
            
            self.download_walker.append(urwid.Divider())
        
        # Completed files
        if status['downloaded_files']:
            self.download_walker.append(urwid.Text(('success', "Downloaded Files:")))
            
            for filepath in status['downloaded_files'][:10]:  # Limit display
                filename = os.path.basename(filepath)
                
                # Check hash verification status
                verification = status.get('hash_verification', {}).get(filepath, (None, ''))
                
                if verification[0] is True:
                    icon = ('success', "✓")
                elif verification[0] is False:
                    icon = ('error', "✗")
                else:
                    icon = ('warning', "•")
                
                self.download_walker.append(
                    urwid.Text([icon, " ", filename])
                )
        
        if not status['active'] and not status['downloaded_files']:
            self.download_walker.append(urwid.Text("Set target dir (D) to begin"))
    
    def schedule_update(self):
        """Schedule next update."""
        if self.update_alarm:
            self.loop.remove_alarm(self.update_alarm)
        
        self.update_alarm = self.loop.set_alarm_in(0.5, self.periodic_update)
    
    def periodic_update(self, loop, user_data):
        """Periodically update download status."""
        if self.download_manager:
            self.update_download_panel()
            self.loop.draw_screen()
        
        self.schedule_update()
    
    def handle_input(self, key):
        """Handle keyboard input."""
        if key in ('q', 'Q'):
            self.cleanup()
            raise urwid.ExitMainLoop()
        
        elif key == 'enter':
            # Toggle expand/collapse for selected item
            focus_widget = self.menu_listbox.focus
            if focus_widget and hasattr(focus_widget, 'item_name'):
                self.toggle_expand(focus_widget)
            return True
        
        elif key in ('right', 'l'):
            # Expand container
            focus_widget = self.menu_listbox.focus
            if focus_widget and hasattr(focus_widget, 'has_children') and focus_widget.has_children:
                if focus_widget.path not in self.expanded_items:
                    self.expanded_items.add(focus_widget.path)
                    focused_path = focus_widget.path
                    self.update_menu()
                    self.update_header()
                    # Restore focus to the expanded item
                    for idx, widget in enumerate(self.menu_walker):
                        if hasattr(widget, 'path') and widget.path == focused_path:
                            self.menu_walker.set_focus(idx)
                            break
            return True
        
        elif key in ('left', 'esc', 'h'):
            # Collapse container or go to parent
            focus_widget = self.menu_listbox.focus
            if focus_widget and hasattr(focus_widget, 'path'):
                focused_path = focus_widget.path
                # If this item is expanded, collapse it
                if focus_widget.path in self.expanded_items:
                    self.expanded_items.remove(focus_widget.path)
                    self.update_menu()
                    self.update_header()
                    # Restore focus
                    for idx, widget in enumerate(self.menu_walker):
                        if hasattr(widget, 'path') and widget.path == focused_path:
                            self.menu_walker.set_focus(idx)
                            break
                else:
                    # Find and collapse parent
                    path_parts = focus_widget.path.split('/')
                    if len(path_parts) > 1:
                        parent_path = '/'.join(path_parts[:-1])
                        if parent_path in self.expanded_items:
                            self.expanded_items.remove(parent_path)
                            self.update_menu()
                            self.update_header()
                            # Try to focus on parent
                            for idx, widget in enumerate(self.menu_walker):
                                if hasattr(widget, 'path') and widget.path == parent_path:
                                    self.menu_walker.set_focus(idx)
                                    break
            return True
        
        elif key in ('d', 'D'):
            # Set download directory
            self.show_directory_dialog()
            return True
        
        elif key in ('a', 'A'):
            # Toggle auto-deploy
            focus_widget = self.menu_listbox.focus
            if focus_widget and hasattr(focus_widget, 'path'):
                self.toggle_auto_deploy(focus_widget.path)
            return True
        
        elif key in ('v', 'V'):
            # View failed verifications
            if self.download_manager:
                self.show_failed_verifications()
            return True
        
        elif key in ('c', 'C'):
            # Clear all selections and cancel downloads
            self.show_clear_all_dialog()
            return True
        
        elif key == '/':
            # Start search (only at root level)
            if not self.path_stack:
                self.show_search_dialog()
            return True
    
    def toggle_expand(self, widget):
        """Toggle expansion of a tree item."""
        if not hasattr(widget, 'has_children') or not widget.has_children:
            return
        
        if widget.path in self.expanded_items:
            self.expanded_items.remove(widget.path)
        else:
            self.expanded_items.add(widget.path)
        
        self.update_menu()
        self.update_header()
        
        # Try to keep focus on the same item
        for idx, w in enumerate(self.menu_walker):
            if hasattr(w, 'path') and w.path == widget.path:
                self.menu_walker.set_focus(idx)
                break
    
    def navigate_to(self, item):
        """Navigate to and expand an item (used by search)."""
        # Find the item in the tree and expand it
        for idx, widget in enumerate(self.menu_walker):
            if hasattr(widget, 'item_name') and widget.item_name == item:
                if hasattr(widget, 'has_children') and widget.has_children:
                    if widget.path not in self.expanded_items:
                        self.expanded_items.add(widget.path)
                        self.update_menu()
                        self.update_header()
                        # Refocus after update
                        for new_idx, w in enumerate(self.menu_walker):
                            if hasattr(w, 'path') and w.path == widget.path:
                                self.menu_walker.set_focus(new_idx)
                                break
                break
    
    def show_directory_dialog(self):
        """Show dialog to set download directory with history."""
        config = load_config()
        history = config.get('location_history', [])
        
        # Build menu items
        menu_items = []
        buttons = []
        
        # Add "Enter new location" option
        new_button = urwid.Button("< Enter new location >")
        urwid.connect_signal(new_button, 'click', lambda btn: self.enter_new_directory())
        buttons.append(urwid.AttrMap(new_button, None, focus_map='focus'))
        
        # Add history items
        for location in history:
            btn = urwid.Button(location)
            urwid.connect_signal(btn, 'click', lambda btn, loc=location: self.set_directory(loc))
            buttons.append(urwid.AttrMap(btn, None, focus_map='focus'))
        
        if not buttons:
            buttons.append(urwid.Text("No history available"))
        
        # Create listbox
        walker = urwid.SimpleFocusListWalker(buttons)
        listbox = urwid.ListBox(walker)
        
        dialog = urwid.LineBox(
            urwid.Pile([
                urwid.Text("Select Download Location:"),
                urwid.Divider(),
                urwid.BoxAdapter(listbox, height=min(10, len(buttons) + 2)),
                urwid.Divider(),
                urwid.Text("Use ↑↓ to navigate, Enter to select, Esc to cancel")
            ])
        )
        
        overlay = urwid.Overlay(
            dialog,
            self.main_frame,
            align='center',
            width=70,
            valign='middle',
            height=min(20, len(buttons) + 8)
        )
        
        original_input_handler = self.loop.unhandled_input
        
        def handle_dialog_input(key):
            if key == 'esc':
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
        
        self.loop.widget = overlay
        self.loop.unhandled_input = handle_dialog_input
    
    def enter_new_directory(self):
        """Show text input dialog for entering new directory."""
        edit = urwid.Edit("Download directory: ", self.target_directory or "")
        
        dialog = urwid.LineBox(
            urwid.Pile([
                urwid.Text("Enter download directory:"),
                urwid.Text("(or hostname:/path for remote)"),
                urwid.Divider(),
                edit,
                urwid.Divider(),
                urwid.Text("Press Enter to confirm, Esc to cancel")
            ])
        )
        
        overlay = urwid.Overlay(
            dialog,
            self.main_frame,
            align='center',
            width=60,
            valign='middle',
            height=10
        )
        
        original_input_handler = self.loop.unhandled_input
        
        def handle_dialog_input(key):
            if key == 'enter':
                new_dir = edit.get_edit_text()
                if new_dir:
                    self.set_directory(new_dir)
                else:
                    self.loop.widget = self.main_frame
                    self.loop.unhandled_input = original_input_handler
            elif key == 'esc':
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
        
        self.loop.widget = overlay
        self.loop.unhandled_input = handle_dialog_input
    
    def set_directory(self, directory):
        """Set the download directory and initialize manager."""
        try:
            self.target_directory = directory
            
            # Add to history
            add_to_location_history(directory)
            
            # Expand ~ and environment variables for local paths
            if ':' not in self.target_directory:
                self.target_directory = os.path.expandvars(os.path.expanduser(self.target_directory))
                os.makedirs(self.target_directory, exist_ok=True)
            
            self.initialize_download_manager()
            self.loop.widget = self.main_frame
            self.loop.unhandled_input = self.handle_input
            self.update_header()
            self.update_download_panel()
        except PermissionError as e:
            self.show_error_dialog(
                "Permission Denied",
                f"Cannot create or access directory:\n{directory}",
                f"Error: {e}"
            )
            self.target_directory = None
        except OSError as e:
            self.show_error_dialog(
                "Directory Error",
                f"Cannot create directory:\n{directory}",
                f"Error: {e}"
            )
            self.target_directory = None
        except Exception as e:
            self.show_error_dialog(
                "Unexpected Error",
                "An error occurred while setting the download directory.",
                f"Error: {e}"
            )
            self.target_directory = None
    
    def initialize_download_manager(self):
        """Initialize the download manager."""
        if not self.download_manager:
            try:
                self.download_manager = DownloadManager(self.target_directory)
                self.download_manager.start()
                
                # Queue already-selected items
                for item_path in self.selected_items:
                    urls = extract_urls_for_path(self.distro_dict, item_path)
                    for url in urls:
                        if url not in self.downloaded_items:
                            self.download_manager.add_download(url)
                            self.downloaded_items.add(url)
            except Exception as e:
                self.show_error_dialog(
                    "Download Manager Error",
                    "Failed to initialize the download manager.",
                    f"Error: {e}"
                )
                self.download_manager = None
    
    def toggle_auto_deploy(self, item_path):
        """Toggle auto-deploy marker for an item."""
        try:
            if item_path in self.auto_deploy_items:
                self.auto_deploy_items.discard(item_path)
                self.config_mgr.remove_auto_deploy_item(item_path)
            else:
                self.auto_deploy_items.add(item_path)
                self.config_mgr.add_auto_deploy_item(item_path)
            
            self.update_menu()
        except Exception as e:
            self.show_error_dialog(
                "Configuration Error",
                "Failed to update auto-deploy marker.",
                f"Error: {e}"
            )
    
    def show_search_dialog(self):
        """Show search dialog for finding distros."""
        edit = urwid.Edit("Search: ", "")
        
        # Create a list for displaying results
        results_walker = urwid.SimpleFocusListWalker([
            urwid.Text("Type to search distros...")
        ])
        results_listbox = urwid.ListBox(results_walker)
        
        search_results = []
        
        def update_search(edit_widget, new_text):
            """Update search results as user types."""
            query = new_text.lower()
            if not query:
                results_walker[:] = [urwid.Text("Type to search distros...")]
                search_results.clear()
                return
            
            # Search through all top-level distros
            matches = []
            for distro_name in sorted(self.distro_dict.keys(), key=str.lower):
                if query in distro_name.lower():
                    matches.append(distro_name)
            
            # Update results list
            if matches:
                search_results.clear()
                search_results.extend(matches)
                
                # Build new results list
                new_results = []
                for match in matches[:20]:  # Limit to 20 results
                    btn = urwid.Button(match)
                    urwid.connect_signal(btn, 'click', lambda b, m=match: jump_to_match(m))
                    new_results.append(urwid.AttrMap(btn, None, focus_map='focus'))
                
                if len(matches) > 20:
                    new_results.append(urwid.Text(f"... and {len(matches) - 20} more"))
                
                results_walker[:] = new_results
            else:
                results_walker[:] = [urwid.Text(("error", "No matches found"))]
                search_results.clear()
        
        # Connect the change event to update search
        urwid.connect_signal(edit, 'change', update_search)
        
        def jump_to_match(match_name):
            """Jump to a specific match in the main menu and open it."""
            # Close dialog first
            self.loop.widget = self.main_frame
            self.loop.unhandled_input = original_input_handler
            
            # Find index in menu and move focus
            try:
                idx = self.current_menu.index(match_name)
                # Set focus on the walker
                self.menu_walker.set_focus(idx)
                # Ensure left panel has focus
                self.columns.focus_position = 0
                # Force redraw
                self.loop.draw_screen()
                
                # Auto-open the matched distro (navigate into it)
                self.navigate_to(match_name)
            except (ValueError, IndexError):
                pass
        
        pile_contents = [
            urwid.Text("Search Distributions (at root level):"),
            urwid.Divider(),
            edit,
            urwid.Divider(),
            urwid.BoxAdapter(results_listbox, height=8),
            urwid.Divider(),
            urwid.Text("Type to search, ↑↓ to select, Enter to jump, Esc to cancel")
        ]
        
        pile = urwid.Pile(pile_contents)
        # Set initial focus to the edit widget
        pile.focus_position = 2  # The edit widget is at index 2
        
        dialog = urwid.LineBox(pile)
        
        overlay = urwid.Overlay(
            dialog,
            self.main_frame,
            align='center',
            width=70,
            valign='middle',
            height=18
        )
        
        original_input_handler = self.loop.unhandled_input
        
        def handle_dialog_input(key):
            # Ignore mouse events
            if isinstance(key, tuple):
                return
            
            if key == 'enter':
                # Jump to first/selected search result
                if search_results:
                    # Check if we're in the results list
                    if pile.focus_position == 4:  # results_listbox position
                        # Get focused item from results listbox
                        focus_widget = results_listbox.focus
                        if focus_widget and hasattr(focus_widget, 'original_widget'):
                            # It's an AttrMap wrapping a Button
                            button = focus_widget.original_widget
                            if hasattr(button, 'get_label'):
                                match_name = button.get_label()
                                jump_to_match(match_name)
                                return
                    
                    # Fallback to first result
                    jump_to_match(search_results[0])
                else:
                    # No results, just close
                    self.loop.widget = self.main_frame
                    self.loop.unhandled_input = original_input_handler
            elif key == 'esc':
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
            elif key == 'tab':
                # Switch focus between edit and results
                if pile.focus_position == 2:  # edit
                    pile.focus_position = 4  # results
                else:
                    pile.focus_position = 2  # edit
            elif key in ('up', 'down') and pile.focus_position == 2:
                # If we're in edit and press up/down, move to results
                if search_results:
                    pile.focus_position = 4
        
        self.loop.widget = overlay
        self.loop.unhandled_input = handle_dialog_input
    
    def show_error_dialog(self, title, message, error_details=None):
        """Show an error dialog.
        
        Args:
            title: Brief error title
            message: Main error message
            error_details: Optional detailed error information
        """
        content = [
            urwid.Text(('error', title)),
            urwid.Divider(),
            urwid.Text(message),
        ]
        
        if error_details:
            content.extend([
                urwid.Divider(),
                urwid.Text(('warning', "Details:")),
                urwid.Text(str(error_details)),
            ])
        
        content.extend([
            urwid.Divider(),
            urwid.Text("Press any key to close")
        ])
        
        dialog = urwid.LineBox(urwid.Pile(content))
        
        overlay = urwid.Overlay(
            dialog,
            self.main_frame,
            align='center',
            width=('relative', 70),
            valign='middle',
            height=('relative', 50)
        )
        
        original_input_handler = self.loop.unhandled_input
        
        def handle_dialog_input(key):
            self.loop.widget = self.main_frame
            self.loop.unhandled_input = original_input_handler
        
        self.loop.widget = overlay
        self.loop.unhandled_input = handle_dialog_input
    
    def show_clear_all_dialog(self):
        """Show confirmation dialog to clear all selections and cancel downloads."""
        selection_count = len(self.selected_items)
        download_count = len(self.downloaded_items) if self.download_manager else 0
        
        # Build dialog content
        content = [
            urwid.Text(('error', "Clear All Selections?")),
            urwid.Divider(),
        ]
        
        if selection_count > 0:
            content.append(urwid.Text(f"Selected items: {selection_count}"))
        
        if download_count > 0:
            content.append(urwid.Text(f"Queued/Active downloads: {download_count}"))
            content.append(urwid.Divider())
            content.append(urwid.Text(('warning', "This will cancel all active downloads!")))
        
        content.extend([
            urwid.Divider(),
            urwid.Text("Press 'Y' to confirm, any other key to cancel")
        ])
        
        dialog = urwid.LineBox(urwid.Pile(content))
        
        overlay = urwid.Overlay(
            dialog,
            self.main_frame,
            align='center',
            width=60,
            valign='middle',
            height=len(content) + 4
        )
        
        original_input_handler = self.loop.unhandled_input
        
        def handle_dialog_input(key):
            if key in ('y', 'Y'):
                # Clear all selections
                self.selected_items.clear()
                self.downloaded_items.clear()
                
                # Stop and reset download manager
                if self.download_manager:
                    self.download_manager.stop()
                    self.download_manager = None
                    self.target_directory = None
                
                # Update display
                self.update_menu()
                self.update_header()
                self.update_download_panel()
                
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
            else:
                # Cancel - just close dialog
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
        
        self.loop.widget = overlay
        self.loop.unhandled_input = handle_dialog_input
    
    def show_failed_verifications(self):
        """Show dialog with failed hash verifications."""
        failed = self.download_manager.get_failed_verifications()
        
        if not failed:
            return
        
        # Build dialog content
        content = [
            urwid.Text(('error', "Hash Verification Failed")),
            urwid.Divider(),
            urwid.Text("The following files failed verification:"),
            urwid.Divider(),
        ]
        
        for filepath, message in failed:
            filename = os.path.basename(filepath)
            content.append(urwid.Text([('error', "✗ "), filename]))
        
        content.extend([
            urwid.Divider(),
            urwid.Text("Press 'd' to delete all failed files"),
            urwid.Text("Press 'k' to keep files"),
        ])
        
        dialog = urwid.LineBox(urwid.Pile(content))
        
        overlay = urwid.Overlay(
            dialog,
            self.main_frame,
            align='center',
            width=('relative', 80),
            valign='middle',
            height=('relative', 60)
        )
        
        original_input_handler = self.loop.unhandled_input
        
        def handle_dialog_input(key):
            if key in ('d', 'D'):
                deleted = self.download_manager.delete_failed_verifications()
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
                self.update_download_panel()
            elif key in ('k', 'K', 'esc'):
                self.loop.widget = self.main_frame
                self.loop.unhandled_input = original_input_handler
        
        self.loop.widget = overlay
        self.loop.unhandled_input = handle_dialog_input
    
    def cleanup(self):
        """Cleanup before exit."""
        if self.download_manager:
            # Stop downloads immediately without waiting
            # (joining the queue would block the UI)
            self.download_manager.stop()
    
    def run(self):
        """Run the UI."""
        try:
            self.loop.run()
        except Exception as e:
            # If we get an unhandled exception in the main loop,
            # try to show it in a dialog if possible
            try:
                self.show_error_dialog(
                    "Fatal Error",
                    "An unexpected error occurred in the application.",
                    f"Error: {e}\n\nThe application will now exit."
                )
                # Give user time to read the error
                import time
                time.sleep(3)
            except:
                # If even the error dialog fails, print to console
                print(f"\n\nFATAL ERROR: {e}")
                import traceback
                traceback.print_exc()
            raise
        finally:
            # Show summary after UI exits
            try:
                if self.download_manager:
                    status = self.download_manager.get_status()
            except:
                pass
                print("\n" + "=" * 80)
                print("Download Summary")
                print("=" * 80)
                
                if status['completed'] > 0:
                    print(f"✓ Successfully downloaded {status['completed']} file(s)")
                if status['failed'] > 0:
                    print(f"✗ Failed: {status['failed']} file(s)")
                
                # Check for hash verification failures
                failed_verifications = self.download_manager.get_failed_verifications()
                if failed_verifications:
                    print(f"\n⚠ {len(failed_verifications)} file(s) failed hash verification")
                
                print("=" * 80)


def run_urwid_ui(distro_dict):
    """Run the urwid-based UI."""
    ui = DistroGetUI(distro_dict)
    ui.run()

# ============================================================================
# Legacy Curses Menu (kept for reference, can be removed later)
# ============================================================================

# Curses menu
def curses_menu(stdscr, distro_dict):
    import time
    from config_manager import ConfigManager
    
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
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
    download_manager = None  # Will be initialized when target_directory is set
    downloaded_items = set()  # Track which items have been queued for download
    config_mgr = ConfigManager()  # For auto-deploy markers
    auto_deploy_items = set(config_mgr.get_auto_deploy_items())  # Load marked items

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
        
        # Calculate split screen dimensions
        left_width = int(width * 0.6)
        right_width = width - left_width - 1
        
        # Count selected ISOs (leaf nodes only)
        iso_count = sum(1 for path in selected_items if '/' in path and not any(other.startswith(path + '/') for other in selected_items))
        
        # Draw header
        dest_info = f" | Dest: {target_directory}" if target_directory else ""
        header = f"Navigate: ↑↓, Select: SPACE, Enter/→: Enter, ←/ESC: Back, /: Search, a: Auto-deploy, A: All, D: Set Dir, V: View failed, Q: Quit"
        stdscr.addstr(0, 0, header[:width-1])
        
        # Draw path/search line
        path_display = f"Path: {'/'.join(path_stack) if path_stack else 'root'} | Selected: {iso_count}{dest_info}"
        if search_mode and search_buffer:
            path_display += f" | Search: {search_buffer}"
        elif search_mode:
            path_display += " | Search: _"
        stdscr.addstr(1, 0, path_display[:width-1])
        
        # Draw left box border (menu)
        for y in range(2, height):
            stdscr.addch(y, left_width, '│')
        stdscr.addstr(2, 0, '┌' + '─' * (left_width - 1) + '┤')
        stdscr.addstr(2, 1, ' ISO Selection ')
        if height > 2:
            stdscr.addstr(height - 1, 0, '└' + '─' * (left_width - 1) + '┴')
        
        # Draw right box border (downloads)
        stdscr.addstr(2, left_width + 1, '┌' + '─' * (right_width - 3) + '┐')
        stdscr.addstr(2, left_width + 2, ' Downloads ')
        # Don't draw to the last character position to avoid curses error
        if height > 2 and width > left_width + 1:
            bottom_line = '└' + '─' * (right_width - 3) + '┘'
            # Don't write the last character if it's at the screen edge
            if left_width + 1 + len(bottom_line) >= width:
                bottom_line = bottom_line[:-1]
            stdscr.addstr(height - 1, left_width + 1, bottom_line)
        for y in range(3, height - 1):
            if width > 1:
                stdscr.addch(y, width - 1, '│')
        
        # Calculate visible area for left panel
        menu_height = height - 4  # Space for borders
        
        if not current_menu:
            stdscr.addstr(3, 1, "No items available."[:left_width-2])
        else:
            # Adjust scroll offset to keep current row visible
            if current_row < scroll_offset:
                scroll_offset = current_row
            elif current_row >= scroll_offset + menu_height:
                scroll_offset = current_row - menu_height + 1
            
            # Display visible items in left panel
            for idx in range(scroll_offset, min(scroll_offset + menu_height, len(current_menu))):
                item = current_menu[idx]
                item_path = "/".join(path_stack + [item])
                
                # Check if auto-deploy marked
                auto_mark = "[a]" if item_path in auto_deploy_items else "   "
                
                # Determine checkbox state
                if item_path in selected_items:
                    prefix = "[x]"
                elif path_stack == []:  # Top-level distro
                    # Check if any child items are selected
                    has_selected = any(sel.startswith(item + "/") for sel in selected_items)
                    prefix = "[o]" if has_selected else "[ ]"
                else:
                    prefix = "[ ]"
                
                display_line = f"{auto_mark}{prefix} {item}"[:left_width-2]
                screen_row = idx - scroll_offset + 3
                
                if idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(screen_row, 1, display_line + ' ' * (left_width - 2 - len(display_line)))
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(screen_row, 1, display_line)
        
        # Draw download status in right panel
        download_y = 3
        if download_manager:
            status = download_manager.get_status()
            
            # If remote, split right panel into two sections
            if status['is_remote']:
                # Draw separator for downloads section
                sep_y = 3 + (height - 6) // 2
                stdscr.addstr(sep_y, left_width + 1, '├' + '─' * (right_width - 3) + '┤')
                stdscr.addstr(sep_y, left_width + 2, ' SCP Transfer ')
                
                # Downloads section (top half)
                summary = f"Total: {iso_count} | Done: {status['completed']}"
                stdscr.addstr(download_y, left_width + 2, summary[:right_width-3])
                download_y += 1
                
                if status['queued'] > 0:
                    queued_line = f"Queued: {status['queued']}"
                    stdscr.addstr(download_y, left_width + 2, queued_line[:right_width-3])
                    download_y += 1
                
                # Show active downloads (compact)
                active_items = list(status['active'].items())
                if active_items and download_y < sep_y - 1:
                    for url, info in active_items[:sep_y - download_y - 1]:
                        filename = info['filename'][:right_width-10]
                        progress = info['progress']
                        total = info['total']
                        
                        if total > 0:
                            pct = int(100 * progress / total)
                            stdscr.attron(curses.color_pair(3))
                            stdscr.addstr(download_y, left_width + 2, f"⬇ {filename} {pct}%"[:right_width-3])
                            stdscr.attroff(curses.color_pair(3))
                        else:
                            stdscr.attron(curses.color_pair(3))
                            stdscr.addstr(download_y, left_width + 2, f"⬇ {filename}..."[:right_width-3])
                            stdscr.attroff(curses.color_pair(3))
                        download_y += 1
                
                # SCP Transfer section (bottom half)
                scp_y = sep_y + 1
                transfer_status = status.get('transfer_status', 'pending')
                
                if transfer_status == 'pending':
                    if status['downloaded_files']:
                        verified_count = sum(1 for f in status['downloaded_files'] 
                                           if status.get('hash_verification', {}).get(f, (None,))[0] is True)
                        failed_count = sum(1 for f in status['downloaded_files']
                                         if status.get('hash_verification', {}).get(f, (None,))[0] is False)
                        
                        ready_text = f"Ready: {len(status['downloaded_files'])} file(s)"
                        if verified_count > 0 or failed_count > 0:
                            ready_text += f" (✓{verified_count}"
                            if failed_count > 0:
                                ready_text += f" ✗{failed_count}"
                            ready_text += ")"
                        stdscr.addstr(scp_y, left_width + 2, ready_text[:right_width-3])
                        scp_y += 1
                        
                        # Show downloaded files waiting for transfer with verification status
                        for filepath in status['downloaded_files'][:height - scp_y - 2]:
                            filename = os.path.basename(filepath)[:right_width-8]
                            verification = status.get('hash_verification', {}).get(filepath, (None, ''))
                            
                            if verification[0] is True:
                                # Verified successfully - green checkmark
                                stdscr.attron(curses.color_pair(2))
                                stdscr.addstr(scp_y, left_width + 2, f"✓ {filename}"[:right_width-3])
                                stdscr.attroff(curses.color_pair(2))
                            elif verification[0] is False:
                                # Verification failed - red X
                                stdscr.attron(curses.color_pair(4))
                                stdscr.addstr(scp_y, left_width + 2, f"✗ {filename}"[:right_width-3])
                                stdscr.attroff(curses.color_pair(4))
                            else:
                                # No verification available - regular checkmark
                                stdscr.attron(curses.color_pair(2))
                                stdscr.addstr(scp_y, left_width + 2, f"• {filename}"[:right_width-3])
                                stdscr.attroff(curses.color_pair(2))
                            scp_y += 1
                    else:
                        stdscr.addstr(scp_y, left_width + 2, "Waiting..."[:right_width-3])
                elif transfer_status == 'transferring':
                    stdscr.attron(curses.color_pair(3))
                    stdscr.addstr(scp_y, left_width + 2, "Transferring to remote..."[:right_width-3])
                    stdscr.attroff(curses.color_pair(3))
                    scp_y += 1
                    # Show files being transferred
                    for filepath in status['downloaded_files'][:height - scp_y - 2]:
                        filename = os.path.basename(filepath)[:right_width-5]
                        stdscr.addstr(scp_y, left_width + 2, f"→ {filename}"[:right_width-3])
                        scp_y += 1
                elif transfer_status == 'completed':
                    stdscr.attron(curses.color_pair(2))
                    stdscr.addstr(scp_y, left_width + 2, "✓ Transfer complete!"[:right_width-3])
                    stdscr.attroff(curses.color_pair(2))
                elif transfer_status == 'failed':
                    stdscr.attron(curses.color_pair(4))
                    stdscr.addstr(scp_y, left_width + 2, "✗ Transfer failed"[:right_width-3])
                    stdscr.attroff(curses.color_pair(4))
            else:
                # Local download - original layout
                summary = f"Total: {iso_count} | Done: {status['completed']}"
                stdscr.addstr(download_y, left_width + 2, summary[:right_width-3])
                download_y += 1
                
                if status['queued'] > 0:
                    queued_line = f"Queued: {status['queued']}"
                    stdscr.addstr(download_y, left_width + 2, queued_line[:right_width-3])
                    download_y += 1
            
            if status['failed'] > 0:
                stdscr.attron(curses.color_pair(4))
                failed_line = f"Failed: {status['failed']}"
                stdscr.addstr(download_y, left_width + 2, failed_line[:right_width-3])
                stdscr.attroff(curses.color_pair(4))
                download_y += 1
            
            download_y += 1
            
            # Show active downloads
            active_items = list(status['active'].items())
            if active_items:
                stdscr.addstr(download_y, left_width + 2, "Active downloads:"[:right_width-3])
                download_y += 1
                
                for url, info in active_items[:menu_height - 10]:
                    filename = info['filename'][:right_width-5]
                    progress = info['progress']
                    total = info['total']
                    
                    if total > 0:
                        pct = int(100 * progress / total)
                        bar_width = min(right_width - 8, 20)
                        filled = int(bar_width * progress / total)
                        bar = '█' * filled + '░' * (bar_width - filled)
                        
                        stdscr.attron(curses.color_pair(3))
                        stdscr.addstr(download_y, left_width + 2, filename[:right_width-3])
                        stdscr.attroff(curses.color_pair(3))
                        download_y += 1
                        
                        progress_line = f"{bar} {pct}%"
                        stdscr.addstr(download_y, left_width + 2, progress_line[:right_width-3])
                        download_y += 1
                    else:
                        stdscr.attron(curses.color_pair(3))
                        stdscr.addstr(download_y, left_width + 2, filename[:right_width-3])
                        stdscr.attroff(curses.color_pair(3))
                        download_y += 1
                        stdscr.addstr(download_y, left_width + 2, "Starting..."[:right_width-3])
                        download_y += 1
            
            # Show list of all downloaded/queued items
            if download_y < height - 3:
                download_y += 1
                if downloaded_items:
                    stdscr.addstr(download_y, left_width + 2, "Download queue:"[:right_width-3])
                    download_y += 1
                    
                    for url in list(downloaded_items)[:menu_height - download_y]:
                        filename = url.split('/')[-1][:right_width-5]
                        retry_count = status.get('retry_counts', {}).get(url, 0)
                        
                        # Check status
                        if url in status['active']:
                            marker = "⬇"
                            color = 3  # Yellow
                        elif url in status.get('completed_urls', set()):
                            marker = "✓"
                            color = 2  # Green
                        elif retry_count > 0:
                            # Show retry attempt with red indicators
                            marker = "●" * retry_count
                            color = 4  # Red
                        else:
                            marker = "⋯"
                            color = 0  # Normal
                        
                        if color > 0:
                            stdscr.attron(curses.color_pair(color))
                        stdscr.addstr(download_y, left_width + 2, f"{marker} {filename}"[:right_width-3])
                        if color > 0:
                            stdscr.attroff(curses.color_pair(color))
                        download_y += 1
                        
                        if download_y >= height - 2:
                            break
        else:
            stdscr.addstr(download_y, left_width + 2, "Set target dir (D)"[:right_width-3])
            download_y += 1
            stdscr.addstr(download_y, left_width + 2, "to start downloads"[:right_width-3])
        
        stdscr.timeout(100)  # 100ms timeout for getch to allow search timeout checking
        key = stdscr.getch()
        
        if key == -1:  # No key pressed (timeout)
            # Redraw if downloads are active to update progress
            if download_manager:
                status = download_manager.get_status()
                needs_redraw = len(status['active']) > 0
            else:
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
                # If download manager is active, queue download immediately
                if download_manager:
                    # Check if we're selecting a direct URL item (list entry)
                    selected_item = current_menu[current_row]
                    if isinstance(current_menu, list) and ": " in selected_item and "://" in selected_item:
                        # Extract URL directly from the list item
                        url_start = selected_item.find(": http")
                        if url_start == -1:
                            url_start = selected_item.find(": ftp")
                        if url_start != -1:
                            url = selected_item[url_start + 2:]  # Skip ": "
                            if url not in downloaded_items:
                                download_manager.add_download(url)
                                downloaded_items.add(url)
                    else:
                        # Navigate through dict structure
                        urls = extract_urls_for_path(distro_dict, item_path)
                        for url in urls:
                            if url not in downloaded_items:
                                download_manager.add_download(url)
                                downloaded_items.add(url)
        elif key == ord('a'):
            # Toggle auto-deploy mark for current item
            item_path = "/".join(path_stack + [current_menu[current_row]])
            # Only allow marking leaf nodes (actual ISOs)
            if '/' in item_path:  # Not a top-level category
                current_node = distro_dict
                for part in item_path.split('/'):
                    if isinstance(current_node, dict) and part in current_node:
                        current_node = current_node[part]
                    else:
                        break
                
                # Check if it's a leaf (list of URLs)
                if isinstance(current_node, list):
                    is_marked = config_mgr.toggle_auto_deploy_item(item_path)
                    if is_marked:
                        auto_deploy_items.add(item_path)
                    else:
                        auto_deploy_items.discard(item_path)
                    needs_redraw = True
        elif key in [ord('A')]:
            # Select all items in current menu
            for item in current_menu:
                item_path = "/".join(path_stack + [item])
                selected_items.add(item_path)
        elif key in [ord('d'), ord('D')]:
            # Set target directory - show popup selector
            selected_location = show_location_popup(stdscr)
            
            if selected_location is False:
                # User cancelled
                continue
            elif selected_location is None:
                # User wants to enter new location
                curses.endwin()
                target_directory = input("\nEnter target directory (or hostname:/path for remote): ").strip()
                # Expand ~ and environment variables for local paths
                if target_directory and ':' not in target_directory:
                    import os
                    target_directory = os.path.expandvars(os.path.expanduser(target_directory))
            else:
                # User selected from history
                target_directory = selected_location
            
            # Initialize download manager if directory was set
            if target_directory and not download_manager:
                # Save to history
                add_to_location_history(target_directory)
                
                is_remote = ':' in target_directory and not target_directory.startswith('/')
                
                if is_remote:
                    remote_host, remote_path = target_directory.split(':', 1)
                    ssh_password = None
                    
                    # Create a transfer manager to test connection
                    import shutil
                    transfer_mgr = TransferManager(remote_host, remote_path, ssh_password)
                    
                    # Test SSH connection (non-interactive, quick test)
                    if not transfer_mgr.test_connection():
                        # SSH keys not set up, need password - retry loop
                        max_password_attempts = 3
                        password_attempt = 0
                        auth_success = False
                        
                        while password_attempt < max_password_attempts and not auth_success:
                            password_attempt += 1
                            prompt = f"Password for {remote_host}:"
                            if password_attempt > 1:
                                prompt = f"Authentication failed. Try again ({password_attempt}/{max_password_attempts}):"
                            
                            ssh_password = show_password_popup(stdscr, prompt)
                            
                            if ssh_password is None:
                                # User cancelled password entry
                                stdscr = curses.initscr()
                                curses.curs_set(0)
                                curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
                                curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
                                curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
                                curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
                                target_directory = None
                                break
                            
                            # Check if sshpass is available
                            if not shutil.which('sshpass'):
                                curses.endwin()
                                print("\n✗ sshpass not found. Install it for password authentication:")
                                print("  Fedora/RHEL: sudo dnf install sshpass")
                                print("  Debian/Ubuntu: sudo apt install sshpass")
                                print("\nOr set up SSH keys for password-free access:")
                                print(f"  ssh-copy-id {remote_host}")
                                print("\nPress Enter to continue...")
                                input()
                                stdscr = curses.initscr()
                                curses.curs_set(0)
                                curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
                                curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
                                curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
                                curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
                                target_directory = None
                                break
                            
                            # Test connection with password
                            transfer_mgr.ssh_password = ssh_password
                            if transfer_mgr.test_connection_with_password():
                                auth_success = True
                            else:
                                # Authentication failed, clear password and retry
                                ssh_password = None
                                transfer_mgr.ssh_password = None
                        
                        # If authentication failed after all attempts, abort
                        if not auth_success:
                            if target_directory:  # Only show error if user didn't cancel
                                curses.endwin()
                                print("\n✗ SSH authentication failed after multiple attempts")
                                print("Press Enter to continue...")
                                input()
                                stdscr = curses.initscr()
                                curses.curs_set(0)
                                curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
                                curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
                                curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
                                curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
                            target_directory = None
                            continue
                    
                    if target_directory:
                        # Create remote directory
                        if not transfer_mgr.create_remote_directory():
                            curses.endwin()
                            print("\n✗ Could not create remote directory")
                            print("Press Enter to continue...")
                            input()
                            stdscr = curses.initscr()
                            curses.curs_set(0)
                            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
                            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
                            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
                            curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
                            target_directory = None
                            continue
                        
                        download_manager = CombinedDownloadTransferManager(
                            remote_host, remote_path, ssh_password=ssh_password)
                else:
                    Path(target_directory).mkdir(parents=True, exist_ok=True)
                    download_manager = DownloadManager(target_directory)
                
                if download_manager:
                    download_manager.start()
                    
                    # Queue any already-selected items for download
                    for item_path in selected_items:
                        # Check if this is a direct list item (contains URL)
                        # URLs contain "://", so if the path contains it, extract the URL part
                        if "://" in item_path:
                            # Find where the URL starts (after ": ")
                            url_start = item_path.find(": http")
                            if url_start == -1:
                                url_start = item_path.find(": ftp")
                            if url_start != -1:
                                url = item_path[url_start + 2:]  # Skip ": "
                                if url not in downloaded_items:
                                    download_manager.add_download(url)
                                    downloaded_items.add(url)
                                continue
                        
                        # Otherwise, extract URLs from path
                        urls = extract_urls_for_path(distro_dict, item_path)
                        for url in urls:
                            if url not in downloaded_items:
                                download_manager.add_download(url)
                                downloaded_items.add(url)
            
            stdscr = curses.initscr()
            curses.curs_set(0)
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
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
        elif key in [ord('v'), ord('V')]:
            # View and handle failed hash verifications
            if download_manager:
                show_failed_verification_popup(stdscr, download_manager)
                needs_redraw = True
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
    
    # Stop download manager if it was started
    if download_manager:
        # Check if it's a combined manager (remote) or regular manager (local)
        if isinstance(download_manager, CombinedDownloadTransferManager):
            if not download_manager.wait_and_transfer():
                print("\n✗ Failed to transfer files to remote host")
                print("Files are available locally for manual transfer")
        else:
            # Local downloads - just wait for completion
            download_manager.download_queue.join()
            download_manager.stop()
            
            # Show download summary
            status = download_manager.get_status()
            completed_count = status['completed']
            failed_count = status['failed']
            
            print("\n" + "=" * 80)
            print("Download Summary")
            print("=" * 80)
            
            if completed_count > 0:
                print(f"✓ Successfully downloaded {completed_count} file(s) to:")
                print(f"  {target_directory}")
                print()
                
                # List downloaded files
                for filepath in status['downloaded_files']:
                    filename = os.path.basename(filepath)
                    size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    print(f"  • {filename} ({format_size(size)})")
            
            if failed_count > 0:
                print(f"\n✗ Failed to download {failed_count} file(s)")
            
            if completed_count == 0 and failed_count == 0:
                print("No files were downloaded (all may already exist)")
            
            print("=" * 80)
            
            # Check for hash verification failures
            failed_verifications = download_manager.get_failed_verifications()
            if failed_verifications:
                print("\n" + "=" * 80)
                print("Hash Verification Failed")
                print("=" * 80)
                print(f"\n⚠ {len(failed_verifications)} file(s) failed hash verification:")
                print("These files may be corrupted or incomplete.\n")
                
                for filepath, message in failed_verifications:
                    filename = os.path.basename(filepath)
                    print(f"  ✗ {filename}")
                    print(f"    {message}")
                
                print("\n" + "-" * 80)
                response = input("Delete all failed files? [y/N]: ").strip().lower()
                
                if response in ['y', 'yes']:
                    deleted = download_manager.delete_failed_verifications()
                    print(f"\n✓ Deleted {len(deleted)} file(s)")
                else:
                    print("\n⚠ Files kept (you may want to re-download them)")
                
                print("=" * 80)
            
            # Show detailed download log
            print("\n" + download_manager.get_download_log())
            
            # Save log to file
            log_file = download_manager.save_download_log()
            if log_file:
                print(f"\n📄 Download log saved to: {log_file}\n")
    
    return final_urls, target_directory

def deploy_to_proxmox_mode():
    """Interactive mode to deploy downloaded files to Proxmox storage."""
    import getpass
    from pathlib import Path
    
    print("=" * 80)
    print("Proxmox VE Deployment Tool")
    print("=" * 80)
    print()
    
    # Get Proxmox connection details
    hostname = input("Proxmox hostname or IP: ").strip()
    if not hostname:
        print("Hostname required")
        sys.exit(1)
    
    username = input(f"Username [{os.getenv('USER', 'root')}]: ").strip()
    if not username:
        username = os.getenv('USER', 'root')
    
    password = getpass.getpass(f"Password for {username}@{hostname}: ")
    
    # Create Proxmox connection
    print("\nConnecting to Proxmox...")
    pve = ProxmoxTarget(hostname, username, password)
    
    # Test connection
    success, message = pve.test_connection()
    if not success:
        print(f"✗ {message}")
        sys.exit(1)
    
    print(f"✓ {message}")
    
    # Discover storages
    print("\nDiscovering storages...")
    storages = pve.discover_storages()
    
    if not storages:
        print("✗ No storages found")
        sys.exit(1)
    
    print(f"✓ Found {len(storages)} storage(s)")
    
    # Get files to upload
    print("\nSelect files to upload:")
    print("  1. Upload files from a directory")
    print("  2. Upload specific file")
    
    choice = input("\nChoice (1-2): ").strip()
    
    files_to_upload = []
    
    if choice == '1':
        directory = input("Directory path: ").strip()
        if not os.path.isdir(directory):
            print(f"✗ Directory not found: {directory}")
            sys.exit(1)
        
        # Find all ISO, qcow2, img files
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.iso', '.qcow2', '.img', '.raw', '.tar.gz', '.tar.xz')):
                    files_to_upload.append(os.path.join(root, file))
        
        if not files_to_upload:
            print("✗ No ISO or cloud image files found in directory")
            sys.exit(1)
        
        print(f"\nFound {len(files_to_upload)} file(s):")
        for i, file in enumerate(files_to_upload, 1):
            size = os.path.getsize(file)
            print(f"  {i}. {os.path.basename(file)} ({format_size(size)})")
        
    elif choice == '2':
        filepath = input("File path: ").strip()
        if not os.path.isfile(filepath):
            print(f"✗ File not found: {filepath}")
            sys.exit(1)
        files_to_upload.append(filepath)
    else:
        print("Invalid choice")
        sys.exit(1)
    
    # Upload each file
    print()
    for i, filepath in enumerate(files_to_upload, 1):
        filename = os.path.basename(filepath)
        file_type = detect_file_type(filename)
        
        print(f"\n[{i}/{len(files_to_upload)}] Uploading {filename}")
        print(f"  Detected type: {file_type}")
        
        # Select storage
        storage = select_storage_interactive(pve, file_type)
        if not storage:
            print("  Skipped")
            continue
        
        # Upload with progress
        def progress_callback(percent, name):
            print(f"\r  Progress: {percent}% ", end='', flush=True)
        
        success, message = pve.upload_file(filepath, storage, file_type, progress_callback)
        print()  # New line after progress
        
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ✗ {message}")
    
    print("\n" + "=" * 80)
    print("Deployment complete")
    print("=" * 80)


def format_size(bytes_size):
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def main():
    config = load_config()
    print("Fetching distros...")
    distro_dict = fetch_iso_list()
    
    # Use urwid UI instead of curses
    run_urwid_ui(distro_dict)
    
    sys.exit(0)

def update_only_mode():
    """Non-interactive update mode for CI/CD."""
    print("Updating distro versions in README.md...")
    
    file_path = Path('./README.md')
    if not file_path.exists():
        print("✗ README.md not found in current directory")
        sys.exit(1)
    
    # Read current content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    # Update auto-update status section at the top
    auto_update_section = "## Auto-Updated Distributions\n\n"
    auto_update_section += "The following distributions are automatically updated with the latest versions:\n\n"
    for distro_name in sorted(DISTRO_UPDATERS.keys()):
        auto_update_section += f"- ✓ {distro_name}\n"
    auto_update_section += f"\n*Last update check: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n\n"
    auto_update_section += "---\n\n"
    
    # Check if auto-update section exists
    if "## Auto-Updated Distributions" in content:
        # Update existing section
        import re
        pattern = r'## Auto-Updated Distributions.*?(?=\n##[^#]|\Z)'
        content = re.sub(pattern, auto_update_section.rstrip() + '\n\n', content, flags=re.DOTALL)
    else:
        # Add section after any leading comments/title but before first ## header
        import re
        match = re.search(r'^(.*?)(## [^#])', content, re.DOTALL)
        if match:
            content = match.group(1) + auto_update_section + match.group(2) + content[match.end():]
        else:
            # No headers found, add at the beginning
            content = auto_update_section + content
    
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
                    # Validate URLs
                    print("  Validating URLs...")
                    validated = 0
                    total = 0
                    
                    # Extract URLs from links structure
                    urls_to_check = []
                    if isinstance(links, dict):
                        for key, value in links.items():
                            if isinstance(value, list):
                                for url in value:
                                    if isinstance(url, str) and url.startswith('http'):
                                        urls_to_check.append(url)
                                    elif isinstance(url, str):
                                        # Extract URL from markdown format
                                        import re
                                        match = re.search(r'\(([^)]+)\)', url)
                                        if match:
                                            urls_to_check.append(match.group(1))
                    elif isinstance(links, list):
                        for link in links:
                            # Extract URL from markdown format
                            import re
                            match = re.search(r'\(([^)]+)\)', link)
                            if match:
                                urls_to_check.append(match.group(1))
                    
                    # Validate a sample of URLs (up to 3 to avoid too many requests)
                    sample_urls = urls_to_check[:min(3, len(urls_to_check))]
                    for url in sample_urls:
                        if validate_url(url):
                            validated += 1
                        total += 1
                    
                    if total > 0:
                        print(f"  Validated {validated}/{total} URLs (sample)")
                    
                    # Count links differently for hierarchical structures
                    if isinstance(links, dict):
                        total_links = sum(len(v) if isinstance(v, list) else sum(len(sv) for sv in v.values() if isinstance(sv, list)) 
                                        for v in links.values())
                        print(f"  Generated {total_links} download link(s)")
                    else:
                        print(f"  Generated {len(links)} download link(s)")
                    
                    # Add metadata: auto-update marker and timestamp
                    current_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                    content = updater_class.update_section(content, version, links, 
                                                          metadata={'auto_updated': True, 'last_updated': current_time})
                    
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
        print(f"\n✓ Updated: {', '.join(changes_made)}")
        sys.exit(0)
    else:
        print("\n✓ No changes needed")
        sys.exit(0)

if __name__ == "__main__":
    # Initialize logging (INFO level for debug, change to WARNING for production)
    log_file = setup_logging(log_level=logging.DEBUG)
    logger.info(f"distroget starting - log file: {log_file}")
    
    # Check for command-line flags
    if len(sys.argv) > 1:
        if sys.argv[1] == '--update-only':
            update_only_mode()
        elif sys.argv[1] == '--update-repo':
            update_repository()
        elif sys.argv[1] == '--deploy-to-proxmox':
            deploy_to_proxmox_mode()
        elif sys.argv[1] == '--configure':
            # Run configuration menu
            from configure import main_config_menu
            main_config_menu()
        elif sys.argv[1] == '--auto-update':
            # Run automatic update - remove --auto-update from argv so argparse works
            sys.argv.pop(1)  # Remove '--auto-update'
            from auto_update import main
            main()
        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("distroget - Linux ISO/Cloud Image Downloader and Proxmox Deployer")
            print()
            print("Usage:")
            print("  python3 distroget.py                      Interactive TUI mode")
            print("  python3 distroget.py --configure          Configure Proxmox and auto-update")
            print("  python3 distroget.py --auto-update        Run automatic updates (for cron)")
            print("  python3 distroget.py --auto-update --deploy-to-proxmox")
            print("                                            Auto-update + deploy to Proxmox")
            print("  python3 distroget.py --deploy-to-proxmox  Deploy local files to Proxmox")
            print("  python3 distroget.py --update-only        Update README.md versions (CI mode)")
            print("  python3 distroget.py --update-repo        Update GitHub repository")
            print("  python3 distroget.py --help               Show this help")
            print()
            print("Auto-Update Options:")
            print("  --deploy-to-proxmox       Deploy marked [a] items to Proxmox")
            print("  --no-deploy               Skip Proxmox deployment")
            print("  --download-dir DIR        Custom download directory")
            print("  --dry-run                 Show what would be done")
            print()
            print("Configuration:")
            print("  Run '--configure' to set up:")
            print("    • Proxmox VE server connection")
            print("    • Storage mappings (ISO, LXC, snippets)")
            print("    • Auto-update distribution selection")
            print("    • Auto-update download directory")
            print()
            print("TUI Keys:")
            print("  ↑↓        Navigate menu")
            print("  →/Enter   Expand category")
            print("  ←/ESC     Go back")
            print("  SPACE     Select/download item")
            print("  a         Toggle auto-deploy marker [a]")
            print("  A         Select all in current menu")
            print("  d         Set download directory")
            print("  q         Quit")
            print()
            print("Automation:")
            print("  Add to crontab for nightly updates and deployment:")
            print("    0 2 * * * cd /path/to/distroget && \\")
            print("              python3 distroget.py --auto-update --deploy-to-proxmox")
            print()
            print("  Or just updates without deployment:")
            print("    0 2 * * * python3 /path/to/distroget.py --auto-update --no-deploy")
            sys.exit(0)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    else:
        main()

