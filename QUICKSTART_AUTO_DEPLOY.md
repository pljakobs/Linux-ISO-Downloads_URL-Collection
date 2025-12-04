# Quick Start: Auto-Deploy to Proxmox

## Complete Setup in 5 Minutes

### Step 1: Configure Proxmox Connection

```bash
python3 distroget.py --configure
```

Choose **1. Configure Proxmox**, then:
- Enter hostname: `pve.local` (or your Proxmox IP)
- Enter username: `root` (default)
- Test connection (will prompt for password if needed)
- Select storage for each content type:
  - **ISO storage**: For cloud images (qcow2/img files)
  - **CT Template storage**: For container templates
  - **Snippets storage**: For cloud-init configs

Example output:
```
✓ Connected to pve.local
Available storages:
  1. local (iso, vztmpl, snippets) - /var/lib/vz
  2. Install (iso) - /mnt/install
  
Select storage for 'iso' content: 2
✓ Configured: iso → Install
```

### Step 2: Mark Images for Auto-Deploy

```bash
python3 distroget.py
```

Navigate and mark images:
1. Use **↑↓** to navigate
2. Press **→** or **Enter** to expand categories
3. Navigate to specific image (e.g., `Fedora → Fedora Cloud → 40`)
4. Press **a** to toggle auto-deploy marker
5. Look for **[a]** prefix: `[a][ ] Fedora Cloud 40`
6. Press **q** to quit (settings auto-save)

**Example**: Mark Fedora Cloud 40 for auto-deploy
```
   [ ] Fedora                    ← Category
     → Fedora Cloud              ← Sub-category  
       [a][ ] 40                 ← Marked for auto-deploy!
```

### Step 3: Test Auto-Deploy

```bash
# Download directory (will be created if needed)
mkdir -p ~/iso_downloads

# Test run (shows what would be deployed)
python3 distroget.py --auto-update --deploy-to-proxmox --dry-run

# Actual deployment
python3 distroget.py --auto-update --deploy-to-proxmox
```

### Step 4: Set Up Cron (Optional)

Add to crontab (`crontab -e`):

```bash
# Auto-deploy nightly at 2 AM
0 2 * * * cd /path/to/distroget && python3 distroget.py --auto-update --deploy-to-proxmox >> /var/log/distroget.log 2>&1
```

---

## What Happens During Auto-Deploy

When you run `python3 distroget.py --auto-update --deploy-to-proxmox`:

1. **Checks Auto-Update Distributions** (configured via `--configure`)
   - Downloads ALL variants of enabled distributions
   - Example: If "Fedora Cloud" is enabled, downloads all spins

2. **Checks Auto-Deploy Items** (marked with `a` in TUI)
   - Finds items marked with `[a]` in config
   - Checks README.md for those specific items
   - Downloads ONLY if found in current list
   - Deploys to configured Proxmox storage

3. **Deployment Process**
   - Detects file type (iso, qcow2, img)
   - Selects appropriate storage
   - Uploads via SCP to Proxmox
   - Verifies file integrity

---

## Practical Examples

### Example 1: Single Cloud Image

**Goal**: Auto-deploy latest Fedora Cloud Base

```bash
# 1. Configure Proxmox
python3 distroget.py --configure
# Select: 1. Configure Proxmox
# Enter: pve.local, root, select "Install" storage

# 2. Mark the image
python3 distroget.py
# Navigate: Fedora → Fedora Cloud → 40
# Press: a (toggle marker)
# See: [a][ ] 40
# Press: q (quit)

# 3. Deploy
python3 distroget.py --auto-update --deploy-to-proxmox
```

**Result**: Downloads and deploys `fedora-cloud-40.qcow2` to `Install` storage

---

### Example 2: Multiple Cloud Images

**Goal**: Keep Ubuntu, Debian, and Rocky Cloud images updated

```bash
# Mark multiple images in TUI
python3 distroget.py
```

Navigate and press `a` on each:
- `Ubuntu/Ubuntu Cloud/24.04` → `[a][ ] 24.04`
- `Debian/Debian Cloud/12` → `[a][ ] 12`
- `Rocky Linux/Rocky Cloud/9` → `[a][ ] 9`

```bash
# Deploy all marked images
python3 distroget.py --auto-update --deploy-to-proxmox
```

**Result**: All three cloud images deployed to Proxmox

---

### Example 3: Automated Nightly Updates

**Goal**: Always have latest cloud images available

```bash
# 1. One-time setup
python3 distroget.py --configure
# Configure Proxmox and mark desired images

# 2. Mark images for auto-deploy
python3 distroget.py
# Mark: Fedora Cloud, Ubuntu Cloud, Debian Cloud

# 3. Add to cron
crontab -e
# Add: 0 2 * * * cd ~/distroget && python3 distroget.py --auto-update --deploy-to-proxmox
```

**Result**: Every night at 2 AM:
- Checks for new versions
- Downloads updates
- Deploys to Proxmox automatically

---

## Verification

### Check Marked Items

```bash
python3 -c "from config_manager import ConfigManager; print(ConfigManager().get_auto_deploy_items())"
```

Output:
```python
['Fedora/Fedora Cloud/40', 'Ubuntu/Ubuntu Cloud/24.04', 'Debian/Debian Cloud/12']
```

### View in Proxmox

After deployment, check in Proxmox:

```bash
ssh root@pve.local "ls -lh /mnt/pve/Install/template/iso/"
```

Or in Proxmox UI:
1. Navigate to: **Datacenter → Storage → Install**
2. Click: **Content**
3. See: `fedora-cloud-40.qcow2`, `ubuntu-24.04-server.img`, etc.

---

## Understanding Auto-Update vs Auto-Deploy

### Auto-Update (Distribution Level)

Configured via: `python3 distroget.py --configure` → **2. Configure Auto-Update**

```bash
# Enable "Fedora Cloud" in auto-update
```

**Effect**: Downloads **ALL** Fedora Cloud variants:
- Fedora-Cloud-Base-40.qcow2
- Fedora-Cloud-Minimal-40.qcow2
- Fedora-Cloud-Server-40.qcow2
- etc.

**Does NOT deploy** unless items are also marked with `[a]`

### Auto-Deploy (Item Level)

Marked via: `python3 distroget.py` → navigate → press `a`

```bash
# Mark "Fedora Cloud/40" with [a]
```

**Effect**: When running with `--deploy-to-proxmox`:
- Checks if "Fedora Cloud/40" exists in README
- Downloads the specific image
- **Deploys to Proxmox**

### Combined Usage

**Best practice**: Use both together

1. **Auto-Update**: Downloads all variants (for local archive)
2. **Auto-Deploy**: Deploys only specific images to Proxmox

```bash
# Configure auto-update for "Fedora Cloud" (downloads all)
python3 distroget.py --configure

# Mark only "Base" variant for deploy
python3 distroget.py
# Navigate to: Fedora/Fedora Cloud/40
# Press: a

# Run with both flags
python3 distroget.py --auto-update --deploy-to-proxmox
```

**Result**:
- Downloads: All Fedora Cloud variants (Base, Minimal, Server, etc.)
- Deploys: Only Fedora Cloud Base to Proxmox

---

## Troubleshooting

### Issue: "No auto-deploy items found"

**Check**: Are items marked?
```bash
python3 distroget.py
# Look for [a] prefix on items
```

**Fix**: Navigate to image and press `a`

---

### Issue: "Could not connect to Proxmox"

**Check**: SSH connection
```bash
ssh root@pve.local
```

**Fix**: 
- Verify hostname/IP is correct
- Set up SSH keys: `ssh-copy-id root@pve.local`
- Or install sshpass: `sudo dnf install sshpass`

---

### Issue: "No storage configured for iso"

**Check**: Storage mappings
```bash
python3 distroget.py --configure
# Select: 1. Configure Proxmox
# Verify storage is selected for each type
```

**Fix**: Re-run configuration and select storage

---

### Issue: Files not appearing in Proxmox

**Check**: Storage path
```bash
ssh root@pve.local "pvesm path Install:iso/fedora-cloud-40.qcow2"
```

**Verify**: File exists
```bash
ssh root@pve.local "ls -lh /mnt/pve/Install/template/iso/"
```

**Refresh**: Proxmox UI (click refresh icon in Storage → Content)

---

## Advanced Usage

### Deploy Without Auto-Update

```bash
# Only deploy marked items, skip auto-update checks
python3 distroget.py --deploy-to-proxmox

# Then select items in TUI and they deploy immediately
```

### Custom Download Location

```bash
# Specify download directory
python3 distroget.py --auto-update --deploy-to-proxmox --download-dir /data/isos
```

### Deploy Specific File Manually

```bash
python3 -c "
from pathlib import Path
from proxmox import ProxmoxTarget
from config_manager import ConfigManager

config = ConfigManager()
pve_config = config.get_proxmox_config()

pve = ProxmoxTarget(
    hostname=pve_config['hostname'],
    username=pve_config['username']
)

file_path = Path('/downloads/fedora-cloud-40.qcow2')
storage = config.get_storage_for_type('iso')

if pve.upload_file(file_path, storage):
    print(f'✓ Deployed {file_path.name}')
"
```

---

## Summary Commands

```bash
# Initial setup (one-time)
python3 distroget.py --configure

# Mark images (as needed)
python3 distroget.py
# Navigate, press 'a' to mark, press 'q' to quit

# Test deployment
python3 distroget.py --auto-update --deploy-to-proxmox --dry-run

# Deploy marked images
python3 distroget.py --auto-update --deploy-to-proxmox

# Automate (optional)
crontab -e
# Add: 0 2 * * * cd /path/to/distroget && python3 distroget.py --auto-update --deploy-to-proxmox
```

---

## Next Steps

- See [AUTO_DEPLOY_GUIDE.md](AUTO_DEPLOY_GUIDE.md) for detailed documentation
- See [PROXMOX_DEPLOYMENT.md](PROXMOX_DEPLOYMENT.md) for Proxmox integration details
- See [AUTOMATION_GUIDE.md](AUTOMATION_GUIDE.md) for cron configuration
