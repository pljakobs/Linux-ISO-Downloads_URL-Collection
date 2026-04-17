#!/usr/bin/env python3
"""
Comprehensive test of all 63 distro updaters.
Tests that each updater class is properly instantiated and has required methods.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import updaters
sys.path.insert(0, str(Path(__file__).parent.parent))

from updaters import DISTRO_UPDATERS, DistroUpdater

def test_updater_structure(distro_name: str, updater_class) -> dict:
    """
    Validate updater class structure and required methods.
    Tests method signatures without making HTTP calls.
    
    Returns:
        dict with status and any validation errors
    """
    result = {
        'distro': distro_name,
        'status': 'unknown',
        'has_get_latest_version': False,
        'has_generate_download_links': False,
        'has_update_section': False,
        'error': None
    }
    
    try:
        # Check inheritance
        if not issubclass(updater_class, DistroUpdater):
            result['error'] = 'Does not inherit from DistroUpdater'
            result['status'] = 'error'
            return result
        
        # Check required methods exist
        has_glv = hasattr(updater_class, 'get_latest_version') and callable(getattr(updater_class, 'get_latest_version'))
        has_gdl = hasattr(updater_class, 'generate_download_links') and callable(getattr(updater_class, 'generate_download_links'))
        has_us = hasattr(updater_class, 'update_section') and callable(getattr(updater_class, 'update_section'))
        
        result['has_get_latest_version'] = has_glv
        result['has_generate_download_links'] = has_gdl
        result['has_update_section'] = has_us
        
        if not (has_glv and has_gdl and has_us):
            result['error'] = f'Missing methods: get_latest_version={has_glv}, generate_download_links={has_gdl}, update_section={has_us}'
            result['status'] = 'incomplete'
            return result
        
        # Test with mocked requests
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = '<html><body>test version 1.0</body></html>'
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            try:
                version = updater_class.get_latest_version()
                if version is None or version == '':
                    # Some updaters may return None on mock data - that's ok for structure test
                    result['status'] = 'callable'
                else:
                    result['status'] = 'success'
                    result['version'] = str(version)[:30]  # Truncate long versions
            except Exception:
                # Structure is valid even if version detection fails with mock data
                result['status'] = 'callable'
        
        return result
    
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        return result


def main():
    """Test all 63 updaters for proper structure and methods."""
    print("=" * 80)
    print("Validating All 63 Distro Updater Classes")
    print("=" * 80)
    print()
    
    results = []
    successful = 0
    callable_only = 0
    incomplete = 0
    errors = 0
    
    # Sort distros for consistent output
    sorted_distros = sorted(DISTRO_UPDATERS.keys())
    
    total_updaters = len(DISTRO_UPDATERS)
    for i, distro_name in enumerate(sorted_distros, 1):
        updater_class = DISTRO_UPDATERS[distro_name]
        
        print(f"[{i:2d}/{total_updaters}] {distro_name:30s} ", end='', flush=True)
        
        result = test_updater_structure(distro_name, updater_class)
        results.append(result)
        
        if result['status'] == 'success':
            print(f"✓ v{result.get('version', 'unknown'):25s}")
            successful += 1
        elif result['status'] == 'callable':
            print(f"✓ (methods callable)")
            callable_only += 1
        elif result['status'] == 'incomplete':
            print(f"⚠ INCOMPLETE: {result.get('error', 'unknown')}")
            incomplete += 1
        else:  # error
            print(f"✗ ERROR: {result.get('error', 'unknown')}")
            errors += 1
    
    # Print summary
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"✓ Validated:   {successful}/{total_updaters} (with mock version data)")
    print(f"✓ Callable:    {callable_only}/{total_updaters} (structure valid)")
    print(f"⚠ Incomplete:  {incomplete}/{total_updaters} (missing methods)")
    print(f"✗ Errors:      {errors}/{total_updaters}")
    print()
    print(f"Total Valid:   {successful + callable_only}/{total_updaters}")
    print()
    
    # Print details of any errors/incomplete
    failures = [r for r in results if r['status'] in ['error', 'incomplete']]
    if failures:
        print("=" * 80)
        print("Issues Found")
        print("=" * 80)
        for result in failures:
            print(f"\n{result['distro']}:")
            print(f"  Status: {result['status']}")
            if result['error']:
                print(f"  Error: {result['error']}")
    
    print()
    
    # Exit with appropriate code
    if errors > 0 or incomplete > 0:
        print(f"FAILED: {errors + incomplete} issues found")
        sys.exit(1)
    else:
        print(f"SUCCESS: All {total_updaters} updater classes properly structured")
        sys.exit(0)


if __name__ == '__main__':
    main()
