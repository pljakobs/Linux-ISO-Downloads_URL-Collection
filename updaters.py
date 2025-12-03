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


class FedoraUpdater(DistroUpdater):
    """Updater for Fedora Workstation and Spins with multiple versions."""
    
    @staticmethod
    def get_latest_version():
        """Get latest Fedora versions (latest stable + previous)."""
        try:
            # List the releases directory (following redirects)
            r = requests.get('https://download.fedoraproject.org/pub/fedora/linux/releases/', 
                           timeout=10, allow_redirects=True)
            r.raise_for_status()
            
            # Find all version numbers
            versions = re.findall(r'href="(\d+)/"', r.text)
            if versions:
                # Return the two highest version numbers
                sorted_versions = sorted([int(v) for v in versions], reverse=True)
                return [str(v) for v in sorted_versions[:2]]
        except Exception as e:
            print(f"    Error fetching Fedora versions: {e}")
        
        return None
    
    @staticmethod
    def generate_download_links(versions):
        """Generate hierarchical Fedora structure with multiple versions."""
        if not versions or not isinstance(versions, list):
            return []
        
        # Structure: {version: {'Workstation': [urls], 'Server': [urls], 'Spins': [urls], 'Silverblue': [urls]}}
        structure = {}
        
        for version_num in versions:
            structure[version_num] = {
                'Workstation': [], 
                'Server': [],
                'Spins': [],
                'Silverblue': [],
                'Kinoite': []
            }
            
            # Get Workstation edition
            try:
                workstation_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Workstation/x86_64/iso"
                r = requests.get(workstation_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find Workstation ISO
                iso_pattern = re.compile(r'href="(Fedora-Workstation-Live[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                if matches:
                    structure[version_num]['Workstation'].append(f"{workstation_url}/{matches[0]}")
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Workstation: {e}")
            
            # Get Server edition
            try:
                server_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Server/x86_64/iso"
                r = requests.get(server_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find Server ISOs
                iso_pattern = re.compile(r'href="(Fedora-Server[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                for iso in sorted(set(matches)):
                    structure[version_num]['Server'].append(f"{server_url}/{iso}")
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Server: {e}")
            
            # Get Silverblue edition
            try:
                silverblue_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Silverblue/x86_64/iso"
                r = requests.get(silverblue_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find Silverblue ISO
                iso_pattern = re.compile(r'href="(Fedora-Silverblue[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                if matches:
                    structure[version_num]['Silverblue'].append(f"{silverblue_url}/{matches[0]}")
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Silverblue: {e}")
            
            # Get Kinoite edition
            try:
                kinoite_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Kinoite/x86_64/iso"
                r = requests.get(kinoite_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find Kinoite ISO
                iso_pattern = re.compile(r'href="(Fedora-Kinoite[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                if matches:
                    structure[version_num]['Kinoite'].append(f"{kinoite_url}/{matches[0]}")
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Kinoite: {e}")
            
            # Get all Spins
            try:
                spins_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{version_num}/Spins/x86_64/iso"
                r = requests.get(spins_url + "/", timeout=10, allow_redirects=True)
                r.raise_for_status()
                
                # Find all spin ISOs (deduplicate)
                iso_pattern = re.compile(r'href="(Fedora-[^"]*\.iso)"')
                matches = iso_pattern.findall(r.text)
                unique_isos = sorted(set(matches))
                
                for iso in unique_isos:
                    structure[version_num]['Spins'].append(f"{spins_url}/{iso}")
                    
            except Exception as e:
                print(f"    Warning: Could not fetch Fedora {version_num} Spins: {e}")
        
        # Add CoreOS (version-independent, always latest)
        structure['CoreOS'] = {'Stable': []}
        try:
            coreos_url = "https://builds.coreos.fedoraproject.org/prod/streams/stable/builds"
            r = requests.get(coreos_url + "/builds.json", timeout=10)
            r.raise_for_status()
            import json
            builds = json.loads(r.text)
            if 'builds' in builds and builds['builds']:
                latest_build = builds['builds'][0]
                build_id = latest_build['id']
                iso_url = f"https://builds.coreos.fedoraproject.org/prod/streams/stable/builds/{build_id}/x86_64/fedora-coreos-{build_id}-live.x86_64.iso"
                structure['CoreOS']['Stable'].append(iso_url)
        except Exception as e:
            print(f"    Warning: Could not fetch Fedora CoreOS: {e}")
        
        # Add Rawhide (development version, always latest)
        structure['Rawhide'] = {'Development': []}
        try:
            rawhide_url = "https://download.fedoraproject.org/pub/fedora/linux/development/rawhide/Workstation/x86_64/iso"
            r = requests.get(rawhide_url + "/", timeout=10, allow_redirects=True)
            r.raise_for_status()
            
            # Find Rawhide Workstation ISO
            iso_pattern = re.compile(r'href="(Fedora-Workstation-Live[^"]*\.iso)"')
            matches = iso_pattern.findall(r.text)
            if matches:
                structure['Rawhide']['Development'].append(f"{rawhide_url}/{matches[0]}")
        except Exception as e:
            print(f"    Warning: Could not fetch Fedora Rawhide: {e}")
        
        return structure
    
    @staticmethod
    def update_section(content, versions, structure, metadata=None):
        """Update Fedora section with hierarchical markdown."""
        # Find any existing Fedora section (Fedora or Fedora Workstation)
        # Match only top-level ## sections (not ### subsections)
        pattern = r'## Fedora(?:\s+Workstation)?\s*\n(.*?)(?=\n## [^#]|\Z)'
        
        if structure:
            new_section = "## Fedora\n\n"
            
            for version in versions:
                if version not in structure:
                    continue
                
                version_data = structure[version]
                
                # Add Workstation subsection
                if version_data.get('Workstation'):
                    new_section += f"### Fedora {version} Workstation\n"
                    for url in version_data['Workstation']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
                
                # Add Server subsection
                if version_data.get('Server'):
                    new_section += f"### Fedora {version} Server\n"
                    for url in version_data['Server']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
                
                # Add Silverblue subsection
                if version_data.get('Silverblue'):
                    new_section += f"### Fedora {version} Silverblue\n"
                    for url in version_data['Silverblue']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
                
                # Add Kinoite subsection
                if version_data.get('Kinoite'):
                    new_section += f"### Fedora {version} Kinoite\n"
                    for url in version_data['Kinoite']:
                        filename = url.split('/')[-1]
                        new_section += f"- [{filename}]({url})\n"
                    new_section += "\n"
                
                # Add Spins subsection
                if version_data.get('Spins'):
                    new_section += f"### Fedora {version} Spins\n"
                    for url in version_data['Spins']:
                        filename = url.split('/')[-1]
                        # Extract spin name from filename
                        match = re.search(r'Fedora-([^-]+)-', filename)
                        spin_name = match.group(1) if match else filename
                        new_section += f"- [{spin_name}]({url})\n"
                    new_section += "\n"
            
            # Add CoreOS section
            if 'CoreOS' in structure and structure['CoreOS'].get('Stable'):
                new_section += "### Fedora CoreOS\n"
                for url in structure['CoreOS']['Stable']:
                    filename = url.split('/')[-1]
                    new_section += f"- [{filename}]({url})\n"
                new_section += "\n"
            
            # Add Rawhide section
            if 'Rawhide' in structure and structure['Rawhide'].get('Development'):
                new_section += "### Fedora Rawhide (Development)\n"
                for url in structure['Rawhide']['Development']:
                    filename = url.split('/')[-1]
                    new_section += f"- [{filename}]({url})\n"
                new_section += "\n"
            
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, new_section, content, flags=re.DOTALL)
            else:
                # Add new section
                content = f"{content}\n{new_section}"
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Linux Mint\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Arch Linux\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## MX Linux\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Kali Linux\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Pop!_OS\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Alpine Linux\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Manjaro\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## EndeavourOS\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


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
        if not links:
            return content
        
        section_content = '\n'.join(links)
        section_content = DistroUpdater.add_metadata_comment(section_content, metadata)
        pattern = r'(## Zorin OS\s*\n)(.*?)(?=\n## [^#]|\Z)'
        replacement = f'\\1{section_content}\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content


# Registry of all updaters
DISTRO_UPDATERS = {
    'Fedora': FedoraUpdater,
    'Debian': DebianUpdater,
    'Ubuntu': UbuntuUpdater,
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
}
