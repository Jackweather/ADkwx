import os
from PIL import Image

# Define the source and destination folders
src_folder = os.path.join(os.path.dirname(__file__), '..', 'gfsmodel', 'GFS', 'static', 'PRATEGFS')
dst_gif = os.path.join(os.path.dirname(__file__), 'animation.gif')

# Get all PNG files and sort them
png_files = sorted(
    [f for f in os.listdir(src_folder) if f.endswith('.png')]
)

# Load images
images = [Image.open(os.path.join(src_folder, f)) for f in png_files]

# Save as GIF
if images:
    images[0].save(
        dst_gif,
        save_all=True,
        append_images=images[1:],
        duration=1300,  # ms per frame
        loop=0
    )
else:
    print("No PNG images found in source folder.")
