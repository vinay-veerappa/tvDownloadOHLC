import glob

injection = '{"$mid":24,"mimeType":"cache_control","data":"ZXBoZW1lcmFs"}'
count = 0
for fpath in glob.glob('web/**/*.{ts,tsx}', recursive=True):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    if injection in content:
        content = content.replace(injection, '')
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Cleaned {fpath}')
        count += 1

for fpath in glob.glob('api/**/*.py', recursive=True):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    if injection in content:
        content = content.replace(injection, '')
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Cleaned {fpath}')
        count += 1

print(f'Done. Cleaned {count} files')
