import os
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

def create_gif_from_folder(src_folder):
    """Create a GIF from all PNGs in the given folder."""
    if not os.path.exists(src_folder):
        print(f"Folder does not exist, skipping: {src_folder}")
        return

    png_files = sorted([f for f in os.listdir(src_folder) if f.endswith('.png')])
    if not png_files:
        print(f"No PNG images found in folder: {src_folder}")
        return

    images = [Image.open(os.path.join(src_folder, f)) for f in png_files]
    folder_name = os.path.basename(src_folder.rstrip('/'))
    dst_gif = os.path.join('/var/data', f'{folder_name}.gif')

    images[0].save(
        dst_gif,
        save_all=True,
        append_images=images[1:],
        duration=1300,  # ms per frame
        loop=0
    )
    print(f"Created GIF: {dst_gif}")


# Base directory where all PNGs are located
base_static = '/var/data'

# Automatically find all subfolders under /var/data
for root, dirs, files in os.walk(base_static):
    if any(f.endswith('.png') for f in files):
        create_gif_from_folder(root)
