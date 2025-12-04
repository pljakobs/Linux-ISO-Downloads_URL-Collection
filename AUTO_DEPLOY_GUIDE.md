# Auto-Deploy Guide

## Overview

The auto-deploy feature allows you to mark specific ISO images or cloud images for automatic download and deployment to Proxmox VE when running scheduled updates.

## How It Works

1. **Mark Images**: In the TUI, navigate to specific images and press `a` to toggle the auto-deploy marker `[a]`
2. **Run Auto-Update with Deploy**: Execute `python3 distroget.py --auto-update --deploy-to-proxmox`
3. **Automatic Processing**: The system will:
   - Check all marked items for newer versions
   - Download any updates
   - Deploy directly to your configured Proxmox storage

## Marking Images for Auto-Deploy

### Using the TUI

```bash
python3 distroget.py
```

1. Navigate through the menu to find the specific image you want to auto-deploy
2. Press `a` to toggle the auto-deploy marker
3. Look for `[a]` prefix on marked items:
   - `[a][x] Fedora 40 Cloud` - Marked for auto-deploy AND selected
   - `[a][ ] Ubuntu 24.04 Cloud` - Marked for auto-deploy but not selected
   - `   [ ] Debian 12` - Not marked for auto-deploy

### Key Difference: Auto-Update vs Auto-Deploy

- **Auto-Update Distributions** (configured with `--configure`):
  - Downloads ALL versions/variants of a distribution
  - Example: Enabling "Fedora Cloud" downloads all spins (Base, Minimal, etc.)
  - Configured at distribution level
  
- **Auto-Deploy Items** (marked with `a` in TUI):
  - Deploys SPECIFIC images to Proxmox
  - Example: Only "Fedora 40 Cloud Base" gets deployed
  - Marked at individual image level

## Cron Automation

### Setup for Auto-Deploy

Add to your crontab (`crontab -e`):

```bash
# Check for updates and deploy nightly at 2 AM
0 2 * * * cd /path/to/distroget && python3 distroget.py --auto-update --deploy-to-proxmox >> /var/log/distroget-deploy.log 2>&1
```

### What Happens During Execution

1. **Auto-Update Check**: Downloads new versions of distributions marked in auto-update configuration
2. **Auto-Deploy Check**: For each item marked with `[a]`:
   - Checks if a newer version exists in the README.md
   - Downloads the new version
   - Deploys to configured Proxmox storage
   - Skips if already up-to-date

### Without Deploy Flag

```bash
# Only download, don't deploy
0 2 * * * cd /path/to/distroget && python3 distroget.py --auto-update
```

This will:
- Download new versions of auto-update distributions
- Skip auto-deploy items (no deployment happens)

## Example Workflow

### Scenario: Auto-deploy Latest Fedora Cloud Base

1. **Configure Proxmox** (one-time):
   ```bash
   python3 distroget.py --configure
   # Select: 1. Configure Proxmox
   # Enter hostname, select storage
   ```

2. **Mark Specific Image**:
   ```bash
   python3 distroget.py
   # Navigate: Fedora → Fedora Cloud → 40 → Base
   # Press: a (to mark for auto-deploy)
   # Quit: q
   ```

3. **Enable Auto-Update for Fedora Cloud** (optional):
   ```bash
   python3 distroget.py --configure
   # Select: 2. Configure Auto-Update
   # Toggle: Fedora Cloud (to download all new versions)
   ```

4. **Set Up Cron**:
   ```bash
   crontab -e
   # Add: 0 2 * * * cd /path/to/distroget && python3 distroget.py --auto-update --deploy-to-proxmox
   ```

### Result

Every night at 2 AM:
- Downloads any new Fedora Cloud images (all variants)
- Checks if Fedora Cloud Base has a newer version
- If yes, deploys the new Base image to Proxmox
- Logs all activity

## Configuration File

Auto-deploy items are stored in `~/.config/distroget/config.json`:

```json
{
  "auto_deploy_items": [
    "Fedora/Fedora Cloud/40",
    "Ubuntu/Ubuntu Cloud/24.04",
    "Debian/Debian Cloud/12"
  ],
  "proxmox": {
    "hostname": "pve.local",
    "storage_mappings": {
      "iso": "Install",
      "vztmpl": "Install"
    }
  }
}
```

## Use Cases

### 1. Testing Lab
Mark specific test images for auto-deploy:
- `Fedora/Fedora Cloud/40` - Latest Fedora for compatibility testing
- `Ubuntu/Ubuntu Cloud/24.04 LTS` - Long-term support version
- Updates deploy automatically each night

### 2. Production Base Images
Mark production-ready images:
- `Debian/Debian Cloud/12` - Stable base for containers
- `Rocky Linux/Rocky Cloud/9` - RHEL-compatible base
- Always have latest security patches

### 3. Development Environments
Mark development distros:
- `Fedora/Fedora Server/40` - Latest features
- `Ubuntu/Ubuntu Server/24.04` - Common deployment target
- Auto-deploy ensures dev environments stay current

## Checking Status

### View Marked Items

```bash
python3 -c "from config_manager import ConfigManager; print(ConfigManager().get_auto_deploy_items())"
```

### Test Auto-Deploy (Dry Run)

```bash
python3 distroget.py --auto-update --deploy-to-proxmox --dry-run
```

## Troubleshooting

### Issue: Items Not Deploying

**Check 1**: Verify item is marked
```bash
python3 distroget.py
# Navigate to the item, check for [a] prefix
```

**Check 2**: Verify Proxmox configuration
```bash
python3 distroget.py --configure
# Select: 1. Configure Proxmox
# Verify hostname and storage are set
```

**Check 3**: Test connection
```bash
ssh root@pve.local "pvesm status"
```

### Issue: Wrong Image Gets Deployed

- Auto-deploy works at the **leaf level** (specific image)
- Marking a category (e.g., "Fedora Cloud") doesn't work
- Must mark specific versions (e.g., "Fedora Cloud/40")

### Issue: Too Many Files Downloaded

**Solution 1**: Don't enable auto-update for the distribution
- Only mark specific items with `a`
- Don't add the distribution to auto-update list

**Solution 2**: Use separate download directory
```bash
python3 distroget.py --auto-update --deploy-to-proxmox --download-dir /path/to/auto-deploy
```

## Advanced: Python API

```python
from config_manager import ConfigManager
from pathlib import Path

config = ConfigManager()

# Mark items programmatically
config.toggle_auto_deploy_item("Fedora/Fedora Cloud/40")
config.toggle_auto_deploy_item("Ubuntu/Ubuntu Cloud/24.04")

# Run auto-update with deploy
from auto_update import auto_update_distributions

results = auto_update_distributions(
    download_dir=Path("/downloads"),
    deploy_to_proxmox=True
)

print(f"Deployed {len(results['deployments'])} files")
```

## Best Practices

1. **Start Small**: Mark 1-2 images initially to test the workflow
2. **Monitor Logs**: Check cron logs regularly for the first week
3. **Disk Space**: Ensure Proxmox storage has adequate space (cloud images are 2-5GB each)
4. **Version Pinning**: Mark specific versions (e.g., "40") not categories
5. **Test First**: Run `--dry-run` before adding to cron

## See Also

- [AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md) - General automation setup
- [PROXMOX_DEPLOYMENT.md](PROXMOX_DEPLOYMENT.md) - Proxmox integration details
- [FEATURE_SUMMARY.md](FEATURE_SUMMARY.md) - Complete feature overview
