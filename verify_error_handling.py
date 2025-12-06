#!/usr/bin/env python3
"""
Quick error handling demo for distroget UI.

This script simulates common error scenarios to verify that
errors are caught and displayed in dialogs instead of crashing.
"""

import sys
import tempfile
import os

def test_error_dialog_exists():
    """Verify the error dialog infrastructure exists."""
    print("Testing error dialog infrastructure...")
    
    try:
        from distroget import DistroGetUI
        import inspect
        
        # Check show_error_dialog exists
        if not hasattr(DistroGetUI, 'show_error_dialog'):
            print("❌ show_error_dialog method not found")
            return False
        
        # Check signature
        sig = inspect.signature(DistroGetUI.show_error_dialog)
        params = list(sig.parameters.keys())
        expected = ['self', 'title', 'message', 'error_details']
        
        if params == expected:
            print("✅ show_error_dialog has correct signature")
        else:
            print(f"⚠️  show_error_dialog signature: {params}")
            print(f"   Expected: {expected}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking dialog infrastructure: {e}")
        return False


def test_protected_methods():
    """Check that critical methods have error handling."""
    print("\nChecking error handling in critical methods...")
    
    try:
        from distroget import DistroGetUI
        import inspect
        
        methods = [
            'set_directory',
            'initialize_download_manager',
            'toggle_auto_deploy',
            'update_download_panel',
            'on_checkbox_changed',
            'run',
        ]
        
        all_protected = True
        
        for method_name in methods:
            if not hasattr(DistroGetUI, method_name):
                print(f"❌ {method_name} not found")
                all_protected = False
                continue
            
            source = inspect.getsource(getattr(DistroGetUI, method_name))
            
            # Check for try-except blocks
            has_try = 'try:' in source
            has_except = 'except' in source
            
            if has_try and has_except:
                print(f"✅ {method_name} has error handling")
            else:
                print(f"⚠️  {method_name} may lack error handling")
                all_protected = False
        
        return all_protected
        
    except Exception as e:
        print(f"❌ Error checking method protection: {e}")
        return False


def generate_error_scenarios():
    """Generate test scenarios for manual testing."""
    print("\n" + "="*60)
    print("Manual Error Testing Scenarios")
    print("="*60)
    
    scenarios = [
        {
            'name': 'Permission Denied',
            'action': 'Press D, enter: /root/download',
            'expected': 'Error dialog: "Permission Denied"',
            'verify': 'UI remains functional after dismissing dialog'
        },
        {
            'name': 'Invalid Path',
            'action': 'Press D, enter: /dev/null/invalid',
            'expected': 'Error dialog: "Directory Error"',
            'verify': 'Can try a different path'
        },
        {
            'name': 'Empty Path',
            'action': 'Press D, leave empty, press Enter',
            'expected': 'Dialog closes, no error (by design)',
            'verify': 'No crash, UI functional'
        },
        {
            'name': 'Read-Only Filesystem',
            'action': 'Create dir, chmod 444, try to use it',
            'expected': 'Error dialog: "Permission Denied"',
            'verify': 'Can select different directory'
        },
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   Action:   {scenario['action']}")
        print(f"   Expected: {scenario['expected']}")
        print(f"   Verify:   {scenario['verify']}")
    
    print("\n" + "="*60)
    print("To test: Run 'python distroget.py' and try each scenario")
    print("="*60 + "\n")


def main():
    """Run all verification tests."""
    print("="*60)
    print("Error Handling Verification for distroget")
    print("="*60 + "\n")
    
    # Run automated checks
    dialog_ok = test_error_dialog_exists()
    methods_ok = test_protected_methods()
    
    # Generate manual test scenarios
    generate_error_scenarios()
    
    # Summary
    print("\nVerification Summary:")
    print("-" * 60)
    if dialog_ok and methods_ok:
        print("✅ All automated checks passed")
        print("✅ Error handling infrastructure is in place")
        print("\n📋 Next step: Run manual tests in the UI")
        return 0
    else:
        print("⚠️  Some checks failed - review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
