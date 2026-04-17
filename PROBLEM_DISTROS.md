# Distros Requiring Manual Attention

Based on analysis of the updater implementations, the following distros are known to have potential issues with version detection or link generation:

## Category 1: Uses DistroWatch Fallback (May Return None)
These updaters rely on DistroWatch as their primary or fallback method, which can be unreliable:

- AlmaLinux
- Artix Linux
- BackBox
- CentOS
- Clear Linux
- KNOPPIX
- LXLE
- OpenMandriva (potential name typo)
- Parrot OS
- Redcore Linux
- Septor
- SparkyLinux
- Void Linux

**Action**: Verify DistroWatch links are current, or implement GitHub API/mirror-based version detection

---

## Category 2: Uses SourceForge (SSL Certificate Issues)
These may have SSL verification issues:

- Finnix
- FreeDOS

**Action**: Verify SourceForge accessibility from your network, or update to use GitHub releases if available

---

## Category 3: Mirror-Based (Network Dependent)
These rely on directory listing from mirrors and may timeout:

- BlackArch (mirror SSL issues)
- Devuan
- Gentoo
- Slackware
- TrueNAS Core

**Action**: Verify mirror accessibility and SSL certificates are valid

---

## Category 4: Complex Multi-Edition Updaters
These generate multiple links and may fail partially:

- Fedora (multiple editions + cloud)
- Mageia (multiple editions)
- Solus (multiple editions)

**Action**: Verify all edition mirrors are accessible

---

## Quick Manual Check Steps

```bash
#1. Run diagnostic
python3 diagnose_updaters.py

# 2. For each problematic distro, manually test the URL in updater
# For example, test Devuan:

curl -s https://pkgmaster.devuan.org/devuan/dists/ceres/Release | head -20

# 3. If URL fails, update updaters.py with correct URL

# 4. Re-run diagnostic to verify fix

python3 diagnose_updaters.py
```

---

## How to Fix a Problematic Updater

1. **Identify the issue**:
   - `None` return = version detection failed
   - `[]` return = links not generated
   - Network error = mirror unreachable

2. **Update the updater** in `updaters.py`:
   ```python
   class ProblematicDistroUpdater(DistroUpdater):
       @staticmethod
       def get_latest_version():
           try:
               r = requests.get('https://correct-mirror-url.com/...', timeout=10)
               # Parse version from response
               return version
           except Exception as e:
               print(f"    Error: {e}")
               return None
   ```

3. **Test locally**:
   ```python
   from updaters import ProblematicDistroUpdater
   version = ProblematicDistroUpdater.get_latest_version()
   links = ProblematicDistroUpdater.generate_download_links(version)
   print(version)  # Should show version, not None
   print(links)    # Should show URLs, not empty
   ```

4. **Re-test** with:
   ```bash
   python3 diagnose_updaters.py | grep ProblematicDistro
   ```

---

## Known SSL/Network Issues

- BlackArch mirror has SSL hostname mismatch
- Some proxies may block certain mirrors
- Firewalls may block access to SourceForge

**Workaround**: Use a VPN or check proxy settings if you see connection errors
