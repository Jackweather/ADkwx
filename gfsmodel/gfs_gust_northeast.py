import importlib
import os
import cartopy
from filelock import FileLock
import requests
from datetime import datetime, timedelta
import pytz
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
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
lock = FileLock(os.path.join(cartopy.config['data_dir'], 'cartopy.lock20'))
with lock:
    # import modules while holding the lock so only one process fetches data files
    shpreader = importlib.import_module('cartopy.io.shapereader')
    cfeature = importlib.import_module('cartopy.feature')

BASE_DIR = '/var/data'
gust_dir = os.path.join(BASE_DIR, "GDAS", "static", "GUST_NE")
grib_dir = os.path.join(gust_dir, "grib_files")
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(gust_dir, exist_ok=True)

# GFS 0.25-degree URL and variables
base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_gust = "GUST"

# Current UTC time minus 6 hours (nearest available GDAS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps (every 6 hours up to 384, like total_precip)
forecast_steps = list(range(0, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)

def download_grib(url, file_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {os.path.basename(file_path)}")
        return file_path
    else:
        print(f"Failed to download {os.path.basename(file_path)} (Status Code: {response.status_code})")
        return None

def get_gust_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"gust_surface_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_gust}=on"
        f"&subregion=&leftlon=280&rightlon=295&toplat=47&bottomlat=37"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

# Gust colormap and levels (custom, similar to total precip style, in m/s)
gust_breaks = [
    0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 45, 50
]
gust_colors = [
    "#ffffff", "#e3f2fd", "#bbdefb", "#90caf9", "#64b5f6", "#42a5f5", "#2196f3", "#1e88e5",
    "#43a047", "#388e3c", "#2e7d32", "#fbc02d", "#f9a825", "#f57c00", "#ef6c00", "#e65100",
    "#e53935", "#b71c1c", "#c62828", "#ad1457", "#6a1b9a", "#7b1fa2", "#212121"
]
gust_cmap = LinearSegmentedColormap.from_list("gust_cmap", gust_colors, N=len(gust_colors))
gust_norm = BoundaryNorm(gust_breaks, len(gust_colors))

def plot_gust_surface(grib_path, step):
    try:
        ds = xr.open_dataset(grib_path, engine="cfgrib")
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None

    gust = ds['gust'].values.squeeze()
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        gust2d = gust
    else:
        Lon2d, Lat2d = lons_plot, lats
        gust2d = gust

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-82, -66, 38, 48]  # Northeast US
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 7}
    gl.ylabel_style = {'size': 7}
    gl.xlocator = plt.MaxNLocator(6)
    gl.ylocator = plt.MaxNLocator(5)

    mesh = ax.contourf(
        Lon2d, Lat2d, gust2d,
        levels=gust_breaks,
        cmap=gust_cmap,
        norm=gust_norm,
        extend='max',
        transform=ccrs.PlateCarree(),
        alpha=0.75,
        zorder=2
    )

    # --- Add 1-degree grid with gust numbers ---
    for lat in range(int(extent[2]), int(extent[3]) + 1):
        for lon in range(int(extent[0]), int(extent[1]) + 1):
            iy = np.abs(lats - lat).argmin() if lats.ndim == 1 else np.abs(lats[:,0] - lat).argmin()
            ix = np.abs(lons_plot - lon).argmin() if lons_plot.ndim == 1 else np.abs(lons_plot[0,:] - lon).argmin()
            gust_val = gust2d[iy, ix]
            if not np.isnan(gust_val):
                ax.text(
                    lon, lat, f"{int(round(gust_val))}",
                    color='black', fontsize=5, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(),
                    zorder=10
                )

    run_str = f"{hour_str}z"
    valid_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H") + timedelta(hours=step)
    init_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H")
    utc = pytz.utc
    eastern = pytz.timezone('US/Eastern')
    valid_time_utc = utc.localize(valid_time)
    valid_time_est = valid_time_utc.astimezone(eastern)
    title_str = (
        f"GFS 0.25° | Surface Wind Gust (m/s)\n"
        f"Valid: {valid_time_est:%Y-%m-%d %I:%M %p %Z}  |  "
        f"Init: {init_time:%Y-%m-%d %H:%M UTC}  |  Forecast Hour: {step:03d}  |  Run: {run_str}"
    )
    plt.title(title_str, fontsize=11, fontweight='bold', y=1.01, loc='left')

    plt.subplots_adjust(left=0.05, right=0.95, top=0.93, bottom=0.18, hspace=0)

    cax = fig.add_axes([0.13, 0.13, 0.74, 0.025])
    cbar = plt.colorbar(mesh, cax=cax, orientation='horizontal', ticks=gust_breaks)
    cbar.set_label("Surface Wind Gust (m/s)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')
    for label in cbar.ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha('right')

    ax.set_axis_off()
    png_path = os.path.join(gust_dir, f"gust_surface_gfs_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0.05, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated Gust Surface PNG: {png_path}")
    return png_path

def optimize_png(filepath):
    try:
        with Image.open(filepath) as img:
            img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
            img.save(filepath, optimize=True)
            print(f"Optimized PNG: {filepath}")
    except Exception as e:
        print(f"Failed to optimize {filepath}: {e}")

# Main process
for step in forecast_steps:
    gust_grib = get_gust_grib(step)
    if gust_grib:
        plot_gust_surface(gust_grib, step)
        gc.collect()
        time.sleep(1)

# Delete all GRIB files after PNGs are made
for f in os.listdir(grib_dir):
    file_path = os.path.join(grib_dir, f)
    if os.path.isfile(file_path):
        os.remove(file_path)
        gc.collect()
        time.sleep(1)

# Optimize PNGs
for f in os.listdir(gust_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(gust_dir, f))

print("All GDAS Gust PNGs optimized.")
