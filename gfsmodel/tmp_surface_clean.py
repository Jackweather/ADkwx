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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Clean up old files in grib_files, pngs, and tmp_surface directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "tmp_surface", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "tmp_surface")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
tmp_surface_dir = os.path.join(output_dir, "static", "tmp_surface")
grib_dir = os.path.join(tmp_surface_dir, "grib_files")
png_dir = tmp_surface_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_tmp = "TMP"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Custom colormap and levels for temperature (°F)
temp_levels = [-20, 0, 10, 20, 32, 40, 50, 60, 70, 80, 90, 100]
custom_cmap = LinearSegmentedColormap.from_list(
    "temp_cmap",
    [
        "#08306b", "#2171b5", "#6baed6", "#b3cde3", "#ffffff",
        "#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"
    ],
    N=256
)

def download_file(hour_str, step):
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, file_name)
    url_tmp = (
        f"{base_url}?file={file_name}"
        f"&lev_2_m_above_ground=on&var_{variable_tmp}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    response = requests.get(url_tmp, stream=True)
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
    ds = xr.open_dataset(file_path, engine="cfgrib")
    data = ds['t2m'].values - 273.15  # Kelvin to Celsius

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # --- Add map features as in mslp_prate.py ---
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)
    # --- End map features ---

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
        f"2m Temperature (°F)"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # --- Plot temperature ---
    if 'latitude' in ds and 'longitude' in ds:
        lats = ds['latitude'].values
        lons = ds['longitude'].values
        lons_plot = np.where(lons > 180, lons - 360, lons)
        if lats.ndim == 1 and lons.ndim == 1:
            Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
            data2d = data.squeeze()
        else:
            Lon2d, Lat2d = lons_plot, lats
            data2d = data.squeeze()
        mesh = ax.contourf(
            Lon2d, Lat2d, data2d * 9/5 + 32,
            levels=temp_levels,
            cmap=custom_cmap,
            extend='both',
            transform=ccrs.PlateCarree()
        )

        # --- Add 1-degree grid with temperature numbers ---
        # Only plot for integer lat/lon within extent
        for lat in range(int(extent[2]), int(extent[3]) + 1):
            for lon in range(int(extent[0]), int(extent[1]) + 1):
                # Find nearest grid point
                iy = np.abs(lats - lat).argmin() if lats.ndim == 1 else np.abs(lats[:,0] - lat).argmin()
                ix = np.abs(lons_plot - lon).argmin() if lons_plot.ndim == 1 else np.abs(lons_plot[0,:] - lon).argmin()
                temp_c = data2d[iy, ix]
                temp_f = temp_c * 9/5 + 32
                ax.text(
                    lon, lat, f"{int(round(temp_f))}",
                    color='black', fontsize=4, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(),
                    zorder=10
                    # removed bbox for transparent background
                )
    else:
        leaflet_extent = extent
        mesh = ax.imshow(
            data.squeeze() * 9/5 + 32,
            cmap=custom_cmap,
            extent=leaflet_extent,
            origin='lower',
            interpolation='bilinear',
            aspect='auto',
            transform=ccrs.PlateCarree()
        )
        # No grid overlay for imshow fallback

    # --- Add colorbar below plot, styled like mslp_prate.py ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom'
    )
    cbar.set_label("2m Temperature (°F)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "ADKWX.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"2mtemp_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated clean PNG: {png_path}")
    return png_path

# Main process: Download and plot
forecast_steps = list(range(6, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)
for step in forecast_steps:
    grib_file = download_file(hour_str, step)
    if grib_file:
        generate_clean_png(grib_file, step)
        gc.collect()
        time.sleep(3)

print("All GRIB file download and PNG creation tasks complete!")
