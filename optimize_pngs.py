import os
from PIL import Image

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

def walk_and_optimize(base_dir):
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith('.png'):
                full_path = os.path.join(root, file)
                optimize_png(full_path)

if __name__ == '__main__':
    walk_and_optimize(BASE_DIR)
