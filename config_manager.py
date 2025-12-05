#!/usr/bin/env python3
"""Configuration manager for distroget with Proxmox settings."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class ConfigManager:
    """Manage distroget configuration including Proxmox settings."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to config file (default: ~/.config/distroget/config.json)
        """
        if config_path:
            self.config_path = Path(config_path) if not isinstance(config_path, Path) else config_path
        else:
            self.config_path = Path.home() / ".config" / "distroget" / "config.json"
        
        self.config = self.load()
    
    def load(self) -> Dict:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
        
        # Return default config
        return {
            'location_history': [],
            'proxmox': {
                'hostname': '',
                'username': 'root',
                # NOTE: Password is NEVER stored - use SSH keys or prompt at runtime
                'storage_mappings': {
                    'iso': '',
                    'vztmpl': '',
                    'snippets': ''
                }
            },
            'auto_update': {
                'enabled': False,
                'distributions': [],
                'download_dir': str(Path.home() / 'Downloads' / 'distroget-auto')
            },
            'auto_deploy_items': []  # List of item paths marked for auto-deploy
        }
    
    def save(self):
        """Save configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_proxmox_config(self) -> Dict:
        """Get Proxmox configuration."""
        return self.config.get('proxmox', {})
    
    def set_proxmox_config(self, hostname: str, username: str = 'root', 
                          storage_mappings: Optional[Dict] = None):
        """
        Set Proxmox configuration.
        
        Args:
            hostname: Proxmox hostname or IP
            username: SSH username
            storage_mappings: Dict mapping content types to storage names
        """
        if 'proxmox' not in self.config:
            self.config['proxmox'] = {}
        
        self.config['proxmox']['hostname'] = hostname
        self.config['proxmox']['username'] = username
        
        if storage_mappings:
            self.config['proxmox']['storage_mappings'] = storage_mappings
        
        self.save()
    
    def get_storage_for_type(self, content_type: str) -> Optional[str]:
        """
        Get configured storage name for a content type.
        
        Args:
            content_type: 'iso', 'vztmpl', or 'snippets'
            
        Returns:
            Storage name or None
        """
        mappings = self.config.get('proxmox', {}).get('storage_mappings', {})
        return mappings.get(content_type)
    
    def get_auto_update_distros(self) -> List[str]:
        """Get list of distributions marked for automatic updates."""
        return self.config.get('auto_update', {}).get('distributions', [])
    
    def set_auto_update_distros(self, distros: List[str]):
        """
        Set distributions for automatic updates.
        
        Args:
            distros: List of distribution names to auto-update
        """
        if 'auto_update' not in self.config:
            self.config['auto_update'] = {'enabled': False, 'distributions': []}
        
        self.config['auto_update']['distributions'] = distros
        self.save()
    
    def is_auto_update_enabled(self) -> bool:
        """Check if auto-update is enabled."""
        return self.config.get('auto_update', {}).get('enabled', False)
    
    def get_auto_update_download_dir(self) -> str:
        """Get auto-update download directory."""
        import os
        default = str(Path.home() / 'Downloads' / 'distroget-auto')
        path = self.config.get('auto_update', {}).get('download_dir', default)
        # Expand ~ and environment variables like $HOME
        return os.path.expandvars(os.path.expanduser(path))
    
    def set_auto_update_download_dir(self, download_dir: str):
        """Set auto-update download directory."""
        import os
        if 'auto_update' not in self.config:
            self.config['auto_update'] = {}
        # Expand ~ and environment variables like $HOME
        expanded_dir = os.path.expandvars(os.path.expanduser(download_dir))
        self.config['auto_update']['download_dir'] = expanded_dir
        self.save()
    
    def set_auto_update_enabled(self, enabled: bool):
        """Enable or disable auto-update."""
        if 'auto_update' not in self.config:
            self.config['auto_update'] = {'enabled': False, 'distributions': []}
        
        self.config['auto_update']['enabled'] = enabled
        self.save()
    
    def toggle_distro_auto_update(self, distro_name: str) -> bool:
        """
        Toggle auto-update for a specific distribution.
        
        Args:
            distro_name: Name of the distribution
            
        Returns:
            New state (True if now enabled, False if disabled)
        """
        distros = self.get_auto_update_distros()
        
        if distro_name in distros:
            distros.remove(distro_name)
            enabled = False
        else:
            distros.append(distro_name)
            enabled = True
        
        self.set_auto_update_distros(distros)
        return enabled
    
    def get_auto_deploy_items(self) -> List[str]:
        """Get list of item paths marked for auto-deploy."""
        return self.config.get('auto_deploy_items', [])
    
    def toggle_auto_deploy_item(self, item_path: str) -> bool:
        """Toggle auto-deploy for a specific item path.
        
        Args:
            item_path: Full path to the item (e.g., 'Fedora/Fedora Cloud/40')
            
        Returns:
            New state (True if now marked, False if unmarked)
        """
        items = self.get_auto_deploy_items()
        
        if item_path in items:
            items.remove(item_path)
            marked = False
        else:
            items.append(item_path)
            marked = True
        
        self.config['auto_deploy_items'] = items
        self.save()
        return marked
    
    def is_auto_deploy_item(self, item_path: str) -> bool:
        """Check if an item is marked for auto-deploy."""
        return item_path in self.get_auto_deploy_items()
    
    def add_to_location_history(self, location: str):
        """Add a location to download history."""
        history = self.config.get('location_history', [])
        
        if location in history:
            history.remove(location)
        
        history.insert(0, location)
        self.config['location_history'] = history[:10]
        self.save()
    
    def get_location_history(self) -> List[str]:
        """Get download location history."""
        return self.config.get('location_history', [])
    
    def export_config(self, path: Path) -> bool:
        """
        Export configuration to a file.
        
        Args:
            path: Path to export file
            
        Returns:
            True if successful
        """
        try:
            with open(path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False
    
    def import_config(self, path: Path) -> bool:
        """
        Import configuration from a file.
        
        Args:
            path: Path to import file
            
        Returns:
            True if successful
        """
        try:
            with open(path, 'r') as f:
                imported = json.load(f)
            
            # Merge with existing config
            self.config.update(imported)
            self.save()
            return True
        except Exception as e:
            print(f"Error importing config: {e}")
            return False
    
    def reset(self):
        """Reset configuration to defaults."""
        self.config = {
            'location_history': [],
            'proxmox': {
                'hostname': '',
                'username': 'root',
                'use_password': True,
                'storage_mappings': {
                    'iso': '',
                    'vztmpl': '',
                    'snippets': ''
                }
            },
            'auto_update': {
                'enabled': False,
                'distributions': []
            }
        }
        self.save()
    
    def show_config(self):
        """Print current configuration."""
        print("Current Configuration:")
        print("=" * 70)
        
        # Proxmox settings
        pve = self.config.get('proxmox', {})
        print("\nProxmox VE Settings:")
        print(f"  Hostname: {pve.get('hostname', 'Not configured')}")
        print(f"  Username: {pve.get('username', 'root')}")
        
        mappings = pve.get('storage_mappings', {})
        print("  Storage Mappings:")
        print(f"    ISO Images:    {mappings.get('iso', 'Not configured')}")
        print(f"    LXC Templates: {mappings.get('vztmpl', 'Not configured')}")
        print(f"    Snippets:      {mappings.get('snippets', 'Not configured')}")
        
        # Auto-update settings
        auto = self.config.get('auto_update', {})
        print("\nAuto-Update Settings:")
        print(f"  Enabled: {auto.get('enabled', False)}")
        distros = auto.get('distributions', [])
        if distros:
            print(f"  Distributions ({len(distros)}):")
            for distro in distros:
                print(f"    • {distro}")
        else:
            print("  Distributions: None")
        
        # Location history
        history = self.config.get('location_history', [])
        if history:
            print(f"\nDownload History ({len(history)} locations):")
            for loc in history[:5]:
                print(f"  • {loc}")
        
        print("=" * 70)


if __name__ == '__main__':
    # Test configuration manager
    import sys
    
    config = ConfigManager()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'show':
            config.show_config()
        elif sys.argv[1] == 'reset':
            config.reset()
            print("Configuration reset to defaults")
        elif sys.argv[1] == 'export' and len(sys.argv) > 2:
            if config.export_config(Path(sys.argv[2])):
                print(f"Configuration exported to {sys.argv[2]}")
        elif sys.argv[1] == 'import' and len(sys.argv) > 2:
            if config.import_config(Path(sys.argv[2])):
                print(f"Configuration imported from {sys.argv[2]}")
        else:
            print("Usage:")
            print("  python3 config_manager.py show")
            print("  python3 config_manager.py reset")
            print("  python3 config_manager.py export <file>")
            print("  python3 config_manager.py import <file>")
    else:
        config.show_config()
