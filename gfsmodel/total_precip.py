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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
total_precip_dir = os.path.join(output_dir, "static", "total_precip")
grib_dir = os.path.join(total_precip_dir, "grib_files")
png_dir = total_precip_dir
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
        if os.path.getsize(file_path) < 10240:
            print(f"Downloaded {file_name} but file is too small (likely empty or error page).")
            os.remove(file_path)
            return None
        print(f"Downloaded {file_name}")
        return file_path
    else:
        print(f"Failed to download {file_name} (Status Code: {response.status_code})")
        return None

def plot_total_precip(total_precip_in, lats, lons, step):
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
        f"Total Precipitation (Accumulated)\n"
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        data2d = total_precip_in.squeeze()
    else:
        Lon2d, Lat2d = lons_plot, lats
        data2d = total_precip_in.squeeze()
    mask_extent = (
        (Lat2d >= extent_bottom) & (Lat2d <= extent_top) &
        (Lon2d >= extent_left) & (Lon2d <= extent_right)
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

    # --- Add 2-degree grid with precipitation numbers ---
    for lat in range(int(extent_bottom), int(extent_top) + 1, 2):
        for lon in range(int(extent_left), int(extent_right) + 1, 2):
            # Find nearest grid point
            iy = np.abs(lats - lat).argmin() if lats.ndim == 1 else np.abs(lats[:,0] - lat).argmin()
            ix = np.abs(lons_plot - lon).argmin() if lons_plot.ndim == 1 else np.abs(lons_plot[0,:] - lon).argmin()
            precip_val = data2d[iy, ix]
            if not np.isnan(precip_val):
                # Show "0" if exactly zero, otherwise show 2 decimal places without leading zero
                if precip_val == 0:
                    label = "0"
                else:
                    label = f"{precip_val:.2f}"[1:] if precip_val < 10 else f"{precip_val:.2f}"
                ax.text(
                    lon, lat, label,
                    color='black', fontsize=4, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(),
                    zorder=10
                )

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.08)
    tick_indices = list(range(0, len(precip_breaks), 2))
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
    for label in cbar.ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha('right')

    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"totalprecip_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=True, dpi=300, facecolor='white')
    plt.close(fig)
    print(f"Generated total precip PNG: {png_path}")
    return png_path

# Main process: Download, accumulate, and plot
forecast_steps = list(range(6, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)

total_precip_in = None
lats, lons = None, None

for step in forecast_steps:
    grib_file = download_file(hour_str, step)
    if grib_file:
        ds = xr.open_dataset(grib_file, engine="cfgrib")
        apcp_mm = ds['tp'].values
        apcp_in = apcp_mm / 25.4
        apcp_in = np.where(
            (np.isnan(apcp_in)) | (apcp_in < 0) | (apcp_in > 50),
            0,
            apcp_in
        )
        if total_precip_in is None:
            total_precip_in = apcp_in.copy()
            lats = ds['latitude'].values
            lons = ds['longitude'].values
        else:
            total_precip_in += apcp_in
        plot_total_precip(total_precip_in, lats, lons, step)
        gc.collect()
        time.sleep(3)

print("All GRIB file download and total precipitation PNG creation tasks complete!")

