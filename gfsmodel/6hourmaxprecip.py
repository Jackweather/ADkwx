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
lock = FileLock(os.path.join(cartopy.config['data_dir'], 'cartopy.lock2'))
with lock:
    # import modules while holding the lock so only one process fetches data files
    shpreader = importlib.import_module('cartopy.io.shapereader')
    cfeature = importlib.import_module('cartopy.feature')

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files, pngs, and 6hour_precip_total directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "6hour_precip_total", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "6hour_precip_total")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
precip_total_dir = os.path.join(output_dir, "static", "6hour_precip_total")
grib_dir = os.path.join(precip_total_dir, "grib_files")
png_dir = precip_total_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_apcp = "APCP"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Precipitation colormap and levels (inches, similar to NBM)
precip_breaks = [
    0, 0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2,
    2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.6, 7, 8, 9, 10, 12, 14, 16, 20, 24
]
precip_colors = [
    "#ffffff", "#e3f2fd", "#bbdefb", "#90caf9", "#64b5f6", "#42a5f5", "#2196f3", "#1e88e5",
    "#1976d2", "#1565c0", "#0d47a1", "#43a047", "#388e3c", "#2e7d32", "#fbc02d", "#f9a825",
    "#f57c00", "#ef6c00", "#e65100", "#e53935", "#b71c1c", "#c62828", "#ad1457", "#6a1b9a",
    "#7b1fa2", "#8e24aa", "#9c27b0", "#6d4c41", "#795548", "#a1887f", "#bcaaa4", "#212121", "#fff59d"
]
precip_cmap = ListedColormap(precip_colors)
precip_norm = BoundaryNorm(precip_breaks, len(precip_colors))

def download_file(hour_str, step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, file_name)
    url_apcp = (
        f"{base_url}"
        f"?dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{variable_apcp}=on"
        f"&lev_surface=on"
    )
    response = requests.get(url_apcp, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        # Check file size
        if os.path.getsize(file_path) < 10240:  # less than 10KB
            print(f"Downloaded {file_name} but file is too small (likely empty or error page).")
            os.remove(file_path)
            return None
        print(f"Downloaded {file_name}")
        return file_path
    else:
        print(f"Failed to download {file_name} (Status Code: {response.status_code})")
        return None

def generate_clean_png(file_path, step):
    ds = xr.open_dataset(file_path, engine="cfgrib")
    # APCP is in kg/m^2, which is equivalent to mm. Convert mm to inches.
    apcp_mm = ds['tp'].values
    apcp_in = apcp_mm / 25.4

    # --- Remove random data beams: mask invalid/extreme values ---
    apcp_in = np.where(
        (np.isnan(apcp_in)) | (apcp_in < 0) | (apcp_in > 50),
        np.nan,
        apcp_in
    )

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    # Set desired map extent
    extent_left, extent_right, extent_bottom, extent_top = -126, -69, 24, 50
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
        f"6 Hour Maximum Total Precipitation\n"
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # --- Plot precipitation ---
    if 'latitude' in ds and 'longitude' in ds:
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        lons_plot = np.where(lons > 180, lons - 360, lons)
        if lats.ndim == 1 and lons.ndim == 1:
            Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
            data2d = apcp_in.squeeze()
        else:
            Lon2d, Lat2d = lons_plot, lats
            data2d = apcp_in.squeeze()
        # Mask out data outside the plotting extent
        mask_extent = (
            (Lat2d >= extent_bottom) & (Lat2d <= extent_top) &
            (Lon2d >= extent_left) & (Lon2d <= extent_right)
        )
        data2d = np.where(mask_extent, data2d, np.nan)
        # Plot with extent matching the map
        mesh = ax.contourf(
            Lon2d, Lat2d, data2d,
            levels=precip_breaks,
            cmap=precip_cmap,
            norm=precip_norm,
            extend='max',
            transform=ccrs.PlateCarree()
        )

        # --- Add 2-degree grid with precipitation numbers ---
        for lat in range(int(extent_bottom), int(extent_top) + 1, 2):
            for lon in range(int(extent_left), int(extent_right) + 1, 2):
                # Find nearest grid point
                iy = np.abs(lats - lat).argmin() if lats.ndim == 1 else np.abs(lats[:,0] - lat).argmin()
                ix = np.abs(lons_plot - lon).argmin() if lons_plot.ndim == 1 else np.abs(lons_plot[0,:] - lon).argmin()
                precip_val = data2d[iy, ix]
                if not np.isnan(precip_val):
                    # Show "0" if exactly zero, ".xx" if < 1, otherwise show with leading digit
                    if precip_val == 0:
                        label = "0"
                    elif precip_val < 1:
                        label = f".{int(round(precip_val * 100)):02d}"
                    else:
                        label = f"{precip_val:.2f}"
                    ax.text(
                        lon, lat, label,
                        color='black', fontsize=4, fontweight='bold',
                        ha='center', va='center', transform=ccrs.PlateCarree(),
                        zorder=10
                    )
    else:
        leaflet_extent = [extent_left, extent_right, extent_bottom, extent_top]
        mesh = ax.imshow(
            apcp_in.squeeze(),
            cmap=precip_cmap,
            norm=precip_norm,
            extent=leaflet_extent,
            origin='lower',
            interpolation='bilinear',
            aspect='auto',
            transform=ccrs.PlateCarree()
        )
        # No grid overlay for imshow fallback

    # --- Add colorbar below plot ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.08)  # Increase bottom margin for colorbar
    # Select fewer ticks for readability
    tick_indices = list(range(0, len(precip_breaks), 2))  # Show every other tick
    ticks_to_show = [precip_breaks[i] for i in tick_indices]
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.08, aspect=35, shrink=0.85, fraction=0.08,
        anchor=(0.5, 0.0), location='bottom',
        ticks=ticks_to_show, boundaries=precip_breaks
    )
    cbar.set_label("Precipitation (inches)", fontsize=12)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')
    # Rotate tick labels for readability
    for label in cbar.ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha('right')

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"precip6_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated clean PNG: {png_path}")
    return png_path

# Add Northeast precip PNG output directory (matches frontend)
northeast_precip_dir = os.path.join(BASE_DIR, "GFS", "static", "northeast_precip_pngs")
os.makedirs(northeast_precip_dir, exist_ok=True)

def generate_northeast_precip_png(file_path, step):
    ds = xr.open_dataset(file_path, engine="cfgrib")
    apcp_mm = ds['tp'].values
    apcp_in = apcp_mm / 25.4
    apcp_in = np.where(
        (np.isnan(apcp_in)) | (apcp_in < 0) | (apcp_in > 50),
        np.nan,
        apcp_in
    )
    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-82, -66, 38, 48]  # Northeast US
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # Always try to plot counties in the Northeast
    import cartopy.io.shapereader as shapereader
    county_shp = "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_county_20m.zip"
    try:
        counties = shapereader.Reader(county_shp)
        ax.add_geometries(counties.geometries(), ccrs.PlateCarree(), edgecolor="black", facecolor="none", linewidth=0.3)
    except Exception as e:
        print(f"Warning: Could not plot counties: {e}")

    # Add primary roads
    primary_shp = "https://www2.census.gov/geo/tiger/TIGER2018/PRIMARYROADS/tl_2018_us_primaryroads.zip"
    try:
        primary_roads = shapereader.Reader(primary_shp)
        ax.add_geometries(primary_roads.geometries(), ccrs.PlateCarree(), edgecolor="brown", facecolor="none", linewidth=1.2)
    except Exception as e:
        print(f"Could not load primary roads shapefile: {e}")

    # Basemap features
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    # Title block (same logic as USA)
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
        f"6 Hour Maximum Total Precipitation\n"
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # Plot precipitation
    if 'latitude' in ds and 'longitude' in ds:
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        lons_plot = np.where(lons > 180, lons - 360, lons)
        if lats.ndim == 1 and lons.ndim == 1:
            Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
            data2d = apcp_in.squeeze()
        else:
            Lon2d, Lat2d = lons_plot, lats
            data2d = apcp_in.squeeze()
        mask_extent = (
            (Lat2d >= extent[2]) & (Lat2d <= extent[3]) &
            (Lon2d >= extent[0]) & (Lon2d <= extent[1])
        )
        data2d = np.where(mask_extent, data2d, np.nan)
        mesh = ax.contourf(
            Lon2d, Lat2d, data2d,
            levels=precip_breaks,
            cmap=precip_cmap,
            norm=precip_norm,
            extend='max',
            transform=ccrs.PlateCarree()
        )
        # Add 0.5-degree grid with precip numbers
        for lat in np.arange(extent[2], extent[3] + 0.01, 0.5):
            for lon in np.arange(extent[0], extent[1] + 0.01, 0.5):
                iy = np.abs(lats - lat).argmin() if lats.ndim == 1 else np.abs(lats[:,0] - lat).argmin()
                ix = np.abs(lons_plot - lon).argmin() if lons_plot.ndim == 1 else np.abs(lons_plot[0,:] - lon).argmin()
                precip_val = data2d[iy, ix]
                if not np.isnan(precip_val):
                    if precip_val == 0:
                        label = "0"
                    elif precip_val < 1:
                        label = f".{int(round(precip_val * 100)):02d}"
                    else:
                        label = f"{precip_val:.2f}"
                    ax.text(
                        lon, lat, label,
                        color='black', fontsize=6, fontweight='bold',
                        ha='center', va='center', transform=ccrs.PlateCarree(),
                        zorder=10
                    )
    else:
        leaflet_extent = extent
        mesh = ax.imshow(
            apcp_in.squeeze(),
            cmap=precip_cmap,
            norm=precip_norm,
            extent=leaflet_extent,
            origin='lower',
            interpolation='bilinear',
            aspect='auto',
            transform=ccrs.PlateCarree()
        )

    # Colorbar
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    tick_indices = list(range(0, len(precip_breaks), 2))
    ticks_to_show = [precip_breaks[i] for i in tick_indices]
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom',
        ticks=ticks_to_show, boundaries=precip_breaks
    )
    cbar.set_label("Precipitation (inches)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')
    for label in cbar.ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha('right')

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(northeast_precip_dir, f"northeast_precip_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated Northeast Precip PNG: {png_path}")
    return png_path

# Main process: Download and plot
forecast_steps = list(range(6, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)
for step in forecast_steps:
    grib_file = download_file(hour_str, step)
    if grib_file:
        generate_clean_png(grib_file, step)
        generate_northeast_precip_png(grib_file, step)
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
for f in os.listdir(northeast_precip_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(northeast_precip_dir, f))

print("All PNGs optimized.")

print("All PNGs optimized.")

