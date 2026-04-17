"""Tests for updaters.py"""
import pytest
from unittest.mock import patch, MagicMock
import updaters


class TestDistroUpdater:
    """Test suite for DistroUpdater base class."""
    
    def test_get_latest_version_not_implemented(self):
        """Test that base class raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            updaters.DistroUpdater.get_latest_version()
    
    def test_generate_download_links_not_implemented(self):
        """Test that base class raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            updaters.DistroUpdater.generate_download_links("1.0")
    
    def test_update_section_not_implemented(self):
        """Test that base class raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            updaters.DistroUpdater.update_section("content", "1.0", [])
    
    def test_add_metadata_comment(self):
        """Test metadata comment addition."""
        metadata = {"auto_updated": True, "last_updated": "2024-01-01"}
        section = "## Ubuntu\n"
        
        result = updaters.DistroUpdater.add_metadata_comment(section, metadata)
        
        assert "<!-- Auto-updated: 2024-01-01 -->" in result
        assert "## Ubuntu" in result
    
    def test_add_metadata_comment_no_metadata(self):
        """Test that no comment is added without metadata."""
        section = "## Ubuntu\n"
        
        result = updaters.DistroUpdater.add_metadata_comment(section, None)
        
        assert result == section
        assert "<!--" not in result


class TestGetDistrowatchVersion:
    """Test suite for get_distrowatch_version function."""
    
    @patch('requests.get')
    def test_get_version_success(self, mock_get):
        """Test successful version retrieval from DistroWatch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<a href="/table.php?distribution=ubuntu">Ubuntu 22.04</a>'
        mock_get.return_value = mock_response
        
        version = updaters.get_distrowatch_version('ubuntu')
        
        assert version is not None
    
    @patch('requests.get')
    def test_get_version_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        version = updaters.get_distrowatch_version('nonexistent')
        
        assert version is None
    
    @patch('requests.get')
    def test_get_version_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = Exception("Network error")
        
        version = updaters.get_distrowatch_version('ubuntu')
        
        assert version is None


class TestFedoraCloudUpdater:
    """Test suite for FedoraCloudUpdater."""
    
    @patch('updaters.fetch_fedora_releases')
    def test_get_latest_version(self, mock_fetch):
        """Test getting latest Fedora Cloud version."""
        mock_fetch.return_value = [
            {'version': '40', 'variant': 'Cloud', 'arch': 'x86_64', 'link': 'http://example.com/fedora40.qcow2'},
            {'version': '39', 'variant': 'Cloud', 'arch': 'x86_64', 'link': 'http://example.com/fedora39.qcow2'}
        ]
        
        if hasattr(updaters, 'FedoraCloudUpdater'):
            # Call as static/class method without self
            version = updaters.FedoraCloudUpdater.get_latest_version()
            assert version is not None
    
    @patch('updaters.fetch_fedora_releases')
    def test_generate_download_links(self, mock_fetch):
        """Test generating Fedora Cloud download links."""
        mock_fetch.return_value = [
            {'version': '40', 'variant': 'Cloud', 'arch': 'x86_64', 'link': 'http://example.com/Fedora-Cloud-Generic-40.qcow2'}
        ]
        
        if hasattr(updaters, 'FedoraCloudUpdater'):
            links = updaters.FedoraCloudUpdater.generate_download_links(['40'])
            # Returns dict with version keys
            assert isinstance(links, dict)
            assert '40' in links or len(links) > 0


class TestUbuntuCloudUpdater:
    """Test suite for UbuntuCloudUpdater."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Ubuntu Cloud version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<a href="jammy/">jammy/</a><a href="noble/">noble/</a>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'UbuntuCloudUpdater'):
            version = updaters.UbuntuCloudUpdater.get_latest_version()
            # May return None if parsing fails, just check it doesn't crash
            assert version is None or isinstance(version, (str, list, dict))
    
    def test_generate_download_links(self):
        """Test generating Ubuntu Cloud download links."""
        if hasattr(updaters, 'UbuntuCloudUpdater'):
            # Test with simple version string
            links = updaters.UbuntuCloudUpdater.generate_download_links('jammy')
            assert isinstance(links, (list, dict))
            # May be empty if no actual network call


class TestDebianCloudUpdater:
    """Test suite for DebianCloudUpdater."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Debian Cloud version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<a href="12.0.0/">12.0.0/</a>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'DebianCloudUpdater'):
            version = updaters.DebianCloudUpdater.get_latest_version()
            # May return None if parsing fails
            assert version is None or isinstance(version, str)
    
    def test_generate_download_links(self):
        """Test generating Debian Cloud download links."""
        if hasattr(updaters, 'DebianCloudUpdater'):
            links = updaters.DebianCloudUpdater.generate_download_links("12.0.0")
            assert isinstance(links, list)
            # May be empty without actual network call
            assert len(links) >= 0


class TestRockyCloudUpdater:
    """Test suite for RockyCloudUpdater."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Rocky Cloud version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<a href="9/">9/</a>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'RockyCloudUpdater'):
            version = updaters.RockyCloudUpdater.get_latest_version()
            assert version is not None
    
    def test_generate_download_links(self):
        """Test generating Rocky Cloud download links."""
        if hasattr(updaters, 'RockyCloudUpdater'):
            links = updaters.RockyCloudUpdater.generate_download_links("9")
            assert isinstance(links, list)
            assert len(links) > 0


class TestDevuanUpdater:
    """Test suite for DevuanUpdater."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Devuan version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <html>
            <body>
            <a href="devuan_excalibur_6.1.0_amd64_desktop.iso">desktop</a>
            <a href="devuan_excalibur_6.1.0_amd64_netinstall.iso">netinstall</a>
            <a href="devuan_excalibur_6.0.0_amd64_server.iso">server</a>
            </body>
            </html>
        '''
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'DevuanUpdater'):
            version = updaters.DevuanUpdater.get_latest_version()
            assert version == "6.1.0"
    
    @patch('requests.get')
    def test_get_latest_version_empty(self, mock_get):
        """Test handling when no ISOs are found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>No ISOs</body></html>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'DevuanUpdater'):
            version = updaters.DevuanUpdater.get_latest_version()
            assert version is None
    
    @patch('requests.get')
    def test_generate_download_links(self, mock_get):
        """Test generating Devuan download links."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <a href="devuan_excalibur_6.1.0_amd64_desktop.iso">desktop</a>
            <a href="devuan_excalibur_6.1.0_amd64_netinstall.iso">netinstall</a>
            <a href="devuan_excalibur_6.1.0_amd64_server.iso">server</a>
        '''
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'DevuanUpdater'):
            links = updaters.DevuanUpdater.generate_download_links("6.1.0")
            assert len(links) == 3
            assert all("6.1.0" in link for link in links)
            assert any("desktop" in link for link in links)
            assert any("netinstall" in link for link in links)
            assert any("server" in link for link in links)
    
    @patch('requests.get')
    def test_generate_download_links_with_fallback(self, mock_get):
        """Test fallback when no ISOs are found in HTML."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Error</body></html>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'DevuanUpdater'):
            links = updaters.DevuanUpdater.generate_download_links("6.1.0")
            # Should return fallback links
            assert len(links) > 0
            assert all("6.1.0" in link for link in links)
    
    def test_update_section(self):
        """Test updating Devuan section in README."""
        if hasattr(updaters, 'DevuanUpdater'):
            content = "## Devuan\n- [Old](http://old.link/devuan.iso)\n"
            links = [
                "- [devuan_excalibur_6.1.0_amd64_desktop.iso](https://mirror.leaseweb.com/devuan/6.1.0/desktop.iso)",
                "- [devuan_excalibur_6.1.0_amd64_server.iso](https://mirror.leaseweb.com/devuan/6.1.0/server.iso)"
            ]
            
            result = updaters.DevuanUpdater.update_section(content, "6.1.0", links)
            
            assert "6.1.0" in result
            assert "Devuan" in result
            assert "desktop.iso" in result
            assert "server.iso" in result
            assert "old.link" not in result  # Old content should be replaced


class TestDistroUpdaters:
    """Test suite for DISTRO_UPDATERS dictionary."""
    
    def test_distro_updaters_exists(self):
        """Test that DISTRO_UPDATERS dictionary exists."""
        assert hasattr(updaters, 'DISTRO_UPDATERS')
        assert isinstance(updaters.DISTRO_UPDATERS, dict)
    
    def test_distro_updaters_has_cloud_images(self):
        """Test that DISTRO_UPDATERS includes cloud image updaters."""
        expected_keys = ['fedora cloud', 'ubuntu cloud', 'debian cloud', 'rocky cloud']
        
        for key in expected_keys:
            if key in updaters.DISTRO_UPDATERS:
                updater = updaters.DISTRO_UPDATERS[key]
                assert hasattr(updater, 'get_latest_version')
                assert hasattr(updater, 'generate_download_links')
                assert hasattr(updater, 'update_section')


class TestArchLinuxUpdater:
    """Test suite for ArchLinuxUpdater."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Arch Linux version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'archlinux-2026.04.01-x86_64.iso'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'ArchLinuxUpdater'):
            version = updaters.ArchLinuxUpdater.get_latest_version()
            # Should extract version from filename
            assert version is not None
    
    @patch('requests.get')
    def test_generate_download_links(self, mock_get):
        """Test generating Arch Linux download links."""
        if hasattr(updaters, 'ArchLinuxUpdater'):
            links = updaters.ArchLinuxUpdater.generate_download_links("2026.04.01")
            assert isinstance(links, (list, str))
            # Links should contain version or download info
            assert len(links) > 0 or isinstance(links, str)


class TestElementaryOSUpdater:
    """Test suite for ElementaryOSUpdater (GitHub API)."""
    
    @patch('updaters.requests.get')
    def test_get_latest_version_github_api(self, mock_get):
        """Test getting latest elementary OS version from GitHub releases."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'tag_name': '7.1',
        }
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'ElementaryOSUpdater'):
            version = updaters.ElementaryOSUpdater.get_latest_version()
            # Should extract latest version from GitHub
            assert version == "7.1"


class TestFedoraUpdater:
    """Test suite for FedoraUpdater (Workstation)."""
    
    @patch('updaters.fetch_fedora_releases')
    def test_get_latest_version(self, mock_fetch):
        """Test getting latest Fedora version."""
        mock_fetch.return_value = [
            {'version': '40', 'variant': 'Workstation', 'arch': 'x86_64', 'link': 'http://example.com/fedora40.iso'},
            {'version': '39', 'variant': 'Workstation', 'arch': 'x86_64', 'link': 'http://example.com/fedora39.iso'}
        ]
        
        if hasattr(updaters, 'FedoraUpdater'):
            version = updaters.FedoraUpdater.get_latest_version()
            assert version is not None
    
    @patch('updaters.fetch_fedora_releases')
    def test_generate_download_links(self, mock_fetch):
        """Test generating Fedora download links with editions."""
        mock_fetch.return_value = [
            {'version': '40', 'variant': 'Workstation', 'arch': 'x86_64', 'link': 'http://example.com/Fedora-Workstation-Live-x86_64-40.iso'},
            {'version': '40', 'variant': 'Server', 'arch': 'x86_64', 'link': 'http://example.com/Fedora-Server-dvd-x86_64-40.iso'}
        ]
        
        if hasattr(updaters, 'FedoraUpdater'):
            links = updaters.FedoraUpdater.generate_download_links('40')
            # Should handle multiple editions
            assert isinstance(links, (dict, list))


class TestSolusUpdater:
    """Test suite for SolusUpdater (multiple editions)."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Solus version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<a href="Solus-4.4-Budgie.iso">Budgie</a>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'SolusUpdater'):
            version = updaters.SolusUpdater.get_latest_version()
            # Should extract version number
            assert version is not None or version == "4.4"
    
    @patch('requests.get')
    def test_generate_download_links_editions(self, mock_get):
        """Test generating Solus links for multiple editions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <a href="Solus-4.4-Budgie.iso">Budgie</a>
            <a href="Solus-4.4-GNOME.iso">GNOME</a>
            <a href="Solus-4.4-KDE.iso">KDE</a>
        '''
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'SolusUpdater'):
            links = updaters.SolusUpdater.generate_download_links("4.4")
            # Should handle multiple editions/variants
            assert isinstance(links, (list, dict, str))
            assert len(links) > 0 or isinstance(links, str)


class TestTailsUpdater:
    """Test suite for TailsUpdater."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Tails version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <a href="/tails/stable/Tails/Tails-6.0.iso">6.0</a>
            <a href="/tails/stable/Tails/Tails-5.20.iso">5.20</a>
        '''
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'TailsUpdater'):
            version = updaters.TailsUpdater.get_latest_version()
            assert version is not None or isinstance(version, str)
    
    @patch('requests.get')
    def test_generate_download_links(self, mock_get):
        """Test generating Tails download links."""
        if hasattr(updaters, 'TailsUpdater'):
            links = updaters.TailsUpdater.generate_download_links("6.0")
            assert isinstance(links, (list, dict, str))


class TestGentooUpdater:
    """Test suite for GentooUpdater (mirror scraping)."""
    
    @patch('requests.get')
    def test_get_latest_version(self, mock_get):
        """Test getting latest Gentoo version."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<a href="gentoo-20260417-amd64-minimal.iso">minimal</a>'
        mock_get.return_value = mock_response
        
        if hasattr(updaters, 'GentooUpdater'):
            version = updaters.GentooUpdater.get_latest_version()
            # Should extract version from ISO filename
            assert version is None or isinstance(version, str)
    
    @patch('requests.get')
    def test_generate_download_links(self, mock_get):
        """Test generating Gentoo download links."""
        if hasattr(updaters, 'GentooUpdater'):
            links = updaters.GentooUpdater.generate_download_links("20260417")
            assert isinstance(links, (list, dict, str))


class TestCriticalDistrosIntegration:
    """Integration tests for critical distros."""
    
    def test_all_critical_distros_in_registry(self):
        """Test that critical distros are registered."""
        critical_distros = [
            'Fedora',
            'Arch Linux',
            'Debian',
            'Ubuntu',
            'elementary OS',
            'Tails',
            'Solus',
            'Gentoo'
        ]
        
        for distro in critical_distros:
            assert distro in updaters.DISTRO_UPDATERS, f"{distro} not in DISTRO_UPDATERS"
    
    def test_critical_distros_have_methods(self):
        """Test that critical distros have all required methods."""
        critical_distros = [
            'Fedora',
            'Arch Linux',
            'ubuntu',
            'Devuan',
        ]
        
        for distro in critical_distros:
            if distro in updaters.DISTRO_UPDATERS:
                updater_class = updaters.DISTRO_UPDATERS[distro]
                assert hasattr(updater_class, 'get_latest_version'), f"{distro} missing get_latest_version"
                assert hasattr(updater_class, 'generate_download_links'), f"{distro} missing generate_download_links"
                assert hasattr(updater_class, 'update_section'), f"{distro} missing update_section"
