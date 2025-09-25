import os
import requests
from datetime import datetime, timedelta
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

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files and pngs directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "THICKNESS", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "THICKNESS")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
thickness_dir = os.path.join(output_dir, "static", "THICKNESS")
grib_dir = os.path.join(thickness_dir, "grib_files")
png_dir = thickness_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS 0.25-degree URL and variables
base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_hgt = "HGT"

# Current UTC time minus 6 hours (nearest available GFS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps
forecast_steps = [0] + list(range(6, 385, 6))

# Download function

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

def get_thickness_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"thickness_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_1000_mb=on&lev_500_mb=on&var_{variable_hgt}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

# Plotting function

def plot_thickness(grib_path, step):
    try:
        ds = xr.open_dataset(grib_path, engine="cfgrib")
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None
    hgt_1000 = ds.sel(isobaricInhPa=1000)["gh"].values
    hgt_500 = ds.sel(isobaricInhPa=500)["gh"].values
    thickness = (hgt_500 - hgt_1000) / 10  # convert to dam
    lats = ds["latitude"].values
    lons = ds["longitude"].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    Lon2d, Lat2d = np.meshgrid(lons_plot, lats)

    # --- Basemap integration ---
    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    # --- Title block ---
    run_str = f"{hour_str}z"
    valid_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H") + timedelta(hours=step)
    hour_str_fmt = valid_time.strftime('%I%p').lstrip('0').lower()
    day_of_week = valid_time.strftime('%A')
    title_str = (
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"1000-500 hPa Thickness (dam)"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # --- Plot thickness ---
    levels = np.arange(500, 600, 6)  # dam units
    # Custom colormap: cool colors below/at 540, warm colors above
    colors = [
        '#08306b', '#2171b5', '#6baed6', '#b3cde3', '#a7e3e3',  # cool blues/cyans
        '#ffffff',  # neutral at 540
        '#ffe066', '#ffd700', '#ffa500', '#ff7f50', '#ff4500', '#d73027', '#a50026'  # warm yellows/oranges/reds
    ]
    # The color list should match the number of intervals
    cmap = LinearSegmentedColormap.from_list('thickness_cmap', colors, N=len(levels)-1)
    mesh = ax.contourf(Lon2d, Lat2d, thickness, levels=levels, cmap=cmap, extend='both', alpha=0.7)
    cs = ax.contour(Lon2d, Lat2d, thickness, levels=levels, colors='black', linewidths=0.5)
    ax.clabel(cs, fmt='%d', fontsize=7, colors='black', inline=True)

    # --- Colorbar ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom',
        ticks=levels, boundaries=levels
    )
    cbar.set_label("Thickness (dam)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    fig.text(0.99, 0.01, "adkwx.com", fontsize=10, color="black", ha="right", va="bottom", alpha=0.7, fontweight="bold")
    ax.set_axis_off()
    png_path = os.path.join(thickness_dir, f"thickness_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated thickness PNG: {png_path}")
    return png_path

# Main process
for step in forecast_steps:
    thickness_grib = get_thickness_grib(step)
    if thickness_grib:
        plot_thickness(thickness_grib, step)
        gc.collect()
        time.sleep(3)
        print("All thickness PNG creation tasks complete!")
        time.sleep(3)

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