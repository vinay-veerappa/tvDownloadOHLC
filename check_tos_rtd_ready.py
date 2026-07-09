#!/usr/bin/env python
"""
Check if TOS RTD is properly enabled and COM-registered.

This script verifies:
1. TOS RTD ProgID is registered (Tos.RTD)
2. RTD CLSID is registered ({EC0E6191-DB51-11D3-8F3E-00C04F3651B8})
3. RTD typelib GUID is registered ({BA792DC8-807E-43E3-B484-47465D82C4D1})
4. Attempt to create RTD COM object (requires TOS running)

Steps to enable TOS RTD:
1. Open ThinkorSwim
2. Click Settings (gear icon top right)
3. Go to Application API → RTD Server
4. Check "Enable RTD Server"
5. Close Settings
6. RESTART ThinkorSwim (required for COM registration!)
7. Run this script

Expected output after proper setup:
  [OK] ProgID Tos.RTD registered
  [OK] CLSID {EC0E6191-...} registered
  [OK] TypeLib {BA792DC8-...} registered
  [OK] COM object created successfully
  [OK] RTD is READY
"""
import sys
import time
from winreg import HKEY_CLASSES_ROOT, OpenKey, QueryValue, EnumKey
from pathlib import Path

def check_registry_key(path: str) -> bool:
    """Check if a registry key exists."""
    try:
        with OpenKey(HKEY_CLASSES_ROOT, path):
            return True
    except FileNotFoundError:
        return False

def get_registry_value(path: str, value_name: str = None) -> str:
    """Get a registry value."""
    try:
        with OpenKey(HKEY_CLASSES_ROOT, path) as key:
            val, _ = QueryValue(key, value_name)
            return val
    except Exception as e:
        return f"Error: {e}"

print("=" * 70)
print("TOS RTD COM Registration Check")
print("=" * 70)

# Check 1: ProgID
print("\n[1] Checking ProgID: Tos.RTD")
if check_registry_key("Tos.RTD"):
    val = get_registry_value("Tos.RTD")
    print(f"    [OK] ProgID exists -> {val}")
    print("    Note: Value should be a GUID or reference, not just 'Tos.RTD'")
else:
    print("    [FAIL] ProgID NOT registered")
    print("    FIX: Enable RTD in TOS Settings + RESTART TOS")

# Check 2: CLSID for RTD server
print("\n[2] Checking CLSID: {EC0E6191-DB51-11D3-8F3E-00C04F3651B8}")
rtd_clsid = "CLSID\\{EC0E6191-DB51-11D3-8F3E-00C04F3651B8}"
if check_registry_key(rtd_clsid):
    val = get_registry_value(rtd_clsid)
    print(f"    [OK] RTD CLSID registered -> {val}")
else:
    print("    [FAIL] RTD CLSID NOT registered")
    print("    FIX: Enable RTD in TOS Settings + RESTART TOS")

# Check 3: TypeLib GUID
print("\n[3] Checking TypeLib: {BA792DC8-807E-43E3-B484-47465D82C4D1}")
typelib_guid = "TypeLib\\{BA792DC8-807E-43E3-B484-47465D82C4D1}"
if check_registry_key(typelib_guid):
    val = get_registry_value(typelib_guid)
    print(f"    [OK] TypeLib registered -> {val}")
else:
    print("    [FAIL] TypeLib NOT registered")
    print("    FIX: Enable RTD in TOS Settings + RESTART TOS")

# Check 4: Try to create COM object
print("\n[4] Attempting to create RTD COM object")
try:
    from comtypes.client import CreateObject
    from scripts.streaming.options.tos_rtd.settings import SETTINGS
    
    print(f"    Creating COM object with ProgID: {SETTINGS.progid}")
    obj = CreateObject(SETTINGS.progid, dynamic=True)
    print("    [OK] COM object created successfully!")
    print(f"    Type: {type(obj)}")
    
    # Try to call ServerStart (this will fail if TOS not running, but proves registration)
    print("\n[5] Checking if TOS RTD server responds...")
    try:
        # We can't actually start without a proper IRTDUpdateEvent callback,
        # but we can check if the object has the right methods
        methods = [m for m in dir(obj) if not m.startswith('_')]
        expected_methods = ['ServerStart', 'ConnectData', 'RefreshData', 'DisconnectData', 'Heartbeat']
        found_methods = [m for m in expected_methods if m in methods]
        print(f"    Found RTD methods: {found_methods}")
        
        if len(found_methods) == len(expected_methods):
            print("    [OK] All expected RTD methods available")
            print("\n==> RTD IS READY!")
        else:
            print(f"    [WARN] Missing methods: {set(expected_methods) - set(found_methods)}")
    except Exception as e:
        print(f"    Note: {e}")
        
except ImportError as e:
    print(f"    [FAIL] Cannot import comtypes: {e}")
    print("    FIX: pip install comtypes")
except FileNotFoundError:
    print(f"    [FAIL] RTD COM object NOT found")
    print("    FIX: Enable RTD in TOS Settings + RESTART TOS")
except Exception as e:
    print(f"    [WARN] Error creating COM object: {e}")
    print("    This might be OK if TOS is not running, but check above for registry issues")

print("\n" + "=" * 70)
print("Summary:")
print("  If you see [OK] for checks 1-3 and can create the COM object,")
print("  then RTD is properly registered and ready to use.")
print("\n  If not, follow these steps:")
print("  1. Open ThinkorSwim")
print("  2. Settings -> Application API -> RTD Server")
print("  3. Check 'Enable RTD Server'")
print("  4. RESTART ThinkorSwim (critical!)")
print("  5. Run this script again")
print("=" * 70)

