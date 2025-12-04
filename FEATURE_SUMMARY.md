# distroget - Complete Feature Summary

## Overview

distroget is a comprehensive Linux distribution ISO/cloud image downloader with integrated Proxmox VE deployment and automatic update capabilities.

## Core Features

### 1. Interactive TUI Browser
- Curses-based menu system for browsing distributions
- Hierarchical navigation (distros → versions → editions)
- Multi-selection with checkboxes
- Download progress tracking
- Location history with quick selection

### 2. Distribution Support

**Regular ISOs (14):**
- Alpine Linux
- Arch Linux  
- Debian (multiple desktop environments)
- EndeavourOS
- Fedora (Workstation, Server, Spins, Silverblue, Kinoite, CoreOS)
- FreeDOS
- Kali Linux
- Linux Mint
- MX Linux
- Manjaro
- Pop!_OS
- Ubuntu (multiple flavors)
- Zorin OS
- openSUSE (Leap, Tumbleweed)

**Cloud Images (4):**
- Debian Cloud (qcow2)
- Fedora Cloud (qcow2)
- Rocky Linux Cloud (qcow2)
- Ubuntu Cloud (img)

### 3. Download Management
- Parallel downloads with worker threads
- Resume support for interrupted downloads
- Progress tracking per file
- Automatic decompression (.bz2, .gz, .zip)
- Download queue management
- Configurable download locations

### 4. Remote Transfer
- SSH/SCP integration
- Password retry logic (3 attempts)
- Secure password handling (SSHPASS environment variable)
- Bulk transfer support
- Transfer progress tracking

### 5. Proxmox VE Integration

**Storage Discovery:**
- Automatic storage enumeration
- Content type detection (iso, vztmpl, snippets)
- Available space reporting
- Compatibility filtering

**Deployment:**
- Interactive storage selection
- Automatic file type detection
- Batch and single file upload
- Real-time progress with rsync
- Proper file placement:
  - ISOs → `template/iso/`
  - Cloud images → `template/iso/`
  - LXC templates → `template/cache/`
  - Snippets → `snippets/`

### 6. Configuration System

**ConfigManager:**
- JSON-based configuration storage
- Proxmox connection settings
- Storage mappings per content type
- Download location history
- Import/export functionality

**Settings Stored:**
```json
{
  "proxmox": {
    "hostname": "pve.local",
    "username": "root",
    "storage_mappings": {
      "iso": "Install",
      "vztmpl": "Install",
      "snippets": "Install"
    }
  },
  "auto_update": {
    "enabled": true,
    "distributions": [...]
  }
}
```

### 7. Automatic Updates

**Features:**
- Configurable distribution selection
- Scheduled updates via cron
- Version checking from official sources
- Automatic downloads
- Optional Proxmox deployment
- Email notifications (via cron)
- Dry-run mode

**Cron Integration:**
```bash
# Daily at 2 AM
0 2 * * * python3 /path/to/distroget.py --auto-update
```

### 8. Interactive Configuration Menu

**Menu Options:**
1. Configure Proxmox VE connection and storage
2. Configure auto-update distributions
3. Show full configuration
4. Export/import configuration
5. Reset to defaults

**Distribution Selection:**
- Toggle individual distributions
- Select all/none
- Filter by type (cloud/iso)
- Save preferences

## Command-Line Interface

### Usage Modes

```bash
# Interactive TUI
python3 distroget.py

# Configuration menu
python3 distroget.py --configure

# Automatic updates (for cron)
python3 distroget.py --auto-update [--no-deploy] [--dry-run]

# Manual deployment
python3 distroget.py --deploy-to-proxmox

# CI/CD mode (update README.md)
python3 distroget.py --update-only

# GitHub sync
python3 distroget.py --update-repo

# Help
python3 distroget.py --help
```

### Python API

```python
# Configuration
from config_manager import ConfigManager
config = ConfigManager()
config.set_proxmox_config('pve.local', 'root', {...})
config.set_auto_update_distros(['Fedora Cloud', 'Ubuntu Cloud'])

# Proxmox operations
from proxmox import ProxmoxTarget
pve = ProxmoxTarget('pve.local', 'root', 'password')
success, msg = pve.test_connection()
storages = pve.discover_storages()
pve.upload_file('ubuntu.iso', 'Install', 'iso')

# Downloads
from downloads import DownloadManager
dm = DownloadManager('/path/to/downloads')
dm.download_files([url1, url2, url3])

# Auto-update
from auto_update import auto_update_distributions
results = auto_update_distributions(download_dir, deploy_to_proxmox=True)
```

## Typical Workflows

### Workflow 1: Interactive Download & Deploy

```bash
# Step 1: Browse and download
python3 distroget.py
# → Select distributions from TUI
# → Download to local directory

# Step 2: Deploy to Proxmox
python3 distroget.py --deploy-to-proxmox
# → Enter Proxmox credentials
# → Select files
# → Choose storage
# → Upload with progress
```

### Workflow 2: First-Time Setup

```bash
# Step 1: Configure
python3 distroget.py --configure

# Step 2: Set up Proxmox
# → Enter hostname/IP
# → Test connection
# → Select storages for iso/vztmpl/snippets

# Step 3: Configure auto-update
# → Select distributions (e.g., cloud images only)
# → Enable auto-update

# Step 4: Test
python3 distroget.py --auto-update --dry-run

# Step 5: Add to cron
crontab -e
# Add: 0 2 * * * python3 /path/to/distroget.py --auto-update
```

### Workflow 3: Automated Cloud Image Updates

```bash
# Daily cron job
0 2 * * * python3 /opt/distroget/distroget.py --auto-update >> /var/log/distroget.log 2>&1
```

**What happens:**
1. Checks configured distributions for updates
2. Downloads new versions
3. Decompresses if needed
4. Uploads to Proxmox storage
5. Logs results

### Workflow 4: VM Template Creation

```bash
# Step 1: Auto-update downloads cloud image
# (Happens via cron)

# Step 2: Create VM template on Proxmox
ssh root@pve.local

# Import cloud image
qm create 9000 --name ubuntu-cloud-template --memory 2048 \
   --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci

qm set 9000 --scsi0 Install:0,import-from=/Install/template/iso/ubuntu-24.04-cloudimg.img

# Add cloud-init
qm set 9000 --ide2 Install:cloudinit
qm set 9000 --cicustom "user=Install:snippets/ansible-ready.yaml"
qm set 9000 --boot order=scsi0

# Convert to template
qm template 9000

# Step 3: Deploy from template (instant)
qm clone 9000 100 --name webserver1
qm set 100 --ipconfig0 ip=dhcp
qm start 100
# → VM ready in 30 seconds with Ansible SSH keys!
```

## File Structure

```
distroget_repo/
├── distroget.py           # Main TUI application
├── downloads.py           # Download manager
├── transfers.py           # SSH/SCP transfer manager
├── proxmox.py            # Proxmox VE integration
├── updaters.py           # Distribution scrapers (18 updaters)
├── config_manager.py     # Configuration management
├── configure.py          # Interactive configuration menu
├── auto_update.py        # Automatic update system
├── README.md             # Main documentation
├── PROXMOX_DEPLOYMENT.md # Proxmox deployment guide
├── AUTOMATION_GUIDE.md   # Cron and automation setup
└── FEATURE_SUMMARY.md    # This file

Config location:
~/.config/distroget/config.json
```

## Dependencies

**Required:**
- Python 3.6+
- requests
- curses (usually included)

**For Proxmox:**
- sshpass
- rsync
- openssh-client

**Install:**
```bash
# Debian/Ubuntu
sudo apt install python3 python3-requests sshpass rsync openssh-client

# Fedora/RHEL
sudo dnf install python3 python3-requests sshpass rsync openssh-clients

# Arch Linux
sudo pacman -S python python-requests sshpass rsync openssh
```

## Key Advantages

### vs Manual Downloads
- ✅ One interface for 18 distributions
- ✅ Always gets latest versions
- ✅ Automatic decompression
- ✅ Progress tracking
- ✅ Resume support

### vs Manual Proxmox Upload
- ✅ Storage discovery
- ✅ Automatic type detection
- ✅ Batch uploads
- ✅ Proper placement
- ✅ Progress tracking

### vs Manual VM Creation
- ✅ Cloud images boot in 30 seconds
- ✅ Pre-configured with cloud-init
- ✅ SSH keys pre-installed
- ✅ Ansible-ready immediately
- ✅ No interactive installer

### vs No Automation
- ✅ Cron-based updates
- ✅ Always have latest images
- ✅ Zero manual intervention
- ✅ Email notifications
- ✅ Logging and monitoring

## Performance

- **Download**: Parallel with configurable workers
- **Decompression**: Automatic, background-capable
- **Upload**: rsync with progress (typically 100+ MB/s LAN)
- **Auto-update**: Handles 4 distros in ~5-10 minutes (depending on mirrors)

## Security

- **Passwords**: SSHPASS environment variable (not process args)
- **SSH**: StrictHostKeyChecking configurable
- **Cron**: Supports SSH key authentication
- **Config**: Permissions 644, no password storage

## Future Enhancements

Potential additions:
- [ ] Torrent support for faster downloads
- [ ] Checksum verification (SHA256)
- [ ] Multi-Proxmox cluster support
- [ ] Web UI / REST API
- [ ] Docker container deployment
- [ ] Telegram/Slack notifications
- [ ] Metrics and dashboards

## Support

- **Repository**: https://github.com/pljakobs/Linux-ISO-Downloads_URL-Collection
- **Issues**: GitHub Issues
- **Documentation**: README.md, PROXMOX_DEPLOYMENT.md, AUTOMATION_GUIDE.md

## License

See repository for license information.

---

**distroget** - Download once, deploy everywhere, update automatically.
