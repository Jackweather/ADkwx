import os
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
from matplotlib import patheffects as path_effects
import scipy.ndimage as ndimage

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files, pngs, and 850mb directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "gfs_850mb", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "gfs_850mb")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
gfs_850mb_dir = os.path.join(output_dir, "static", "gfs_850mb")
grib_dir = os.path.join(gfs_850mb_dir, "grib_files")
png_dir = gfs_850mb_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variables
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variables = ["HGT", "RH", "UGRD", "VGRD"]
level = "850_mb"
variable_mslp = "MSLET"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

def download_file(hour_str, step):
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path_850 = os.path.join(grib_dir, file_name)
    file_path_mslp = os.path.join(grib_dir, f"mslp_{file_name}")
    var_str = ''.join([f"&var_{v}=on" for v in variables])
    url_850 = (
        f"{base_url}?file={file_name}"
        f"&lev_{level}=on"
        f"{var_str}"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    url_mslp = (
        f"{base_url}?file={file_name}"
        f"&lev_mean_sea_level=on&var_{variable_mslp}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    # Download 850mb
    response_850 = requests.get(url_850, stream=True)
    if response_850.status_code == 200:
        with open(file_path_850, 'wb') as f:
            for chunk in response_850.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {file_name}")
    else:
        print(f"Failed to download {file_name} (Status Code: {response_850.status_code})")
        return None, None
    # Download MSLP
    response_mslp = requests.get(url_mslp, stream=True)
    if response_mslp.status_code == 200:
        with open(file_path_mslp, 'wb') as f:
            for chunk in response_mslp.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded mslp_{file_name}")
    else:
        print(f"Failed to download mslp_{file_name} (Status Code: {response_mslp.status_code})")
        return file_path_850, None
    return file_path_850, file_path_mslp

def plot_highs_lows(ax, Lon2d, Lat2d, data2d, extent):
    def in_extent(lon, lat):
        return (extent[0] <= lon <= extent[1]) and (extent[2] <= lat <= extent[3])
    mask = (
        (Lon2d >= extent[0]) & (Lon2d <= extent[1]) &
        (Lat2d >= extent[2]) & (Lat2d <= extent[3])
    )
    data_masked = np.where(mask, data2d, np.nan)
    # Highs
    max_filt = ndimage.maximum_filter(data_masked, size=25, mode='constant', cval=np.nan)
    highs = (data_masked == max_filt) & ~np.isnan(data_masked) & (data_masked >= 1020)
    high_y, high_x = np.where(highs)
    highs_plotted = 0
    max_highs = 4
    min_high_distance = 60
    plotted_high_points = []
    for y, x in zip(high_y, high_x):
        if highs_plotted >= max_highs:
            break
        lon, lat = Lon2d[y, x], Lat2d[y, x]
        if not in_extent(lon, lat):
            continue
        too_close = False
        for py, px in plotted_high_points:
            if np.hypot(y - py, x - px) < min_high_distance:
                too_close = True
                break
        if too_close:
            continue
        plotted_high_points.append((y, x))
        ax.text(
            lon, lat, "H",
            color='blue', fontsize=16, fontweight='bold',
            ha='center', va='center', transform=ccrs.PlateCarree(),
            zorder=3, path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()]
        )
        ax.text(
            lon, lat-0.7, f"{data2d[y, x]:.0f}",
            color='blue', fontsize=5, fontweight='bold',
            ha='center', va='top', transform=ccrs.PlateCarree(),
            zorder=3, path_effects=[path_effects.Stroke(linewidth=0.5, foreground='white'), path_effects.Normal()]
        )
        highs_plotted += 1
    # Lows
    min_filt = ndimage.minimum_filter(data_masked, size=25, mode='constant', cval=np.nan)
    lows = (data_masked == min_filt) & ~np.isnan(data_masked) & (data_masked <= 1006)
    low_y, low_x = np.where(lows)
    lows_plotted = 0
    max_lows = 4
    min_low_distance = 60
    plotted_low_points = []
    for y, x in zip(low_y, low_x):
        if lows_plotted >= max_lows:
            break
        if (y, x) in plotted_high_points:
            continue
        lon, lat = Lon2d[y, x], Lat2d[y, x]
        if not in_extent(lon, lat):
            continue
        too_close = False
        for py, px in plotted_low_points:
            if np.hypot(y - py, x - px) < min_low_distance:
                too_close = True
                break
        if too_close:
            continue
        ax.text(
            lon, lat, "L",
            color='red', fontsize=16, fontweight='bold',
            ha='center', va='center', transform=ccrs.PlateCarree(),
            zorder=3, path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()]
        )
        ax.text(
            lon, lat-0.7, f"{data2d[y, x]:.0f}",
            color='red', fontsize=5, fontweight='bold',
            ha='center', va='top', transform=ccrs.PlateCarree(),
            zorder=3, path_effects=[path_effects.Stroke(linewidth=0.5, foreground='white'), path_effects.Normal()]
        )
        plotted_low_points.append((y, x))
        lows_plotted += 1

def generate_850mb_png(file_path_850, file_path_mslp, step):
    ds = xr.open_dataset(file_path_850, engine="cfgrib")
    ds_mslp = xr.open_dataset(file_path_mslp, engine="cfgrib")
    hgt = ds['gh'].values  # geopotential height (meters)
    rh = ds['r'].values    # relative humidity
    ugrd = ds['u'].values  # u-wind
    vgrd = ds['v'].values  # v-wind
    mslp = ds_mslp['mslet'].values / 100.0  # Pa to hPa

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    ax.set_extent(extent, crs=ccrs.PlateCarree())

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
        f"GFS 850mb {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"Geopotential Height (m), RH (%), Wind (kt)"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # --- Plotting ---
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    Lon2d, Lat2d = np.meshgrid(lons_plot, lats)

    # RH filled: dry=brown/tan, moist=light/dark green
    rh_cmap = LinearSegmentedColormap.from_list(
        "rh_cmap", [
            "#a6611a",  # brown
            "#dfc27d",  # tan
            "#a6dba0",  # light green
            "#1a9641"   # dark green
        ], N=256
    )
    rh_levels = np.arange(10, 101, 10)
    rh_plot = ax.contourf(
        Lon2d, Lat2d, rh.squeeze(),
        levels=rh_levels, cmap=rh_cmap, extend='max', transform=ccrs.PlateCarree()
    )

    # Height contours in dam, thicker lines
    hgt_dam = hgt.squeeze() / 10.0
    hgt_min = np.nanmin(hgt_dam)
    hgt_max = np.nanmax(hgt_dam)
    hgt_levels = np.arange(np.floor(hgt_min/3)*3, np.ceil(hgt_max/3)*3+1, 3)
    hgt_contours = ax.contour(
        Lon2d, Lat2d, hgt_dam,
        levels=hgt_levels, colors='black', linewidths=1.2, transform=ccrs.PlateCarree()
    )
    ax.clabel(hgt_contours, fmt='%d', fontsize=6)

    # Wind barbs (subsample for clarity)
    skip = (slice(None, None, 5), slice(None, None, 5))
    ax.barbs(
        Lon2d[skip], Lat2d[skip],
        ugrd.squeeze()[skip], vgrd.squeeze()[skip],
        length=4.5, linewidth=0.3, color='k', transform=ccrs.PlateCarree()
    )

    # --- Add colorbar below plot ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    cbar = plt.colorbar(
        rh_plot, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom'
    )
    cbar.set_label("Relative Humidity (%)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    # --- Plot Highs/Lows only (no MSLP contours) ---
    plot_highs_lows(ax, Lon2d, Lat2d, mslp.squeeze(), extent)

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"gfs_850mb_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated 850mb PNG: {png_path}")
    return png_path

# Main process: Download and plot
forecast_steps = list(range(6, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)
for step in forecast_steps:
    grib_file_850, grib_file_mslp = download_file(hour_str, step)
    if grib_file_850 and grib_file_mslp:
        generate_850mb_png(grib_file_850, grib_file_mslp, step)
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
from PIL import Image

def optimize_png(filepath):
    try:
        with Image.open(filepath) as img:
            img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
            img.save(filepath, optimize=True)
            print(f"Optimized PNG: {filepath}")
    except Exception as e:
        print(f"Failed to optimize {filepath}: {e}")

for f in os.listdir(gfs_850mb_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(gfs_850mb_dir, f))

print("All PNGs optimized.")
