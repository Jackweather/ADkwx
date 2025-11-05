import importlib
import os
import cartopy
from filelock import FileLock
import requests
from datetime import datetime, timedelta
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import time
import gc
from PIL import Image

# Ensure a stable cartopy data directory and create it
cartopy.config['data_dir'] = '/opt/render/project/src/cartopy_data'
os.makedirs(cartopy.config['data_dir'], exist_ok=True)

# Use a file lock so only one process downloads Cartopy data at a time.
# Other processes wait until the lock is released.
lock = FileLock(os.path.join(cartopy.config['data_dir'], 'cartopy.lock6'))
with lock:
    # import modules while holding the lock so only one process fetches data files
    shpreader = importlib.import_module('cartopy.io.shapereader')
    cfeature = importlib.import_module('cartopy.feature')

BASE_DIR = '/var/data'

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
total_lcdc_dir = os.path.join(output_dir, "static", "total_lcdc")
grib_dir = os.path.join(total_lcdc_dir, "grib_files")
png_dir = total_lcdc_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_lcdc = "TCDC"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

def custom_lcdc_colormap():
    return LinearSegmentedColormap.from_list(
        "LCDC_BlueToWhite",
        [
            (0.0, "#00008b"),
            (0.5, "#4169e1"),
            (0.75, "#87ceeb"),
            (1.0, "#ffffff"),
        ],
        N=256
    )

lcdc_cmap = custom_lcdc_colormap()
lcdc_levels = np.linspace(0, 100, 21)  # 0 to 100 percent

def download_file(hour_str, step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, file_name)
    url_lcdc = (
        f"{base_url}"
        f"?dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{variable_lcdc}=on"
        f"&lev_entire_atmosphere=on"
    )
    response = requests.get(url_lcdc, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(file_path) < 10240:
            print(f"Downloaded {file_name} but file is too small (likely empty or error page).")
            os.remove(file_path)
            return None
        print(f"Downloaded {file_name}")
        return file_path
    else:
        print(f"Failed to download {file_name} (Status Code: {response.status_code})")
        return None

def plot_total_lcdc(lcdc_percent, lats, lons, step):
    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent_left, extent_right, extent_bottom, extent_top = -126, -69, 24, 50
    ax.set_extent([extent_left, extent_right, extent_bottom, extent_top], crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    run_hour_map = {
        "00": 20,
        "06": 2,
        "12": 8,
        "18": 14
    }
    base_hour = run_hour_map.get(hour_str, 8)
    base_time = datetime.strptime(date_str + f"{base_hour:02d}", "%Y%m%d%H")
    valid_time = base_time + timedelta(hours=step)
    hour_str_fmt = valid_time.strftime('%I%p').lstrip('0').lower()
    day_of_week = valid_time.strftime('%A')
    run_str = f"{hour_str}z"
    title_str = (
        f"Total Cloud Cover (%)\n"
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        data2d = lcdc_percent.squeeze()
    else:
        Lon2d, Lat2d = lons_plot, lats
        data2d = lcdc_percent.squeeze()
    mask_extent = (
        (Lat2d >= extent_bottom) & (Lat2d <= extent_top) &
        (Lon2d >= extent_left) & (Lon2d <= extent_right)
    )
    data2d = np.where(mask_extent, data2d, np.nan)
    mesh = ax.contourf(
        Lon2d, Lat2d, data2d,
        levels=lcdc_levels,
        cmap=lcdc_cmap,
        extend='max',
        transform=ccrs.PlateCarree()
    )

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.08)
    tick_indices = list(range(0, len(lcdc_levels), 2))
    ticks_to_show = [lcdc_levels[i] for i in tick_indices]
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.08, aspect=35, shrink=0.85, fraction=0.08,
        anchor=(0.5, 0.0), location='bottom',
        ticks=ticks_to_show, boundaries=lcdc_levels
    )
    cbar.set_label("Low Cloud Cover (%)", fontsize=12)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')
    for label in cbar.ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha('right')

    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"total_lcdc_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated total LCDC PNG: {png_path}")
    return png_path

# Main process: Download and plot for each forecast hour
forecast_steps = list(range(0, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)

lats, lons = None, None

for step in forecast_steps:
    grib_file = download_file(hour_str, step)
    if grib_file:
        ds = xr.open_dataset(
            grib_file,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": {"stepType": "instant"}}
        )
        lcdc_percent = ds['tcc'].values
        lcdc_percent = np.clip(lcdc_percent, 0, 100)
        lcdc_percent = np.where(lcdc_percent == 0, np.nan, lcdc_percent)
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        plot_total_lcdc(lcdc_percent, lats, lons, step)
        gc.collect()
        time.sleep(0)

print("All GRIB file download and total LCDC PNG creation tasks complete!")

# --- Delete all GRIB files in grib_dir after PNGs are made ---
for f in os.listdir(grib_dir):
    file_path = os.path.join(grib_dir, f)
    if os.path.isfile(file_path):
        os.remove(file_path)
print("All GRIB files deleted from grib_dir.")

# --- Optimize all PNGs in the output directory ---
def optimize_png(filepath):
    try:
        with Image.open(filepath) as img:
            img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
            img.save(filepath, optimize=True)
            print(f"Optimized PNG: {filepath}")
    except Exception as e:
        print(f"Failed to optimize {filepath}: {e}")

for f in os.listdir(png_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(png_dir, f))

print("All PNGs optimized.")

