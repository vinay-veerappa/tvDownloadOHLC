import winreg

# Check ProgID
key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'Tos.RTD')
val, _ = winreg.QueryValueEx(key, '')
print(f'Tos.RTD CLSID: {val}')

# Check if it's a real GUID or still just "Tos.RTD"
if val.startswith('{') and len(val) == 38:
    print('  -> Valid GUID detected')
    # Check the CLSID registry
    try:
        clsid_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f'CLSID\\{val}')
        clsid_val, _ = winreg.QueryValueEx(clsid_key, '')
        print(f'  -> Server: {clsid_val}')
        # Check LocalServer32
        try:
            sub = winreg.OpenKey(clsid_key, 'LocalServer32')
            ls, _ = winreg.QueryValueEx(sub, '')
            print(f'  -> LocalServer32: {ls}')
        except FileNotFoundError:
            print('  -> No LocalServer32 (InProcServer32 only?)')
        try:
            sub = winreg.OpenKey(clsid_key, 'InProcServer32')
            ip, _ = winreg.QueryValueEx(sub, '')
            print(f'  -> InProcServer32: {ip}')
        except FileNotFoundError:
            print('  -> No InProcServer32')
    except FileNotFoundError:
        print('  -> CLSID not found in registry')
else:
    print(f'  -> NOT a valid GUID (value is "{val}")')
    print('  -> TOS RTD COM server is NOT properly registered')
    print('  -> Try checking ProgID variants...')

# Also check for the expected GUID directly
expected_guid = '{EC0E6191-DB51-11D3-8F3E-00C04F3651B8}'
try:
    clsid_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f'CLSID\\{expected_guid}')
    clsid_val, _ = winreg.QueryValueEx(clsid_key, '')
    print(f'\nExpected GUID {expected_guid} found: {clsid_val}')
except FileNotFoundError:
    print(f'\nExpected GUID {expected_guid} NOT in registry')