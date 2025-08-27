import os
from PIL import Image, ImageFile
import psutil

ImageFile.LOAD_TRUNCATED_IMAGES = True

# Maximum size for GIF frames (reduce memory usage)
MAX_SIZE = (1024, 768)

def memory_usage():
    """Return current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def create_gif_from_folder(src_folder):
    """Create a GIF from all PNGs in the given folder safely."""
    print(f"\n[DEBUG] Processing folder: {src_folder}")
    
    if not os.path.exists(src_folder):
        print(f"[DEBUG] Folder does not exist, skipping: {src_folder}")
        return

    # Collect PNG files
    png_files = sorted([f for f in os.listdir(src_folder) if f.endswith('.png')])
    print(f"[DEBUG] Found {len(png_files)} PNG files in {src_folder}")
    
    if not png_files:
        print(f"[DEBUG] No PNG images found in folder: {src_folder}")
        return

    # Open first image
    first_image_path = os.path.join(src_folder, png_files[0])
    first_image = Image.open(first_image_path)
    first_image.thumbnail(MAX_SIZE)  # Resize to reduce memory usage
    print(f"[DEBUG] Opened first image: {first_image_path}")
    print(f"[DEBUG] Current memory usage: {memory_usage():.2f} MB")

    # Generator to open and resize subsequent images one by one
    def image_generator():
        for f in png_files[1:]:
            img_path = os.path.join(src_folder, f)
            with Image.open(img_path) as img:
                img.thumbnail(MAX_SIZE)
                yield img.copy()  # copy to avoid closing the image

    # Destination GIF path
    folder_name = os.path.basename(src_folder.rstrip('/'))
    dst_gif = os.path.join('/var/data', f'{folder_name}.gif')

    # Save GIF
    print(f"[DEBUG] Creating GIF: {dst_gif}")
    first_image.save(
        dst_gif,
        save_all=True,
        append_images=image_generator(),
        duration=1300,  # ms per frame
        loop=0
    )
    print(f"[DEBUG] Finished GIF: {dst_gif}")
    print(f"[DEBUG] Current memory usage after GIF: {memory_usage():.2f} MB")


# --- Main process ---
BASE_DIR = '/var/data'

print("[DEBUG] Searching for folders containing PNGs...")
# Automatically find all folders containing PNGs
png_folders = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(f.endswith('.png') for f in files):
        png_folders.append(root)

print(f"[DEBUG] Found {len(png_folders)} folders with PNGs:")
for f in png_folders:
    print(f"  - {f}")

# Create GIFs for each folder
for folder in png_folders:
    create_gif_from_folder(folder)

print("[DEBUG] All GIF creation tasks complete!")
