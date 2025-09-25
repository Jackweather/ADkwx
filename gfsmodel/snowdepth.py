import os
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

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files, pngs, and snow_depth directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "snow_depth", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "snow_depth")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
snow_depth_dir = os.path.join(output_dir, "static", "snow_depth")
grib_dir = os.path.join(snow_depth_dir, "grib_files")
png_dir = snow_depth_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_snod = "SNOD"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Snow depth colormap and levels (inches)
snow_breaks = [
    0, 0.1, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 16, 20, 24, 36, 48, 56
]
snow_colors = [
    "#ffffff",      # 0 (white, for no snow)
    "#0d1a4a",      # 0.1 dark blue
    "#1565c0",      # 1 lighter blue
    "#42a5f5",      # 2 lighter blue
    "#90caf9",      # 3 lighter blue
    "#e3f2fd",      # 4 lightest blue
    "#b39ddb",      # 5 light purple
    "#7e57c2",      # 6 medium purple
    "#512da8",      # 7 dark purple
    "#c2185b",      # 8 dark pink
    "#f06292",      # 10 light pink
    "#81c784",      # 12 light green
    "#388e3c",      # 16 medium green
    "#1b5e20",      # 20 dark green
    "#bdbdbd",      # 24 light gray
    "#757575",      # 36 medium gray
    "#212121",      # 48 dark gray
    "#000000",      # 56 black (for extreme snow)
]
snow_cmap = ListedColormap(snow_colors)
snow_norm = BoundaryNorm(snow_breaks, len(snow_colors))

def download_file(hour_str, step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, file_name)
    url_snod = (
        f"{base_url}"
        f"?dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{variable_snod}=on"
        f"&lev_surface=on"
    )
    response = requests.get(url_snod, stream=True)
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

def generate_clean_png(file_path, step, cumulative_snow):
    ds = xr.open_dataset(file_path, engine="cfgrib")
    snod_m = ds['sde'].values
    snod_in = snod_m * 39.3701

    # --- Only keep valid snow depth values ---
    snod_in = np.where((np.isnan(snod_in)) | (snod_in < 0) | (snod_in > 120), np.nan, snod_in)

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    # Updated map extent
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
    title_str = (
        f"Cumulative New Snow (inches)\n"
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # --- Plot cumulative new snow ---
    if 'latitude' in ds and 'longitude' in ds:
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        lons_plot = np.where(lons > 180, lons - 360, lons)
        if lats.ndim == 1 and lons.ndim == 1:
            Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
            data2d = cumulative_snow.squeeze()
        else:
            Lon2d, Lat2d = lons_plot, lats
            data2d = cumulative_snow.squeeze()
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

        # --- Add 2-degree grid with snow depth numbers ---
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
            cumulative_snow.squeeze(),
            cmap=snow_cmap,
            norm=snow_norm,
            extent=leaflet_extent,
            origin='lower',
            interpolation='bilinear',
            aspect='auto',
            transform=ccrs.PlateCarree()
        )

    # --- Add colorbar below plot ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.08)
    # Show a tick for each level
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.08, aspect=35, shrink=0.85, fraction=0.08,
        anchor=(0.5, 0.0), location='bottom',
        ticks=snow_breaks, boundaries=snow_breaks
    )
    cbar.set_label("Cumulative New Snow (inches)", fontsize=12)
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
    png_path = os.path.join(png_dir, f"snowdepth_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated clean PNG: {png_path}")
    return png_path

# Main process: Download and plot cumulative new snow
forecast_steps = list(range(0, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)

prev_snow = None
cumulative_snow = None

for idx, step in enumerate(forecast_steps):
    grib_file = download_file(hour_str, step)
    if grib_file:
        ds = xr.open_dataset(grib_file, engine="cfgrib")
        snod_m = ds['sde'].values
        snod_in = snod_m * 39.3701
        snod_in = np.where((np.isnan(snod_in)) | (snod_in < 0) | (snod_in > 120), np.nan, snod_in)

        if prev_snow is None:
            cumulative_snow = np.copy(snod_in)
        else:
            # Only add positive changes
            diff = snod_in - prev_snow
            diff = np.where(diff > 0, diff, 0)
            cumulative_snow = np.where(np.isnan(cumulative_snow), 0, cumulative_snow) + diff

        prev_snow = np.copy(snod_in)
        generate_clean_png(grib_file, step, cumulative_snow)
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
