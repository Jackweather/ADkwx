import os

base_dir = '/var/data'  # the root directory to search

png_folders = []

for root, dirs, files in os.walk(base_dir):
    if any(f.endswith('.png') for f in files):
        png_folders.append(root)

if png_folders:
    print("Folders containing PNGs:")
    for folder in png_folders:
        print(folder)
else:
    print("No PNGs found under", base_dir)
