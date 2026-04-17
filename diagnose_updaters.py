#!/usr/bin/env python3
"""
Diagnostic script to identify distros with version detection issues.
Tests each updater and reports errors without downloading.
"""

import sys
from pathlib import Path
import threading

sys.path.insert(0, str(Path(__file__).parent))

from updaters import DISTRO_UPDATERS

def test_updater_version_with_timeout(distro_name: str, updater_class, timeout_sec=5) -> dict:
    """
    Test version detection with timeout. Report any errors.
    """
    result = {
        'distro': distro_name,
        'status': 'unknown',
        'version': None,
        'error': None,
    }
    
    # Container for result from thread
    thread_result = [None]
    thread_error = [None]
    
    def run_test():
        try:
            version = updater_class.get_latest_version()
            if version is None or version == '':
                thread_error[0] = 'get_latest_version() returned None or empty'
            else:
                thread_result[0] = str(version)[:50]
        except Exception as e:
            thread_error[0] = str(e)[:100]
    
    thread = threading.Thread(target=run_test, daemon=False)
    thread.start()
    thread.join(timeout=timeout_sec)
    
    if thread.is_alive():
        # Timeout occurred
        result['status'] = 'timeout'
        result['error'] = 'Network timeout (5s) - mirror unreachable'
        return result
    
    if thread_error[0]:
        result['status'] = 'error' if 'returned None' not in thread_error[0] else 'no_version'
        result['error'] = thread_error[0]
        return result
    
    if thread_result[0]:
        result['version'] = thread_result[0]
        result['status'] = 'success'
        return result
    
    result['status'] = 'unknown'
    result['error'] = 'Unknown error'
    return result


def main():
    print("=" * 100)
    print("DISTRO UPDATER DIAGNOSTIC REPORT")
    print("=" * 100)
    print()
    
    sorted_distros = sorted(DISTRO_UPDATERS.keys())
    results = []
    
    successful = 0
    no_version = 0
    timeouts = 0
    errors = 0
    
    for i, distro_name in enumerate(sorted_distros, 1):
        updater_class = DISTRO_UPDATERS[distro_name]
        
        print(f"[{i:2d}/{len(DISTRO_UPDATERS)}] {distro_name:30s} ", end='', flush=True)
        
        result = test_updater_version_with_timeout(distro_name, updater_class)
        results.append(result)
        
        if result['status'] == 'success':
            print(f"✓ v{result.get('version', 'unknown')}")
            successful += 1
        elif result['status'] == 'no_version':
            print(f"⚠ NO VERSION")
            no_version += 1
        elif result['status'] == 'timeout':
            print(f"⏱ TIMEOUT: {result.get('error', '')}")
            timeouts += 1
        else:
            print(f"✗ ERROR: {result.get('error', '')}")
            errors += 1
    
    # Print summary
    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"✓ Successful:  {successful}/{len(DISTRO_UPDATERS)}")
    print(f"⚠ No Version:  {no_version}/{len(DISTRO_UPDATERS)}")
    print(f"⏱ Timeouts:    {timeouts}/{len(DISTRO_UPDATERS)}")
    print(f"✗ Errors:      {errors}/{len(DISTRO_UPDATERS)}")
    print()
    
    # Print problematic distros
    if no_version > 0 or timeouts > 0 or errors > 0:
        print("=" * 100)
        print("DISTROS REQUIRING MANUAL ATTENTION")
        print("=" * 100)
        print()
        
        no_versions = [r for r in results if r['status'] == 'no_version']
        if no_versions:
            print("NO VERSION DETECTED:")
            for result in no_versions:
                print(f"  • {result['distro']}")
        
        timeout_distros = [r for r in results if r['status'] == 'timeout']
        if timeout_distros:
            print()
            print("NETWORK TIMEOUTS (Mirror unreachable):")
            for result in timeout_distros:
                print(f"  • {result['distro']}")
        
        http_errors = [r for r in results if r['status'] == 'error']
        if http_errors:
            print()
            print("ERRORS:")
            for result in http_errors:
                error_short = result.get('error', 'Unknown')[:80]
                print(f"  • {result['distro']}")
                print(f"    → {error_short}")
        
        print()
        print("NEXT STEPS:")
        print("  1. Check distro official website for current download links")
        print("  2. Update the updater class in updaters.py")
        print("  3. Re-run: python3 diagnose_updaters.py")
    
    print()
    
    if errors > 0 or no_version > 0:
        sys.exit(1)
    else:
        print("SUCCESS: Version detection working. Ready to run --update-only")
        sys.exit(0)


if __name__ == '__main__':
    main()
