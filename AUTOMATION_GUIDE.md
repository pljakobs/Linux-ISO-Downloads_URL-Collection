# Automatic Updates and Proxmox Integration Setup

This guide explains how to set up automated distribution updates and Proxmox deployment for distroget.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration Menu](#configuration-menu)
3. [Auto-Update Setup](#auto-update-setup)
4. [Cron Job Setup](#cron-job-setup)
5. [Advanced Configuration](#advanced-configuration)

## Quick Start

### 1. Run Configuration Menu

```bash
python3 distroget.py --configure
```

This interactive menu will guide you through:
- Configuring Proxmox VE connection
- Selecting default storages for different content types
- Choosing distributions for automatic updates

### 2. Configure Proxmox

From the configuration menu, select option `1`:

```
Proxmox hostname or IP: pve.local
Username [root]: root
Password: ********

Testing connection...
✓ Connection successful

Discovering storages...
✓ Found 3 storage(s)
```

### 3. Select Storage Mappings

The tool will prompt you to select storages for:

- **ISO Images** (Regular ISOs and Cloud Images)
- **LXC Templates** (Container templates)
- **Cloud-Init Snippets** (Configuration files)

Example:
```
1. ISO Images (Regular ISOs and Cloud Images)
----------------------------------------------------------------------
Available storages for iso:
----------------------------------------------------------------------
1. Install
   Type: dir
   Content: iso, vztmpl, snippets
   Space: 7.8 GB available

2. local-lvm
   Type: lvmthin
   Content: images, rootdir
   Space: 350 GB available

Select storage (1-2) or 'q' to quit: 1
✓ Selected: Install
```

### 4. Configure Auto-Update

From the configuration menu, select option `2`:

```
Select distributions to automatically update:
(These will be updated when running with --auto-update flag)

Available Distributions:
----------------------------------------------------------------------
   1. [ ] Alpine Linux
   2. [ ] Arch Linux
   3. [ ] Debian
   4. [ ] Debian Cloud
   5. [✓] Fedora
   6. [✓] Fedora Cloud
   7. [ ] FreeDOS
   ...

Commands:
  <number>  - Toggle distribution
  all       - Select all
  none      - Deselect all
  cloud     - Select only cloud images
  iso       - Select only regular ISOs
  save      - Save and exit
  cancel    - Exit without saving

Choice: cloud
✓ Cloud images selected

Choice: save
✓ 4 distribution(s) selected for auto-update

Enable auto-update? [y/N]: y
✓ Auto-update enabled
```

## Configuration Menu

### Main Menu Options

```
distroget - Configuration Menu
======================================================================

Current Settings:
  Proxmox Server:  pve.local
  Auto-Update:     4 distros

Options:
  1. Configure Proxmox VE connection and storage
  2. Configure auto-update distributions
  3. Show full configuration
  4. Export configuration to file
  5. Import configuration from file
  6. Reset to defaults
  q. Quit
```

### Configuration Files

Configuration is stored in:
```
~/.config/distroget/config.json
```

Example configuration:
```json
{
  "location_history": [
    "/home/user/Downloads"
  ],
  "proxmox": {
    "hostname": "pve.local",
    "username": "root",
    "use_password": true,
    "storage_mappings": {
      "iso": "Install",
      "vztmpl": "Install",
      "snippets": "Install"
    }
  },
  "auto_update": {
    "enabled": true,
    "distributions": [
      "Fedora Cloud",
      "Ubuntu Cloud",
      "Debian Cloud",
      "Rocky Linux Cloud"
    ]
  }
}
```

## Auto-Update Setup

### Manual Auto-Update

Run automatic updates manually:

```bash
python3 distroget.py --auto-update
```

Options:
```bash
# Custom download directory
python3 distroget.py --auto-update --download-dir ~/iso-updates

# Skip Proxmox deployment
python3 distroget.py --auto-update --no-deploy

# Dry run (show what would be updated)
python3 distroget.py --auto-update --dry-run
```

### What Auto-Update Does

1. **Check for Updates**: Queries each configured distribution for latest version
2. **Download Images**: Downloads new or updated images to specified directory
3. **Decompress**: Automatically decompresses .bz2, .gz, .zip files
4. **Deploy** (optional): Uploads to Proxmox storage if configured

### Auto-Update Output

```
================================================================================
Automatic Update - 2025-12-04 02:00:00
================================================================================

Updating 4 distribution(s):
  • Fedora Cloud
  • Ubuntu Cloud
  • Debian Cloud
  • Rocky Linux Cloud

================================================================================
Processing: Fedora Cloud
================================================================================
Checking for latest version...
✓ Found versions: 40, 39
Generating download links...
✓ Found 2 download(s)
  [1/2] Downloading Fedora-Cloud-Base-Generic.x86_64-40-1.14.qcow2...
    ✓ Downloaded (450.2 MB)
  [2/2] Downloading Fedora-Cloud-Base-Generic.x86_64-39-1.5.qcow2...
    ✓ Downloaded (445.8 MB)

Deploying to Proxmox...
  • Fedora-Cloud-Base-Generic.x86_64-40-1.14.qcow2 → Install (configured)

================================================================================
Update Summary
================================================================================

Distributions: 4 successful, 0 failed
Downloaded: 8 file(s)
Deployed: 8 file(s)
```

## Cron Job Setup

### For Automated Nightly Updates

1. **Set up SSH Key Authentication** (required for unattended deployment):

```bash
# On your machine
ssh-keygen -t ed25519 -f ~/.ssh/proxmox_deploy

# Copy to Proxmox
ssh-copy-id -i ~/.ssh/proxmox_deploy root@pve.local
```

2. **Edit Crontab**:

```bash
crontab -e
```

3. **Add Auto-Update Job**:

```cron
# Daily at 2 AM: Update and deploy cloud images
0 2 * * * /usr/bin/python3 /path/to/distroget.py --auto-update >> /var/log/distroget-auto.log 2>&1

# Weekly on Sunday at 3 AM: Update all configured distros
0 3 * * 0 /usr/bin/python3 /path/to/distroget.py --auto-update >> /var/log/distroget-weekly.log 2>&1
```

4. **Create Log Directory**:

```bash
sudo mkdir -p /var/log
sudo touch /var/log/distroget-auto.log
sudo chmod 644 /var/log/distroget-auto.log
```

### Cron Schedule Examples

```cron
# Every 6 hours
0 */6 * * * /usr/bin/python3 /path/to/distroget.py --auto-update

# Monday and Thursday at 4 AM
0 4 * * 1,4 /usr/bin/python3 /path/to/distroget.py --auto-update

# First day of month at 1 AM
0 1 1 * * /usr/bin/python3 /path/to/distroget.py --auto-update

# Weekdays at 11 PM
0 23 * * 1-5 /usr/bin/python3 /path/to/distroget.py --auto-update
```

### Email Notifications

To receive email notifications on failures:

```cron
MAILTO=admin@example.com
0 2 * * * /usr/bin/python3 /path/to/distroget.py --auto-update
```

### Custom Script Wrapper

Create `/usr/local/bin/distroget-auto-update.sh`:

```bash
#!/bin/bash

# Configuration
DISTROGET_PATH="/opt/distroget"
DOWNLOAD_DIR="/var/lib/distroget/downloads"
LOG_FILE="/var/log/distroget-auto.log"

# Run update
cd "$DISTROGET_PATH"
python3 distroget.py --auto-update --download-dir "$DOWNLOAD_DIR" >> "$LOG_FILE" 2>&1

# Check exit status
if [ $? -eq 0 ]; then
    echo "$(date): Auto-update successful" >> "$LOG_FILE"
else
    echo "$(date): Auto-update failed!" >> "$LOG_FILE"
    # Send notification (optional)
    # mail -s "distroget auto-update failed" admin@example.com < "$LOG_FILE"
fi
```

Make executable:
```bash
chmod +x /usr/local/bin/distroget-auto-update.sh
```

Add to cron:
```cron
0 2 * * * /usr/local/bin/distroget-auto-update.sh
```

## Advanced Configuration

### Command-Line Configuration

```bash
# Show current configuration
python3 config_manager.py show

# Export configuration
python3 config_manager.py export my-config.json

# Import configuration
python3 config_manager.py import my-config.json

# Reset to defaults
python3 config_manager.py reset
```

### Selective Updates

Temporarily override auto-update configuration:

```python
#!/usr/bin/env python3
from config_manager import ConfigManager

config = ConfigManager()

# Update only specific distros for this run
config.set_auto_update_distros(['Fedora Cloud', 'Ubuntu Cloud'])

# Run your update logic
# ...

# Restore original config
# (or just don't save, changes won't persist)
```

### Pre/Post Update Hooks

Create custom hooks by wrapping the auto-update:

```python
#!/usr/bin/env python3
from auto_update import auto_update_distributions
from pathlib import Path
import datetime

# Pre-update hook
print("Starting update at", datetime.datetime.now())
# ... custom logic ...

# Run update
download_dir = Path.home() / 'Downloads' / 'distroget-auto'
results = auto_update_distributions(download_dir, deploy_to_proxmox=True)

# Post-update hook
if results['status'] == 'success':
    print(f"Successfully updated {len(results['updates'])} distributions")
    # ... send notification, update database, etc. ...
else:
    print("Update failed!")
    # ... send alert ...
```

### Multiple Proxmox Servers

To manage multiple Proxmox servers, use different config files:

```bash
# Production
python3 distroget.py --auto-update --config ~/.config/distroget/prod-config.json

# Development
python3 distroget.py --auto-update --config ~/.config/distroget/dev-config.json
```

### Monitoring and Logging

Set up logrotate for distroget logs:

Create `/etc/logrotate.d/distroget`:
```
/var/log/distroget-*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
}
```

## Troubleshooting

### Auto-Update Not Running

1. Check cron service:
   ```bash
   sudo systemctl status cron  # or crond on RHEL
   ```

2. Check crontab syntax:
   ```bash
   crontab -l
   ```

3. Check logs:
   ```bash
   tail -f /var/log/distroget-auto.log
   grep CRON /var/log/syslog
   ```

### SSH Key Authentication

For cron jobs to deploy to Proxmox automatically, you need SSH keys:

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/distroget_deploy

# Add to Proxmox
ssh-copy-id -i ~/.ssh/distroget_deploy root@pve.local

# Test
ssh -i ~/.ssh/distroget_deploy root@pve.local pvesm status
```

### Permission Issues

Ensure download directory is writable:

```bash
mkdir -p ~/Downloads/distroget-auto
chmod 755 ~/Downloads/distroget-auto
```

### Disk Space

Monitor disk space to avoid failed downloads:

```bash
df -h ~/Downloads/distroget-auto
```

Add to cron before update:
```bash
# Check available space (need at least 10GB)
AVAIL=$(df ~/Downloads | tail -1 | awk '{print $4}')
if [ $AVAIL -lt 10485760 ]; then
    echo "Insufficient disk space"
    exit 1
fi
```

## See Also

- [Proxmox Deployment Documentation](PROXMOX_DEPLOYMENT.md)
- [Main README](README.md)
- [Cloud Images Guide](updaters.py)
