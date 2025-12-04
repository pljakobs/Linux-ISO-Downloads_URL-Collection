# Proxmox VE Integration

The Proxmox deployment module allows you to automatically upload downloaded ISOs, cloud images, and LXC templates directly to your Proxmox VE storage.

## Features

- **Automatic Storage Discovery**: Scans your Proxmox server for available storages and their supported content types
- **Smart File Type Detection**: Automatically detects whether files are ISOs, cloud images, LXC templates, or cloud-init snippets
- **Interactive Storage Selection**: Shows only storages compatible with each file type
- **Secure Authentication**: Uses SSHPASS environment variable for password safety
- **Progress Tracking**: Real-time upload progress using rsync
- **Batch Upload**: Upload entire directories at once
- **Proper Placement**: Automatically places files in correct Proxmox directories:
  - ISOs → `/path/to/storage/template/iso/`
  - Cloud images (.qcow2, .img) → `/path/to/storage/template/iso/`
  - LXC templates → `/path/to/storage/template/cache/`
  - Cloud-init snippets → `/path/to/storage/snippets/`

## Prerequisites

Install required system packages:

```bash
# Debian/Ubuntu
sudo apt install sshpass rsync openssh-client

# Fedora/RHEL
sudo dnf install sshpass rsync openssh-clients

# Arch Linux
sudo pacman -S sshpass rsync openssh
```

## Usage

### Command Line

Deploy files to Proxmox interactively:

```bash
python3 distroget.py --deploy-to-proxmox
```

Test connection to Proxmox server:

```bash
python3 proxmox.py <hostname> [username]
```

### Interactive Workflow

1. **Run deployment command**:
   ```bash
   python3 distroget.py --deploy-to-proxmox
   ```

2. **Enter connection details**:
   - Hostname or IP of your Proxmox server
   - Username (default: root)
   - Password (secure input)

3. **Select upload method**:
   - Upload files from a directory (batch mode)
   - Upload a specific file

4. **Choose target storage**:
   - Tool automatically filters storages by compatibility
   - Shows available space for each storage

5. **Monitor progress**:
   - Real-time upload progress for each file
   - Success/failure status

### Python API

```python
from proxmox import ProxmoxTarget

# Create connection
pve = ProxmoxTarget('pve.local', 'root', 'your_password')

# Test connection
success, message = pve.test_connection()
if success:
    print("Connected successfully!")

# Discover available storages
storages = pve.discover_storages()
for storage in storages:
    print(f"{storage['name']}: {storage['type']} - {', '.join(storage['content'])}")

# Upload a file
def progress(percent, filename):
    print(f"Uploading {filename}: {percent}%")

success, message = pve.upload_file(
    local_path='/path/to/ubuntu-22.04.iso',
    storage_name='Install',
    content_type='iso',
    progress_callback=progress
)

# List files in storage
files = pve.list_files('Install', 'iso')
print(f"ISOs in Install storage: {', '.join(files)}")
```

## Storage Content Types

Proxmox supports different content types for each storage:

| Content Type | File Extensions | Proxmox Directory |
|--------------|-----------------|-------------------|
| `iso` | .iso, .qcow2, .img, .raw | template/iso/ |
| `vztmpl` | .tar.gz, .tar.xz, .tar.zst | template/cache/ |
| `snippets` | .yaml, .yml | snippets/ |

The module automatically detects file types and places them in the correct directory.

## Example: Complete Workflow

### 1. Download Cloud Images

```bash
# Run distroget TUI
python3 distroget.py

# Navigate to "Ubuntu Cloud" and download
# Files saved to: ~/Downloads/distroget/
```

### 2. Deploy to Proxmox

```bash
# Start deployment wizard
python3 distroget.py --deploy-to-proxmox

# Example interaction:
Proxmox hostname or IP: 192.168.1.100
Username [root]: root
Password: ********

Connecting to Proxmox...
✓ Connection successful

Discovering storages...
✓ Found 3 storage(s)

Select files to upload:
  1. Upload files from a directory
  2. Upload specific file

Choice (1-2): 1
Directory path: ~/Downloads/distroget

Found 2 file(s):
  1. ubuntu-24.04-server-cloudimg-amd64.img (500.2 MB)
  2. fedora-cloud-40.qcow2 (450.1 MB)

[1/2] Uploading ubuntu-24.04-server-cloudimg-amd64.img
  Detected type: iso

Available storages for iso:
--------------------------------------------------------------------------------
1. Install
   Type: dir
   Content: iso, vztmpl, snippets
   Space: 7.8 GB available

Select storage (1-1) or 'q' to quit: 1
  Progress: 100%
  ✓ Uploaded to Install:template/iso/ubuntu-24.04-server-cloudimg-amd64.img

[2/2] Uploading fedora-cloud-40.qcow2
  Detected type: iso
  Progress: 100%
  ✓ Uploaded to Install:template/iso/fedora-cloud-40.qcow2

================================================================================
Deployment complete
================================================================================
```

### 3. Import to Proxmox VM

```bash
# SSH to Proxmox
ssh root@192.168.1.100

# Create VM and import cloud image
qm create 100 --name ubuntu-test --memory 2048 --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci
qm set 100 --scsi0 Install:0,import-from=/path/to/Install/template/iso/ubuntu-24.04-server-cloudimg-amd64.img
qm set 100 --ide2 Install:cloudinit
qm set 100 --cicustom "user=Install:snippets/ansible-ready.yaml"
qm set 100 --ipconfig0 ip=dhcp
qm start 100

# VM boots in ~30 seconds, SSH-ready with your ansible keys!
```

## Troubleshooting

### sshpass not found
```bash
sudo apt install sshpass  # Debian/Ubuntu
sudo dnf install sshpass  # Fedora/RHEL
```

### Connection timeout
- Verify Proxmox hostname/IP is correct
- Check firewall allows SSH (port 22)
- Verify SSH is enabled on Proxmox

### Permission denied
- Verify username/password are correct
- Try with root user (Proxmox default)
- Check SSH key authentication if not using password

### Storage not found
- Verify storage exists: `pvesm status`
- Check storage is enabled
- Verify storage supports required content type

### Upload fails
- Check available space: `df -h`
- Verify storage path permissions
- Check rsync is installed on both systems

## Security Notes

- Passwords are passed via SSHPASS environment variable (not command line arguments)
- SSH uses `StrictHostKeyChecking=no` for automated deployment
- For production, consider setting up SSH key authentication instead of passwords
- Store credentials securely or prompt interactively

## Advanced Usage

### Automated Deployment Script

```python
#!/usr/bin/env python3
from proxmox import ProxmoxTarget
import os
from pathlib import Path

# Get credentials from environment
PVE_HOST = os.getenv('PVE_HOST', 'pve.local')
PVE_USER = os.getenv('PVE_USER', 'root')
PVE_PASS = os.getenv('PVE_PASS')

# Connect
pve = ProxmoxTarget(PVE_HOST, PVE_USER, PVE_PASS)

# Get all cloud images from downloads
download_dir = Path.home() / 'Downloads' / 'distroget'
for file in download_dir.glob('*.qcow2'):
    print(f"Uploading {file.name}...")
    success, msg = pve.upload_file(str(file), 'Install', 'iso')
    if success:
        print(f"  ✓ {msg}")
    else:
        print(f"  ✗ {msg}")
```

### Integration with CI/CD

```bash
#!/bin/bash
# deploy-images.sh - Automated cloud image deployment

export PVE_HOST="pve.example.com"
export PVE_USER="automation@pve"
export PVE_PASS="${PVE_PASSWORD}"  # From CI/CD secrets

# Download latest images
python3 distroget.py --download-cloud-images

# Deploy to Proxmox
python3 deploy_script.py
```

## See Also

- [Proxmox Cloud-Init Documentation](https://pve.proxmox.com/wiki/Cloud-Init_Support)
- [distroget README](../README.md)
- [Cloud Image Updaters](../updaters.py)
