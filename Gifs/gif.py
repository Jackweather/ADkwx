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


# List of folders that actually contain PNGs (from your find.py results)
folders = [
    '/var/data/GFS/static/24hour_precip_total',
    '/var/data/GFS/static/total_precip',
    '/var/data/GFS/static/6hour_precip_total',
    '/var/data/GFS/static/PRATEGFS',
    '/var/data/GFS/static/12hour_precip_total',
    '/var/data/GFS/static/tmp_surface',
    '/var/data/GFS/static/total_lcdc'
]

# Create GIFs for each folder
for folder in folders:
    create_gif_from_folder(folder)
