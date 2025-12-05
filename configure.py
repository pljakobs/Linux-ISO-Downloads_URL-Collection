#!/usr/bin/env python3
"""Interactive configuration menu for Proxmox and auto-update settings."""

import getpass
import sys
from config_manager import ConfigManager
from proxmox import ProxmoxTarget, select_storage_interactive
from updaters import DISTRO_UPDATERS


def configure_proxmox_menu():
    """Interactive menu to configure Proxmox settings."""
    config = ConfigManager()
    
    print("\n" + "=" * 70)
    print("Proxmox VE Configuration")
    print("=" * 70)
    
    # Get current settings
    pve_config = config.get_proxmox_config()
    current_host = pve_config.get('hostname', '')
    current_user = pve_config.get('username', 'root')
    
    # Get connection details
    print("\nProxmox Server Details:")
    hostname = input(f"Hostname or IP [{current_host or 'pve.local'}]: ").strip()
    if not hostname:
        hostname = current_host or 'pve.local'
    
    username = input(f"Username [{current_user}]: ").strip()
    if not username:
        username = current_user
    
    # Test connection with SSH keys first
    print("\nTesting connection...")
    pve = ProxmoxTarget(hostname, username)
    
    # Check if SSH keys are configured
    if pve.check_ssh_keys():
        print("✓ SSH keys configured - no password needed")
        success, message = True, "Connection successful (SSH keys)"
    else:
        print("⚠ SSH keys not configured")
        print("  For automated deployments (cron), set up SSH keys:")
        print(f"    ssh-copy-id {username}@{hostname}")
        print()
        
        # Prompt for password for testing
        password = getpass.getpass(f"Password for {username}@{hostname} (for testing): ")
        if not password:
            print("✗ Password required for testing")
            return False
        
        pve.password = password
        success, message = pve.test_connection(interactive=True)
    
    if not success:
        print(f"✗ {message}")
        print("Configuration not saved.")
        return False
    
    print(f"✓ {message}")
    
    # Discover storages
    print("\nDiscovering storages...")
    storages = pve.discover_storages()
    
    if not storages:
        print("✗ No storages found")
        return False
    
    print(f"✓ Found {len(storages)} storage(s)")
    
    # Configure storage mappings
    storage_mappings = {}
    
    print("\n" + "=" * 70)
    print("Storage Configuration")
    print("=" * 70)
    print("\nPlease select a storage for each content type.")
    print("These will be used for automatic deployments.")
    print()
    
    # ISO storage
    print("1. ISO Images (Regular ISOs and Cloud Images)")
    print("-" * 70)
    iso_storage = select_storage_interactive(pve, 'iso')
    if iso_storage:
        storage_mappings['iso'] = iso_storage
        print(f"✓ Selected: {iso_storage}")
    else:
        print("⚠ Skipped - no storage selected")
    
    print()
    
    # LXC template storage
    print("2. LXC Templates")
    print("-" * 70)
    vztmpl_storage = select_storage_interactive(pve, 'vztmpl')
    if vztmpl_storage:
        storage_mappings['vztmpl'] = vztmpl_storage
        print(f"✓ Selected: {vztmpl_storage}")
    else:
        print("⚠ Skipped - no storage selected")
    
    print()
    
    # Snippets storage
    print("3. Cloud-Init Snippets")
    print("-" * 70)
    snippets_storage = select_storage_interactive(pve, 'snippets')
    if snippets_storage:
        storage_mappings['snippets'] = snippets_storage
        print(f"✓ Selected: {snippets_storage}")
    else:
        print("⚠ Skipped - no storage selected")
    
    # Save configuration
    print("\n" + "=" * 70)
    print("Saving configuration...")
    config.set_proxmox_config(hostname, username, storage_mappings)
    print("✓ Configuration saved")
    
    print("\nProxmox configuration complete!")
    print("=" * 70)
    
    return True


def configure_auto_update_menu():
    """Interactive menu to configure auto-update settings."""
    config = ConfigManager()
    
    print("\n" + "=" * 70)
    print("Auto-Update Configuration")
    print("=" * 70)
    
    current_distros = config.get_auto_update_distros()
    
    print("\nSelect distributions to automatically update:")
    print("(These will be updated when running with --auto-update flag)")
    print()
    
    # Get all available distributions
    all_distros = sorted(DISTRO_UPDATERS.keys())
    
    # Build selection state
    selected = {distro: distro in current_distros for distro in all_distros}
    
    while True:
        print("\n" + "-" * 70)
        print("Available Distributions:")
        print("-" * 70)
        
        for i, distro in enumerate(all_distros, 1):
            marker = "✓" if selected[distro] else " "
            print(f"  {i:2d}. [{marker}] {distro}")
        
        print()
        print("Commands:")
        print("  <number>  - Toggle distribution")
        print("  all       - Select all")
        print("  none      - Deselect all")
        print("  cloud     - Select only cloud images")
        print("  iso       - Select only regular ISOs")
        print("  save      - Save and exit")
        print("  cancel    - Exit without saving")
        
        choice = input("\nChoice: ").strip().lower()
        
        if choice == 'save':
            # Save selections
            selected_distros = [d for d, s in selected.items() if s]
            config.set_auto_update_distros(selected_distros)
            
            # Ask about enabling auto-update
            if selected_distros:
                print(f"\n✓ {len(selected_distros)} distribution(s) selected for auto-update")
                
                current_enabled = config.is_auto_update_enabled()
                enable_choice = input(f"\nEnable auto-update? [{'Y' if current_enabled else 'y'}/{'n' if current_enabled else 'N'}]: ").strip().lower()
                
                if enable_choice in ['y', 'yes']:
                    config.set_auto_update_enabled(True)
                    print("✓ Auto-update enabled")
                elif enable_choice in ['n', 'no']:
                    config.set_auto_update_enabled(False)
                    print("✓ Auto-update disabled")
            else:
                config.set_auto_update_enabled(False)
                print("⚠ No distributions selected - auto-update disabled")
            
            print("\nConfiguration saved!")
            break
        
        elif choice == 'cancel':
            print("Configuration not saved")
            break
        
        elif choice == 'all':
            for distro in all_distros:
                selected[distro] = True
            print("✓ All distributions selected")
        
        elif choice == 'none':
            for distro in all_distros:
                selected[distro] = False
            print("✓ All distributions deselected")
        
        elif choice == 'cloud':
            for distro in all_distros:
                selected[distro] = 'Cloud' in distro
            print("✓ Cloud images selected")
        
        elif choice == 'iso':
            for distro in all_distros:
                selected[distro] = 'Cloud' not in distro
            print("✓ Regular ISOs selected")
        
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(all_distros):
                distro = all_distros[idx]
                selected[distro] = not selected[distro]
                state = "selected" if selected[distro] else "deselected"
                print(f"✓ {distro} {state}")
            else:
                print("✗ Invalid number")
        
        else:
            print("✗ Invalid choice")


def configure_download_directory():
    """Configure auto-update download directory."""
    config = ConfigManager()
    current_dir = config.get_auto_update_download_dir()
    
    print("\n" + "=" * 70)
    print("Configure Auto-Update Download Directory")
    print("=" * 70)
    print(f"\nCurrent directory: {current_dir}")
    print("\nThis directory will be used for automatic ISO/cloud image downloads.")
    print("The directory will be created if it doesn't exist.")
    print()
    
    new_dir = input(f"New download directory [{current_dir}]: ").strip()
    
    if not new_dir:
        print("✗ No changes made")
        return
    
    # Expand ~
    from pathlib import Path
    new_dir = str(Path(new_dir).expanduser())
    
    # Confirm
    print(f"\nNew download directory: {new_dir}")
    confirm = input("Save this setting? [Y/n]: ").strip().lower()
    
    if confirm in ['', 'y', 'yes']:
        config.set_auto_update_download_dir(new_dir)
        print(f"✓ Download directory configured: {new_dir}")
        
        # Create directory if it doesn't exist
        try:
            Path(new_dir).mkdir(parents=True, exist_ok=True)
            print(f"✓ Directory created/verified")
        except Exception as e:
            print(f"⚠ Warning: Could not create directory: {e}")
            print(f"  Directory will be created on first download")
    else:
        print("✗ Configuration cancelled")


def main_config_menu():
    """Main configuration menu."""
    config = ConfigManager()
    
    while True:
        print("\n" + "=" * 70)
        print("distroget - Configuration Menu")
        print("=" * 70)
        
        # Show current status
        pve_config = config.get_proxmox_config()
        pve_host = pve_config.get('hostname', 'Not configured')
        
        auto_distros = config.get_auto_update_distros()
        auto_enabled = config.is_auto_update_enabled()
        
        # Show better status
        if auto_enabled and len(auto_distros) > 0:
            auto_status = f"✓ Enabled ({len(auto_distros)} distros)"
        elif len(auto_distros) > 0:
            auto_status = f"⚠ Configured but disabled ({len(auto_distros)} distros)"
        else:
            auto_status = "✗ Not configured"
        
        download_dir = config.get_auto_update_download_dir()
        
        print("\nCurrent Settings:")
        print(f"  Proxmox Server:  {pve_host}")
        print(f"  Auto-Update:     {auto_status}")
        print(f"  Download Dir:    {download_dir}")
        
        print("\nOptions:")
        print("  1. Configure Proxmox VE connection and storage")
        print("  2. Configure auto-update distributions")
        print("  3. Configure auto-update download directory")
        print("  4. Toggle auto-update enabled/disabled")
        print("  5. Show full configuration")
        print("  6. Export configuration to file")
        print("  7. Import configuration from file")
        print("  8. Reset to defaults")
        print("  q. Quit")
        
        choice = input("\nChoice: ").strip().lower()
        
        if choice == '1':
            configure_proxmox_menu()
        
        elif choice == '2':
            configure_auto_update_menu()
        
        elif choice == '3':
            configure_download_directory()
        
        elif choice == '4':
            # Toggle auto-update enabled/disabled
            current = config.is_auto_update_enabled()
            config.set_auto_update_enabled(not current)
            new_state = "enabled" if not current else "disabled"
            print(f"✓ Auto-update {new_state}")
        
        elif choice == '5':
            print()
            config.show_config()
        
        elif choice == '6':
            filepath = input("Export to file: ").strip()
            if filepath:
                from pathlib import Path
                if config.export_config(Path(filepath)):
                    print(f"✓ Configuration exported to {filepath}")
                else:
                    print("✗ Export failed")
        
        elif choice == '7':
            filepath = input("Import from file: ").strip()
            if filepath:
                from pathlib import Path
                if config.import_config(Path(filepath)):
                    print(f"✓ Configuration imported from {filepath}")
                else:
                    print("✗ Import failed")
        
        elif choice == '8':
            confirm = input("Reset all settings to defaults? [y/N]: ").strip().lower()
            if confirm == 'y':
                config.reset()
                print("✓ Configuration reset to defaults")
        
        elif choice == 'q':
            print("Goodbye!")
            break
        
        else:
            print("✗ Invalid choice")


if __name__ == '__main__':
    try:
        main_config_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(0)
