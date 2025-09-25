import os
import requests
from datetime import datetime, timedelta
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import time
import gc
from PIL import Image

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files, pngs, and crain_surface directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "crain_surface", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "crain_surface")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
crain_surface_dir = os.path.join(output_dir, "static", "crain_surface")
grib_dir = os.path.join(crain_surface_dir, "grib_files")
png_dir = crain_surface_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_crain = "CRAIN"
variable_csnow = "CSNOW"

# Use current UTC time minus 6 hours for best available run
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps (same as temp)
forecast_steps = list(range(6, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)

def download_file(hour_str, step):
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, file_name)
    url_vars = f"&lev_surface=on&var_{variable_crain}=on&var_{variable_csnow}=on"
    url = (
        f"{base_url}?file={file_name}"
        f"{url_vars}"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {file_name}")
        return file_path
    else:
        print(f"Failed to download {file_name} (Status Code: {response.status_code})")
        return None

def generate_clean_png(file_path, step):
    try:
        ds = xr.open_dataset(file_path, engine="cfgrib", filter_by_keys={'stepType': 'instant'})
    except Exception as e:
        print(f"Failed to open dataset with 'stepType=instant': {e}")
        return

    if 'crain' not in ds:
        print(f"'crain' variable not found in {file_path}")
        return

    # --- Extract rain and snow ---
    data_rain = ds['crain'].values  # 0 = no rain, 1 = rain
    data_snow = ds['csnow'].values if 'csnow' in ds else None  # 0 = no snow, 1 = snow

    # --- Combine into a single mask: 0=none, 1=rain, 2=snow (snow wins if both) ---
    if data_snow is not None:
        mask = np.zeros_like(data_rain)
        mask[(data_rain == 1) & (data_snow != 1)] = 1  # rain only
        mask[data_snow == 1] = 2  # snow (overrides rain if both)
    else:
        mask = (data_rain == 1).astype(int)  # only rain

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    margin = 1.0  # degrees margin to avoid plotting on the very edge

    # --- Title block (same logic as mslp_prate.py) ---
    run_hour_map = {
        "00": 20,  # 00z run: f000 = 8pm previous day
        "06": 2,   # 06z run: f000 = 2am
        "12": 8,   # 12z run: f000 = 8am
        "18": 14   # 18z run: f000 = 2pm
    }
    base_hour = run_hour_map.get(hour_str, 8)
    base_time = datetime.strptime(date_str + f"{base_hour:02d}", "%Y%m%d%H")
    valid_time = base_time + timedelta(hours=step)
    hour_str_fmt = valid_time.strftime('%I%p').lstrip('0').lower()
    day_of_week = valid_time.strftime('%A')
    run_str = f"{hour_str}z"
    title_str = (
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"Categorical Rain (surface)"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # --- Basemap features (match mslp_prate.py) ---
    ax.add_feature(cfeature.LAND, facecolor='white')  # changed from 'lightgray' to 'white'
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)
    # --- End basemap features ---

    # --- Plot only green (rain) or blue (snow), never both, no other color ---
    from matplotlib.colors import ListedColormap
    rain_snow_cmap = ListedColormap(['none', '#19a319', '#1e90ff'])  # 0: transparent, 1: green, 2: blue
    rain_snow_levels = [-0.5, 0.5, 1.5, 2.5]

    if 'latitude' in ds and 'longitude' in ds:
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        lons_plot = np.where(lons > 180, lons - 360, lons)
        if lats.ndim == 1 and lons.ndim == 1:
            Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
            mask2d = mask.squeeze()
        else:
            Lon2d, Lat2d = lons_plot, lats
            mask2d = mask.squeeze()
        ax.contourf(
            Lon2d, Lat2d, mask2d,
            levels=rain_snow_levels,
            cmap=rain_snow_cmap,
            extend='neither',
            transform=ccrs.PlateCarree(),
            alpha=0.8,
            zorder=2,
            edgecolors='face'
        )
    else:
        leaflet_extent = extent
        ax.imshow(
            mask.squeeze(),
            cmap=rain_snow_cmap,
            extent=leaflet_extent,
            origin='lower',
            interpolation='nearest',
            aspect='auto',
            transform=ccrs.PlateCarree(),
            alpha=0.8,
            zorder=2
        )

    # --- No colorbar ---

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"crain_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated clean PNG: {png_path}")
    return png_path

# Main process: Download and plot
for step in forecast_steps:
    grib_file = download_file(hour_str, step)
    if grib_file:
        generate_clean_png(grib_file, step)
        gc.collect()
        time.sleep(3)

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
