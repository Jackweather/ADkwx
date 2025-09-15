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
import scipy.ndimage

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files and pngs directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "WIND_200", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "WIND_200")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
wind_dir = os.path.join(output_dir, "static", "WIND_200")
grib_dir = os.path.join(wind_dir, "grib_files")
png_dir = wind_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS 0.25-degree URL and variables
base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_ugrd = "UGRD"
variable_vgrd = "VGRD"

# Current UTC time minus 6 hours (nearest available GFS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps
forecast_steps = [0] + list(range(6, 385, 6))

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

def get_wind_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"wind200_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_200_mb=on&var_{variable_ugrd}=on&var_{variable_vgrd}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_hgt_grib(step):
    # Download 200mb height for the given forecast hour
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"hgt200_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_200_mb=on&var_HGT=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def plot_wind_200(grib_path, step, hgt_grib_path=None):
    try:
        ds = xr.open_dataset(grib_path, engine="cfgrib")
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None

    # --- Find correct pressure coordinate ---
    pressure_coord = None
    for coord in ds.coords:
        if "isobaric" in coord:
            pressure_coord = coord
            break
    if pressure_coord is None:
        print("No isobaric coordinate found in GRIB file.")
        print("Available coordinates:", list(ds.coords))
        print("Available variables:", list(ds.data_vars))
        return None

    # --- Find correct U/V variable names ---
    u_var = None
    v_var = None
    for cand in ["u", "UGRD"]:
        if cand in ds.data_vars:
            u_var = cand
            break
    for cand in ["v", "VGRD"]:
        if cand in ds.data_vars:
            v_var = cand
            break
    if u_var is None or v_var is None:
        print("U/V wind variables not found in GRIB file.")
        print("Available variables:", list(ds.data_vars))
        return None

    # --- Select U/V at 200mb ---
    try:
        # If pressure coordinate is scalar, just use the variable directly
        if np.isscalar(ds[pressure_coord].values) or ds[pressure_coord].size == 1:
            u = ds[u_var].values
            v = ds[v_var].values
        else:
            u = ds[u_var].sel({pressure_coord: 200}).values
            v = ds[v_var].sel({pressure_coord: 200}).values
    except Exception as e:
        print(f"Error selecting U/V at 200mb: {e}")
        print("Available pressure levels:", ds[pressure_coord].values)
        return None

    wind_speed = np.sqrt(u**2 + v**2)
    lats = ds["latitude"].values
    lons = ds["longitude"].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    Lon2d, Lat2d = np.meshgrid(lons_plot, lats)

    # Convert U and V from m/s to knots for plotting barbs
    u_knots = u * 1.94384
    v_knots = v * 1.94384

    # --- Smooth wind speed field for shading ---
    wind_speed_knots = wind_speed * 1.94384
    wind_speed_knots_smooth = scipy.ndimage.gaussian_filter(wind_speed_knots, sigma=1.5)

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

    run_str = f"{hour_str}z"
    valid_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H") + timedelta(hours=step)
    hour_str_fmt = valid_time.strftime('%I%p').lstrip('0').lower()
    day_of_week = valid_time.strftime('%A')
    title_str = (
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"200mb Wind Speed (kt) & Wind Barbs | 200hPa Height"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # Only shade wind speeds 50 knots and above
    levels = np.arange(50, 161, 10)  # wind speed in knots
    colors = [
        '#abd9e9', '#74add1', '#4575b4', '#313695',
        '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'
    ]
    cmap = LinearSegmentedColormap.from_list('wind200_cmap', colors, N=len(levels)-1)
    # Mask out wind speeds below 50 knots for shading/contouring
    wind_speed_masked = np.where(wind_speed_knots_smooth >= 50, wind_speed_knots_smooth, np.nan)
    mesh = ax.contourf(Lon2d, Lat2d, wind_speed_masked, levels=levels, cmap=cmap, extend='both', alpha=0.7)
    cs = ax.contour(Lon2d, Lat2d, wind_speed_masked, levels=levels, colors='black', linewidths=0.5)
    ax.clabel(cs, fmt='%d', fontsize=7, colors='black', inline=True)

    # Wind barbs (every ~3 degrees, everywhere, using knots)
    skip = (slice(None, None, 12), slice(None, None, 12))
    ax.barbs(Lon2d[skip], Lat2d[skip], u_knots[skip], v_knots[skip], length=7, linewidth=0.7, color='black', alpha=0.8)

    # --- Plot 200mb height contours if available ---
    if hgt_grib_path is not None and os.path.exists(hgt_grib_path):
        try:
            ds_hgt = xr.open_dataset(hgt_grib_path, engine="cfgrib")
            # Find HGT variable and pressure coordinate
            hgt_var = None
            for cand in ["gh", "HGT"]:
                if cand in ds_hgt.data_vars:
                    hgt_var = cand
                    break
            hgt_pressure_coord = None
            for coord in ds_hgt.coords:
                if "isobaric" in coord:
                    hgt_pressure_coord = coord
                    break
            # Select HGT at 200mb
            if hgt_var and hgt_pressure_coord:
                if np.isscalar(ds_hgt[hgt_pressure_coord].values) or ds_hgt[hgt_pressure_coord].size == 1:
                    hgt_200 = ds_hgt[hgt_var].values
                else:
                    hgt_200 = ds_hgt[hgt_var].sel({hgt_pressure_coord: 200}).values
                # Use same lats/lons as wind
                ax.contour(Lon2d, Lat2d, hgt_200, colors='black', linewidths=1.0)
        except Exception as e:
            print(f"Error plotting HGT contours: {e}")

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom',
        ticks=levels, boundaries=levels
    )
    cbar.set_label("Wind Speed (kt)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    fig.text(0.99, 0.01, "adkwx.com", fontsize=10, color="black", ha="right", va="bottom", alpha=0.7, fontweight="bold")
    ax.set_axis_off()
    png_path = os.path.join(wind_dir, f"wind200_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated wind200 PNG: {png_path}")
    return png_path

for step in forecast_steps:
    wind_grib = get_wind_grib(step)
    hgt_grib_path = get_hgt_grib(step)
    if wind_grib:
        plot_wind_200(wind_grib, step, hgt_grib_path=hgt_grib_path)
        gc.collect()
        time.sleep(3)
        print("All wind200 PNG creation tasks complete!")
        time.sleep(3)

for f in os.listdir(grib_dir):
    file_path = os.path.join(grib_dir, f)
    if os.path.isfile(file_path):
        os.remove(file_path)
print("All GRIB files deleted from grib_dir.")
