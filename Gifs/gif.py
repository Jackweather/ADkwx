import os
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

def create_gif_from_folder(src_folder):
    folder_name = os.path.basename(src_folder)
    dst_gif = os.path.join(os.path.dirname(__file__), f'{folder_name}.gif')
    png_files = sorted(
        [f for f in os.listdir(src_folder) if f.endswith('.png')]
    )
    images = [Image.open(os.path.join(src_folder, f)) for f in png_files]
    if images:
        images[0].save(
            dst_gif,
            save_all=True,
            append_images=images[1:],
            duration=1300,  # ms per frame
            loop=0
        )
    else:
        print(f"No PNG images found in source folder: {src_folder}")

base_static = os.path.join(os.path.dirname(__file__), '..', 'gfsmodel', 'GFS', 'static')

folders = [
    'PRATEGFS',
    'tmp_surface',
    '6hour_precip_total',
    '24hour_precip_total',
    '12hour_precip_total',
    'total_precip'
]

for folder in folders:
    src_folder = os.path.join(base_static, folder)
    create_gif_from_folder(src_folder)
