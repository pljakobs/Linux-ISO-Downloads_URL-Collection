#!/usr/bin/env python3
"""Updaters for various Linux distributions."""

import re
import requests


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
    def update_section(content, version, links, metadata=None):
        """
        Update the distro's section in the markdown content.
        
        Args:
            content: The markdown content
            version: Version number(s)
            links: Generated download links
            metadata: Optional dict with 'auto_updated' and 'last_updated' keys
        """
        raise NotImplementedError
    
    @staticmethod
    def add_metadata_comment(section_content, metadata):
        """Add metadata as HTML comment at the start of section."""
        if metadata and metadata.get('auto_updated'):
            comment = f"<!-- Auto-updated: {metadata.get('last_updated', 'N/A')} -->\n"
            return comment + section_content
        return section_content

    @staticmethod
    def simple_update_section(content, section_name, links, metadata=None):
        """Helper to update a simple section with links list."""
        if not links:
            return content
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = rf'(## {re.escape(section_name)}\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        return re.sub(pattern, replacement, content, flags=re.DOTALL)


def get_distrowatch_version(distro_name):
    """
    Generic scraper to get version from DistroWatch.
    
    Args:
        distro_name: The distro identifier on DistroWatch (e.g., 'mx', 'kali', 'mint')
    
    Returns:
        Version string or None
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0'
        }
        r = requests.get(f'https://distrowatch.com/table.php?distribution={distro_name}', 
                        headers=headers, timeout=10)
        r.raise_for_status()
        
        # Pattern 1: Look for "DistroName X.Y.Z" or "DistroName X.Y"
        # This is flexible and works for most distros
        patterns = [
            rf'{distro_name}[- ](\d+\.\d+(?:\.\d+)?)',  # lowercase with hyphen or space
            r'>(\d+\.\d+(?:\.\d+)?)<',  # Version in tags (common in version column)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, r.text, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"    Error fetching {distro_name} from DistroWatch: {e}")
    
    return None


FEDORA_RELEASES_URL = 'https://fedoraproject.org/releases.json'
_fedora_releases_cache = None


def fetch_fedora_releases():
    """Fetch and cache Fedora releases.json data."""
    global _fedora_releases_cache
    if _fedora_releases_cache is not None:
        return _fedora_releases_cache
    try:
        r = requests.get(FEDORA_RELEASES_URL, timeout=10)
        r.raise_for_status()
        _fedora_releases_cache = r.json()
        return _fedora_releases_cache
    except Exception as e:
        print(f"    Error fetching Fedora releases.json: {e}")
        return []


class FedoraUpdater(DistroUpdater):
    """Updater for Fedora Workstation, Server, Spins, and immutable variants."""

    VARIANTS = ['Workstation', 'Server', 'Silverblue', 'Kinoite', 'Spins']

    @staticmethod
    def get_latest_version():
        """Get latest Fedora versions from releases.json."""
        releases = fetch_fedora_releases()
        if not releases:
            return None
        versions = sorted(set(int(r['version']) for r in releases if r['version'].isdigit()), reverse=True)
        return [str(v) for v in versions[:2]] if versions else None

    @staticmethod
    def generate_download_links(versions):
        """Generate Fedora download links from releases.json."""
        if not versions:
            return {}
        releases = fetch_fedora_releases()
        if not releases:
            return {}

        structure = {v: {var: [] for var in FedoraUpdater.VARIANTS} for v in versions}

        for r in releases:
            if r['arch'] != 'x86_64' or r['version'] not in versions or not r['link'].endswith('.iso'):
                continue
            if r['variant'] in structure.get(r['version'], {}):
                structure[r['version']][r['variant']].append(r['link'])

        for v in versions:
            for var in FedoraUpdater.VARIANTS:
                structure[v][var] = sorted(set(structure[v][var]))

        return structure

    @staticmethod
    def update_section(content, versions, structure, metadata=None):
        """Update Fedora section with hierarchical markdown."""
        pattern = r'## Fedora(?:\s+Workstation)?\s*\n(.*?)(?=\n## [^#]|\Z)'
        if not structure:
            return content

        new_section = "## Fedora\n\n"
        for version in versions:
            if version not in structure:
                continue
            for variant in FedoraUpdater.VARIANTS:
                urls = structure[version].get(variant, [])
                if urls:
                    new_section += f"### Fedora {version} {variant}\n"
                    for url in urls:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"

        if re.search(pattern, content, re.DOTALL):
            return re.sub(pattern, new_section, content, flags=re.DOTALL)
        return f"{content}\n{new_section}"


class DebianUpdater(DistroUpdater):
    """Updater for Debian with multiple desktop environments."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Debian stable and testing versions."""
        try:
            # Get stable version
            r = requests.get('https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/', timeout=10)
            r.raise_for_status()
            
            # Extract version from filename like "debian-live-12.6.0-amd64-..."
            match = re.search(r'debian-live-(\d+\.\d+(?:\.\d+)?)-amd64', r.text)
            if match:
                full_version = match.group(1)
                stable = full_version.split('.')[0]
                # Only return stable - testing live builds are not consistently available
                return {'stable': stable}
        except Exception as e:
            print(f"    Error fetching Debian version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(versions):
        """Generate hierarchical Debian structure with all desktop environments."""
        if not versions or not isinstance(versions, dict):
            return {}
        
        structure = {}
        
        # Define branches to fetch
        branches = []
        if 'stable' in versions:
            branches.append(('stable', 'current-live', versions['stable']))
        # Testing builds removed - not consistently available
        
        for branch_name, path, version_label in branches:
            base_url = f"https://cdimage.debian.org/debian-cd/{path}/amd64/iso-hybrid"
            
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
                        key = f"{branch_name}_{de_name}"
                        if key not in structure:
                            structure[key] = {'version': version_label, 'name': de_name, 'branch': branch_name, 'urls': []}
                        structure[key]['urls'].append(f"{base_url}/{iso}")
            
            except Exception as e:
                print(f"    Error fetching Debian {branch_name} ISOs: {e}")
        
        return structure
    
    @staticmethod
    def update_section(content, versions, structure, metadata=None):
        """Update Debian section with hierarchical desktop environments."""
        pattern = r'## Debian\s*\n(.*?)(?=\n## [^#]|\Z)'
        
        if structure:
            new_section = "## Debian\n\n"
            
            # Group by branch (stable, testing)
            by_branch = {}
            for key, data in structure.items():
                branch = data['branch']
                if branch not in by_branch:
                    by_branch[branch] = []
                by_branch[branch].append(data)
            
            # Add stable first, then testing
            for branch in ['stable', 'testing']:
                if branch not in by_branch:
                    continue
                    
                items = sorted(by_branch[branch], key=lambda x: x['name'])
                for item in items:
                    version_label = item['version']
                    de_name = item['name']
                    branch_label = branch.capitalize()
                    new_section += f"### Debian {version_label} {de_name} ({branch_label})\n"
                    for url in item['urls']:
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
        """Get latest Ubuntu LTS and latest versions."""
        try:
            r = requests.get('https://releases.ubuntu.com/', timeout=10)
            r.raise_for_status()
            
            # Find all version directories
            versions = re.findall(r'href="(\d+\.\d+)/"', r.text)
            if versions:
                # Sort all versions
                sorted_versions = sorted(versions, key=lambda x: tuple(map(int, x.split('.'))))
                latest = sorted_versions[-1] if sorted_versions else None
                
                # Filter for LTS versions (.04)
                lts_versions = [v for v in versions if v.endswith('.04')]
                if lts_versions:
                    lts_versions.sort(key=lambda x: tuple(map(int, x.split('.'))))
                    lts = lts_versions[-1]
                    # Return both if different, otherwise just latest
                    if latest and latest != lts:
                        return {'lts': lts, 'latest': latest}
                    else:
                        return {'lts': lts}
        except Exception as e:
            print(f"    Error fetching Ubuntu version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(versions):
        """Generate hierarchical Ubuntu structure with all flavors."""
        if not versions or not isinstance(versions, dict):
            return {}
        
        structure = {}
        
        # Process each version type
        for version_type, version in versions.items():
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
                            key = f"{version_type}_{flavor}"
                            structure[key] = {'version': version, 'flavor': flavor, 'type': version_type, 'urls': [f"{url}{matches[0]}"]}
                except Exception:
                    pass
        
        return structure
    
    @staticmethod
    def update_section(content, versions, structure, metadata=None):
        """Update Ubuntu section with hierarchical flavors."""
        pattern = r'## Ubuntu\s*\n(.*?)(?=\n## [^#]|\Z)'
        
        if structure:
            new_section = "## Ubuntu\n\n"
            
            # Group by version type (LTS, latest)
            by_type = {}
            for key, data in structure.items():
                version_type = data['type']
                if version_type not in by_type:
                    by_type[version_type] = []
                by_type[version_type].append(data)
            
            # Add LTS first, then latest
            for version_type in ['lts', 'latest']:
                if version_type not in by_type:
                    continue
                    
                items = sorted(by_type[version_type], key=lambda x: x['flavor'])
                for item in items:
                    version = item['version']
                    flavor = item['flavor']
                    type_label = 'LTS' if version_type == 'lts' else ''
                    new_section += f"### {flavor} {version} {type_label}\n".strip() + "\n"
                    for url in item['urls']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                content = f"{content}\n{new_section}"
        
        return content


class OpenSUSEUpdater(DistroUpdater):
    """Updater for openSUSE."""
    
    @staticmethod
    def get_latest_version():
        """Get latest openSUSE versions."""
        try:
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
    def update_section(content, versions, structure, metadata=None):
        """Update openSUSE section."""
        pattern = r'## openSUSE\s*\n(.*?)(?=\n## [^#]|\Z)'
        
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


class LinuxMintUpdater(DistroUpdater):
    """Updater for Linux Mint."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Linux Mint version."""
        try:
            r = requests.get('https://linuxmint.com/download.php', timeout=10)
            r.raise_for_status()
            
            # Find version like "Linux Mint 22.2"
            match = re.search(r'Linux Mint (\d+\.?\d*)', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Linux Mint version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Linux Mint download links."""
        if not version:
            return []
        
        editions = ['cinnamon', 'mate', 'xfce']
        links = []
        
        for edition in editions:
            url = f"https://mirrors.edge.kernel.org/linuxmint/stable/{version}/linuxmint-{version}-{edition}-64bit.iso"
            links.append(f"- [{edition.capitalize()} {version}]({url})")
        
        return links
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Linux Mint section."""
        return DistroUpdater.simple_update_section(content, 'Linux Mint', links, metadata)


class ArchLinuxUpdater(DistroUpdater):
    """Updater for Arch Linux."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Arch Linux ISO date."""
        try:
            r = requests.get('https://archlinux.org/download/', timeout=10)
            r.raise_for_status()
            
            # Find version like "2025.12.01"
            match = re.search(r'(\d{4}\.\d{2}\.\d{2})', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Arch Linux version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Arch Linux download link."""
        if not version:
            return []
        
        url = f"https://geo.mirror.pkgbuild.com/iso/{version}/archlinux-{version}-x86_64.iso"
        return [f"- [Arch Linux {version}]({url})"]
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Arch Linux section."""
        return DistroUpdater.simple_update_section(content, 'Arch Linux', links, metadata)


class MXLinuxUpdater(DistroUpdater):
    """Updater for MX Linux."""
    
    @staticmethod
    def get_latest_version():
        """Get latest MX Linux version."""
        return get_distrowatch_version('mx')
    
    @staticmethod
    def generate_download_links(version):
        """Generate MX Linux download links."""
        if not version:
            return []
        
        links = []
        base_url = "http://ftp.u-strasbg.fr/linux/distributions/mxlinux/isos/MX/Final/Xfce"
        
        # AHS (Advanced Hardware Support) and standard versions
        links.append(f"- [MX-{version} AHS]({base_url}/MX-{version}_ahs_x64.iso)")
        links.append(f"- [MX-{version}]({base_url}/MX-{version}_x64.iso)")
        
        return links
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update MX Linux section."""
        return DistroUpdater.simple_update_section(content, 'MX Linux', links, metadata)


class KaliLinuxUpdater(DistroUpdater):
    """Updater for Kali Linux."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Kali Linux version."""
        try:
            r = requests.get('https://www.kali.org/get-kali/', timeout=10)
            r.raise_for_status()
            
            # Find version like "kali-linux-2025.3-"
            match = re.search(r'kali-linux-(\d{4}\.\d+)-', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Kali Linux version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Kali Linux download links."""
        if not version:
            return []
        
        base_url = "https://archive.kali.org/kali-images/current"
        variants = [
            ('Live', 'live-amd64'),
            ('Installer (Purple)', 'installer-purple-amd64'),
            ('Installer (Netinst)', 'installer-netinst-amd64'),
            ('Installer', 'installer-amd64')
        ]
        
        links = []
        for name, variant in variants:
            url = f"{base_url}/kali-linux-{version}-{variant}.iso"
            links.append(f"- [{name}]({url})")
        
        return links
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Kali Linux section."""
        return DistroUpdater.simple_update_section(content, 'Kali Linux', links, metadata)


class PopOSUpdater(DistroUpdater):
    """Updater for Pop!_OS."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Pop!_OS version."""
        try:
            r = requests.get('https://pop.system76.com/', timeout=10)
            r.raise_for_status()
            
            # Find version like "24.04 LTS"
            match = re.search(r'(\d+\.\d+) LTS', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Pop!_OS version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Pop!_OS download link."""
        if not version:
            return []
        
        # Pop!_OS uses a specific versioning scheme for their CDN
        # The URL format changes based on version, using intel variant as default
        url = f"https://pop-iso.sfo2.cdn.digitaloceanspaces.com/{version}/amd64/intel/5/pop-os_{version}_amd64_intel_5.iso"
        return [f"- [Pop!_OS {version}]({url})"]
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Pop!_OS section."""
        return DistroUpdater.simple_update_section(content, 'Pop!_OS', links, metadata)


class AlpineLinuxUpdater(DistroUpdater):
    """Updater for Alpine Linux."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Alpine Linux version."""
        try:
            r = requests.get('https://alpinelinux.org/downloads/', timeout=10)
            r.raise_for_status()
            
            # Find version like "alpine-standard-3.22.2-x86_64.iso"
            match = re.search(r'alpine-standard-(\d+\.\d+\.\d+)-x86_64\.iso', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Alpine Linux version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Alpine Linux download link."""
        if not version:
            return []
        
        # Alpine uses version like 3.22.2, major.minor is used in URL path (v3.22)
        version_parts = version.split('.')
        major_minor = f"v{version_parts[0]}.{version_parts[1]}"
        
        url = f"https://dl-cdn.alpinelinux.org/alpine/{major_minor}/releases/x86_64/alpine-standard-{version}-x86_64.iso"
        return [f"- [Alpine {version}]({url})"]
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Alpine Linux section."""
        return DistroUpdater.simple_update_section(content, 'Alpine Linux', links, metadata)


class ManjaroUpdater(DistroUpdater):
    """Updater for Manjaro."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Manjaro version."""
        # Manjaro is rolling release, use date from their download page
        try:
            r = requests.get('https://manjaro.org/download/', timeout=10)
            r.raise_for_status()
            
            # Find ISO filenames with versions like "manjaro-xfce-24.1.2"
            match = re.search(r'manjaro-\w+-(\d+\.\d+\.\d+)', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Manjaro version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Manjaro download links."""
        if not version:
            return []
        
        links = []
        base_url = "https://download.manjaro.org"
        editions = ['xfce', 'kde', 'gnome']
        
        for edition in editions:
            # Manjaro uses format: edition/version/manjaro-edition-version-kernel.iso
            # Use minimal notation as kernel version varies
            url = f"{base_url}/{edition}/{version}/manjaro-{edition}-{version}-minimal-x86_64.iso"
            links.append(f"- [{edition.upper()} {version}]({url})")
        
        return links
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Manjaro section."""
        return DistroUpdater.simple_update_section(content, 'Manjaro', links, metadata)


class EndeavourOSUpdater(DistroUpdater):
    """Updater for EndeavourOS."""
    
    @staticmethod
    def get_latest_version():
        """Get latest EndeavourOS version."""
        try:
            r = requests.get('https://endeavouros.com/', timeout=10)
            r.raise_for_status()
            
            # Find version like "EndeavourOS_Ganymede-2025.11.24"
            match = re.search(r'EndeavourOS[_-]\w+-(\d{4}\.\d{2}\.\d{2})', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching EndeavourOS version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate EndeavourOS download link."""
        if not version:
            return []
        
        # EndeavourOS typically has one main ISO
        url = f"https://github.com/endeavouros-team/ISO/releases/latest/download/EndeavourOS_{version}.iso"
        return [f"- [EndeavourOS {version}]({url})"]
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update EndeavourOS section."""
        return DistroUpdater.simple_update_section(content, 'EndeavourOS', links, metadata)


class ZorinOSUpdater(DistroUpdater):
    """Updater for Zorin OS."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Zorin OS version."""
        try:
            r = requests.get('https://zorin.com/os/download/', timeout=10)
            r.raise_for_status()
            
            # Find version like "Zorin OS 18"
            match = re.search(r'Zorin OS (\d+)', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching Zorin OS version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Zorin OS download links."""
        if not version:
            return []
        
        links = []
        # Zorin OS editions on SourceForge
        editions = [('Core', 'Core'), ('Lite', 'Lite')]
        
        for name, edition in editions:
            url = f"https://sourceforge.net/projects/zorin-os/files/{version}/Zorin-OS-{version}-{edition}-64-bit.iso"
            links.append(f"- [{name} {version}]({url})")
        
        return links
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Zorin OS section."""
        return DistroUpdater.simple_update_section(content, 'Zorin OS', links, metadata)


class FreeDOSUpdater(DistroUpdater):
    """Updater for FreeDOS."""
    
    @staticmethod
    def get_latest_version():
        """Get latest FreeDOS version."""
        try:
            r = requests.get('https://freedos.org/download/', timeout=10)
            r.raise_for_status()
            
            # Find version like "FreeDOS 1.3" or similar
            match = re.search(r'FreeDOS (\d+\.\d+)', r.text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"    Error fetching FreeDOS version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate FreeDOS download links."""
        if not version:
            return []
        
        links = []
        
        # Check for available downloads on the page
        try:
            r = requests.get('https://freedos.org/download/', timeout=10)
            r.raise_for_status()
            
            # Look for direct download links - FreeDOS typically uses .zip format
            # Pattern for various possible link formats
            patterns = [
                r'href="(https?://[^"]*FD\d+[^"]*\.zip)"',
                r'href="(https?://[^"]*freedos[^"]*\.zip)"',
                r'href="([^"]*FD\d+[^"]*\.zip)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, r.text, re.IGNORECASE)
                if matches:
                    for url in matches[:3]:  # Limit to first 3 matches
                        # Make URL absolute if needed
                        if not url.startswith('http'):
                            url = 'https://freedos.org' + url if url.startswith('/') else f'https://freedos.org/download/{url}'
                        filename = url.split('/')[-1]
                        links.append(f"- [{filename}]({url})")
                    break
            
            # Fallback to known download pattern if scraping fails
            if not links:
                # Use SourceForge as fallback
                base_url = f"https://sourceforge.net/projects/freedos/files/freedos/{version}"
                links.append(f"- [FreeDOS {version} (SourceForge)]({base_url})")
                
        except Exception as e:
            print(f"    Warning: Could not scrape FreeDOS downloads: {e}")
        
        return links if links else [f"- [FreeDOS {version}](https://freedos.org/download/)"]
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update FreeDOS section."""
        return DistroUpdater.simple_update_section(content, 'FreeDOS', links, metadata)


class FedoraCloudUpdater(DistroUpdater):
    """Updater for Fedora Cloud Base images."""

    @staticmethod
    def get_latest_version():
        """Get latest Fedora Cloud versions from releases.json."""
        releases = fetch_fedora_releases()
        if not releases:
            return None
        versions = sorted(set(int(r['version']) for r in releases
                             if r['version'].isdigit() and r['variant'] == 'Cloud'), reverse=True)
        return [str(v) for v in versions[:2]] if versions else None

    @staticmethod
    def generate_download_links(versions):
        """Generate Fedora Cloud image links from releases.json."""
        if not versions:
            return {}
        releases = fetch_fedora_releases()
        structure = {v: [] for v in versions}

        for r in releases:
            if r['arch'] != 'x86_64' or r['version'] not in versions or r['variant'] != 'Cloud':
                continue
            if r['link'].endswith('.qcow2') and 'Generic' in r['link']:
                structure[r['version']].append(r['link'])

        for v in versions:
            structure[v] = sorted(set(structure[v]))
        return structure

    @staticmethod
    def update_section(content, versions, structure, metadata=None):
        """Update Fedora Cloud section."""
        pattern = r'## Fedora Cloud\s*\n(.*?)(?=\n## [^#]|\Z)'
        if not structure:
            return content

        new_section = "## Fedora Cloud\n\n"
        for version in versions:
            if version in structure and structure[version]:
                new_section += f"### Fedora {version} Cloud Base\n"
                for url in structure[version]:
                    new_section += f"- [{url.split('/')[-1]}]({url})\n"
                new_section += "\n"

        if re.search(pattern, content, re.DOTALL):
            return re.sub(pattern, new_section, content, flags=re.DOTALL)
        return f"{content}\n{new_section}"


class UbuntuCloudUpdater(DistroUpdater):
    """Updater for Ubuntu Cloud images."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Ubuntu LTS and latest versions."""
        try:
            r = requests.get('https://cloud-images.ubuntu.com/', timeout=10)
            r.raise_for_status()
            
            # Find release directories
            releases = re.findall(r'href="([a-z]+)/"', r.text)
            
            # Map to version numbers (need to check each)
            versions = {}
            for release in releases:
                if release in ['daily', 'server', 'minimal']:
                    continue
                try:
                    r2 = requests.get(f'https://cloud-images.ubuntu.com/{release}/current/', timeout=5)
                    if r2.status_code == 200:
                        # Extract version from filename
                        match = re.search(r'(\d+\.\d+)', r2.text)
                        if match:
                            ver = match.group(1)
                            # LTS versions end in .04
                            if ver.endswith('.04'):
                                versions['lts'] = {'name': release, 'version': ver}
                            else:
                                versions['latest'] = {'name': release, 'version': ver}
                except:
                    pass
            
            return versions if versions else None
        except Exception as e:
            print(f"    Error fetching Ubuntu Cloud versions: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(versions):
        """Generate Ubuntu Cloud image links."""
        if not versions or not isinstance(versions, dict):
            return {}
        
        structure = {}
        
        for version_type, info in versions.items():
            release_name = info['name']
            base_url = f"https://cloud-images.ubuntu.com/{release_name}/current"
            
            try:
                r = requests.get(base_url + "/", timeout=10)
                r.raise_for_status()
                
                # Find server cloudimg
                img_pattern = re.compile(r'href="([^"]*server-cloudimg-amd64\.img)"')
                matches = img_pattern.findall(r.text)
                
                if matches:
                    structure[version_type] = {
                        'version': info['version'],
                        'name': release_name,
                        'urls': [f"{base_url}/{matches[0]}"]
                    }
            except Exception as e:
                print(f"    Warning: Could not fetch Ubuntu Cloud {release_name}: {e}")
        
        return structure
    
    @staticmethod
    def update_section(content, versions, structure, metadata=None):
        """Update Ubuntu Cloud section."""
        pattern = r'## Ubuntu Cloud\s*\n(.*?)(?=\n## [^#]|\Z)'
        
        if structure:
            new_section = "## Ubuntu Cloud\n\n"
            
            for version_type in ['lts', 'latest']:
                if version_type in structure:
                    info = structure[version_type]
                    type_label = 'LTS' if version_type == 'lts' else ''
                    new_section += f"### Ubuntu {info['version']} Cloud {type_label}\n".strip() + "\n"
                    for url in info['urls']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                content = f"{content}\n{new_section}"
        
        return content


class DebianCloudUpdater(DistroUpdater):
    """Updater for Debian Cloud images."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Debian cloud image version."""
        try:
            r = requests.get('https://cloud.debian.org/images/cloud/', timeout=10)
            r.raise_for_status()
            
            # Find release directories (e.g., bookworm, bullseye)
            releases = re.findall(r'href="([a-z]+)/"', r.text)
            
            # Get the latest release (typically first non-daily)
            for release in releases:
                if release not in ['sid', 'daily']:
                    # Map codename to version
                    codename_map = {
                        'bookworm': '12',
                        'bullseye': '11',
                        'buster': '10',
                        'trixie': '13'
                    }
                    if release in codename_map:
                        return {'name': release, 'version': codename_map[release]}
        except Exception as e:
            print(f"    Error fetching Debian Cloud version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version_info):
        """Generate Debian Cloud image links."""
        if not version_info or not isinstance(version_info, dict):
            return []
        
        release = version_info['name']
        base_url = f"https://cloud.debian.org/images/cloud/{release}/latest"
        
        try:
            r = requests.get(base_url + "/", timeout=10)
            r.raise_for_status()
            
            # Find generic cloud image (qcow2)
            img_pattern = re.compile(r'href="(debian-\d+-generic-amd64[^"]*\.qcow2)"')
            matches = img_pattern.findall(r.text)
            
            if matches:
                return [f"{base_url}/{matches[0]}"]
        except Exception as e:
            print(f"    Warning: Could not fetch Debian Cloud {release}: {e}")
        
        return []
    
    @staticmethod
    def update_section(content, version_info, links, metadata=None):
        """Update Debian Cloud section."""
        if not links:
            return content
        
        pattern = r'## Debian Cloud\s*\n(.*?)(?=\n## [^#]|\Z)'
        version = version_info.get('version', 'latest')
        
        new_section = f"## Debian Cloud\n\n### Debian {version} Cloud\n"
        for url in links:
            filename = url.split('/')[-1]
            new_section += f"- [{filename}]({url})\n"
        new_section += "\n"
        
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        else:
            content = f"{content}\n{new_section}"
        
        return content


class RockyCloudUpdater(DistroUpdater):
    """Updater for Rocky Linux Cloud images."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Rocky Linux version."""
        try:
            r = requests.get('https://download.rockylinux.org/pub/rocky/', timeout=10)
            r.raise_for_status()
            
            # Find version directories
            versions = re.findall(r'href="(\d+)/"', r.text)
            if versions:
                return sorted(versions, reverse=True)[0]
        except Exception as e:
            print(f"    Error fetching Rocky Cloud version: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(version):
        """Generate Rocky Linux Cloud image links."""
        if not version:
            return []
        
        base_url = f"https://download.rockylinux.org/pub/rocky/{version}/images/x86_64"
        
        try:
            r = requests.get(base_url + "/", timeout=10)
            r.raise_for_status()
            
            # Find GenericCloud qcow2 image
            img_pattern = re.compile(r'href="(Rocky-\d+-GenericCloud[^"]*\.qcow2)"')
            matches = img_pattern.findall(r.text)
            
            if matches:
                # Get the latest (highest version number)
                latest = sorted(matches)[-1]
                return [f"{base_url}/{latest}"]
        except Exception as e:
            print(f"    Warning: Could not fetch Rocky {version} Cloud: {e}")
        
        return []
    
    @staticmethod
    def update_section(content, version, links, metadata=None):
        """Update Rocky Cloud section."""
        if not links:
            return content
        
        pattern = r'## Rocky Linux Cloud\s*\n(.*?)(?=\n## [^#]|\Z)'
        
        new_section = f"## Rocky Linux Cloud\n\n### Rocky Linux {version} Cloud\n"
        for url in links:
            filename = url.split('/')[-1]
            new_section += f"- [{filename}]({url})\n"
        new_section += "\n"
        
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        else:
            content = f"{content}\n{new_section}"
        
        return content


# Registry of all updaters
DISTRO_UPDATERS = {
    'Fedora': FedoraUpdater,
    'Fedora Cloud': FedoraCloudUpdater,
    'Debian': DebianUpdater,
    'Debian Cloud': DebianCloudUpdater,
    'Ubuntu': UbuntuUpdater,
    'Ubuntu Cloud': UbuntuCloudUpdater,
    'Rocky Linux Cloud': RockyCloudUpdater,
    'openSUSE': OpenSUSEUpdater,
    'Linux Mint': LinuxMintUpdater,
    'Arch Linux': ArchLinuxUpdater,
    'MX Linux': MXLinuxUpdater,
    'Kali Linux': KaliLinuxUpdater,
    'Pop!_OS': PopOSUpdater,
    'Alpine Linux': AlpineLinuxUpdater,
    'Manjaro': ManjaroUpdater,
    'EndeavourOS': EndeavourOSUpdater,
    'Zorin OS': ZorinOSUpdater,
    'FreeDOS': FreeDOSUpdater,
}
