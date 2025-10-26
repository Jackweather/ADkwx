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
from matplotlib.colors import ListedColormap, BoundaryNorm
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
lock = FileLock(os.path.join(cartopy.config['data_dir'], 'cartopy.lock8'))
with lock:
    # import modules while holding the lock so only one process fetches data files
    shpreader = importlib.import_module('cartopy.io.shapereader')
    cfeature = importlib.import_module('cartopy.feature')

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files, pngs, and totalsnowfall directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "totalsnowfall_3to1", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "totalsnowfall_3to1")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
totalsnowfall_dir = os.path.join(output_dir, "static", "totalsnowfall_3to1")
grib_dir = os.path.join(totalsnowfall_dir, "grib_files")
png_dir = totalsnowfall_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_weasd = "WEASD"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Snowfall colormap and levels (inches, 3:1 ratio)
snow_breaks = [
    0, 0.1, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 16, 20, 24, 36, 48, 56
]
snow_colors = [
    "#ffffff", "#0d1a4a", "#1565c0", "#42a5f5", "#90caf9", "#e3f2fd",
    "#b39ddb", "#7e57c2", "#512da8", "#c2185b", "#f06292", "#81c784",
    "#388e3c", "#1b5e20", "#bdbdbd", "#757575", "#212121", "#000000"
]
snow_cmap = ListedColormap(snow_colors)
snow_norm = BoundaryNorm(snow_breaks, len(snow_colors))

def download_file(hour_str, step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, file_name)
    url_weasd = (
        f"{base_url}"
        f"?dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{variable_weasd}=on"
        f"&lev_surface=on"
    )
    response = requests.get(url_weasd, stream=True)
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

def generate_clean_png(file_path, step, snowfall_in):
    ds = xr.open_dataset(file_path, engine="cfgrib")
    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent_left, extent_right, extent_bottom, extent_top = -130, -65, 20, 54
    ax.set_extent([extent_left, extent_right, extent_bottom, extent_top], crs=ccrs.PlateCarree())

    # --- Add map features ---
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    # --- Title block ---
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
    # Add extra title line above main title
    plt.title(
        "Above 32°F: Heavy slushy snow\n"
        f"Total Snowfall (inches, 3:1 ratio)\n"
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}",
        fontsize=12, fontweight='bold', y=1.07
    )

    # --- Plot total snowfall ---
    if 'latitude' in ds and 'longitude' in ds:
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        lons_plot = np.where(lons > 180, lons - 360, lons)
        if lats.ndim == 1 and lons.ndim == 1:
            Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
            data2d = snowfall_in.squeeze()
        else:
            Lon2d, Lat2d = lons_plot, lats
            data2d = snowfall_in.squeeze()
        mask_extent = (
            (Lat2d >= extent_bottom) & (Lat2d <= extent_top) &
            (Lon2d >= extent_left) & (Lon2d <= extent_right)
        )
        data2d = np.where(mask_extent, data2d, np.nan)
        mesh = ax.contourf(
            Lon2d, Lat2d, data2d,
            levels=snow_breaks,
            cmap=snow_cmap,
            norm=snow_norm,
            extend='max',
            transform=ccrs.PlateCarree()
        )

        # --- Add 2-degree grid with snowfall numbers ---
        for lat in range(int(extent_bottom), int(extent_top) + 1, 2):
            for lon in range(int(extent_left), int(extent_right) + 1, 2):
                iy = np.abs(lats - lat).argmin() if lats.ndim == 1 else np.abs(lats[:,0] - lat).argmin()
                ix = np.abs(lons_plot - lon).argmin() if lons_plot.ndim == 1 else np.abs(lons_plot[0,:] - lon).argmin()
                snow_val = data2d[iy, ix]
                if not np.isnan(snow_val):
                    if snow_val == 0:
                        label = "0"
                    elif snow_val < 1:
                        label = f".{int(round(snow_val * 100)):02d}"
                    else:
                        label = f"{snow_val:.2f}"
                    ax.text(
                        lon, lat, label,
                        color='black', fontsize=4, fontweight='bold',
                        ha='center', va='center', transform=ccrs.PlateCarree(),
                        zorder=10
                    )
    else:
        mesh = ax.imshow(
            snowfall_in.squeeze(),
            cmap=snow_cmap,
            norm=snow_norm,
            extent=[extent_left, extent_right, extent_bottom, extent_top],
            origin='lower',
            interpolation='bilinear',
            aspect='auto',
            transform=ccrs.PlateCarree()
        )

    # --- Add colorbar below plot ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.08)
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.08, aspect=35, shrink=0.85, fraction=0.08,
        anchor=(0.5, 0.0), location='bottom',
        ticks=snow_breaks, boundaries=snow_breaks
    )
    cbar.set_label("Total Snowfall (inches, 3:1 ratio)", fontsize=12)
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
    png_path = os.path.join(png_dir, f"totalsnowfall_3to1_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated clean PNG: {png_path}")
    return png_path

# Main process: Download and plot total snowfall (3:1 ratio)
forecast_steps = list(range(0, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)

prev_weasd = None
cumulative_snowfall = None

for idx, step in enumerate(forecast_steps):
    grib_file = download_file(hour_str, step)
    if grib_file:
        ds = xr.open_dataset(grib_file, engine="cfgrib")
        weasd_kgm2 = ds['sdwe'].values  # use 'weasd'
        # Convert WEASD (kg/m^2) to inches of snow (3:1 ratio)
        snowfall_in = weasd_kgm2 * 0.0393701 * 3
        snowfall_in = np.where((np.isnan(snowfall_in)) | (snowfall_in < 0) | (snowfall_in > 120), np.nan, snowfall_in)

        if prev_weasd is None:
            cumulative_snowfall = np.copy(snowfall_in)
        else:
            # Only add positive increments
            diff = snowfall_in - prev_weasd
            diff = np.where(diff > 0, diff, 0)
            cumulative_snowfall = np.where(np.isnan(cumulative_snowfall), 0, cumulative_snowfall) + diff

        prev_weasd = np.copy(snowfall_in)
        generate_clean_png(grib_file, step, cumulative_snowfall)
        gc.collect()
        time.sleep(1)

print("All GRIB file download and PNG creation tasks complete!")

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
