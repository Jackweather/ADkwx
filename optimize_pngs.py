import os
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = '/var/data'

def optimize_png(filepath):
    try:
        with Image.open(filepath) as img:
            # Convert to palette mode for further compression (optional, comment out if not desired)
            img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
            img.save(filepath, optimize=True)
            print(f"Optimized: {filepath}")
    except Exception as e:
        print(f"Failed to optimize {filepath}: {e}")

def walk_and_optimize(base_dir, max_workers=8):
    png_files = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith('.png'):
                png_files.append(os.path.join(root, file))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(optimize_png, png_files)

if __name__ == '__main__':
    walk_and_optimize(BASE_DIR)
