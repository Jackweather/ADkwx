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
from PIL import Image
import scipy.ndimage

BASE_DIR = '/var/data'

# --- Clean up old files in grib_files, pngs, and vort850_surface directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "vort850_surface", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "vort850_surface")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
vort850_surface_dir = os.path.join(output_dir, "static", "vort850_surface")
grib_dir = os.path.join(vort850_surface_dir, "grib_files")
png_dir = vort850_surface_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# GFS NOMADS URL and variable
base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_absv = "ABSV"
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Custom colormap and levels for PVA (10^-5 s^-2/hr)
pva_levels = [0, 1, 2, 4, 6, 8, 10, 12, 16, 20, 24, 28]
custom_cmap = LinearSegmentedColormap.from_list(
    "pva_cmap",
    [
        "#ffffff",  # 0 - white
        "#ffffb2",  # light yellow
        "#fed976",  # yellow-orange
        "#feb24c",  # orange
        "#fd8d3c",  # darker orange
        "#fc4e2a",  # red-orange
        "#e31a1c",  # red
        "#b10026"   # dark red
    ],
    N=256
)

def download_file(hour_str, step):
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path_absv = os.path.join(grib_dir, file_name + ".absv")
    file_path_hgt = os.path.join(grib_dir, file_name + ".hgt")
    file_path_wind = os.path.join(grib_dir, file_name + ".wind")
    # Download ABSV
    url_absv = (
        f"{base_url}?file={file_name}"
        f"&lev_850_mb=on&var_{variable_absv}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    # Download HGT
    url_hgt = (
        f"{base_url}?file={file_name}"
        f"&lev_850_mb=on&var_HGT=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    # Download UGRD/VGRD (wind)
    url_wind = (
        f"{base_url}?file={file_name}"
        f"&lev_850_mb=on&var_UGRD=on&var_VGRD=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    absv_ok = False
    hgt_ok = False
    wind_ok = False
    if not os.path.exists(file_path_absv):
        response_absv = requests.get(url_absv, stream=True)
        if response_absv.status_code == 200:
            with open(file_path_absv, 'wb') as f:
                for chunk in response_absv.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            print(f"Downloaded {file_name} (ABSV)")
            absv_ok = True
        else:
            print(f"Failed to download {file_name} (ABSV) (Status Code: {response_absv.status_code})")
    else:
        absv_ok = True
    if not os.path.exists(file_path_hgt):
        response_hgt = requests.get(url_hgt, stream=True)
        if response_hgt.status_code == 200:
            with open(file_path_hgt, 'wb') as f:
                for chunk in response_hgt.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            print(f"Downloaded {file_name} (HGT)")
            hgt_ok = True
        else:
            print(f"Failed to download {file_name} (HGT) (Status Code: {response_hgt.status_code})")
    else:
        hgt_ok = True
    if not os.path.exists(file_path_wind):
        response_wind = requests.get(url_wind, stream=True)
        if response_wind.status_code == 200:
            with open(file_path_wind, 'wb') as f:
                for chunk in response_wind.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            print(f"Downloaded {file_name} (UGRD/VGRD)")
            wind_ok = True
        else:
            print(f"Failed to download {file_name} (UGRD/VGRD) (Status Code: {response_wind.status_code})")
    else:
        wind_ok = True
    if absv_ok and hgt_ok and wind_ok:
        return file_path_absv, file_path_hgt, file_path_wind
    else:
        return None, None, None

def calc_pva(ds):
    # ds['absv'] is in s^-1, lats/lons are 1D
    absv = ds['absv'].values.squeeze()
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    # Convert lons to -180..180 for plotting
    lons_plot = np.where(lons > 180, lons - 360, lons)
    # Calculate grid spacing in meters
    Re = 6371000.0
    dlat = np.deg2rad(lats[1] - lats[0])
    dlon = np.deg2rad(lons[1] - lons[0])
    lat2d, lon2d = np.meshgrid(lats, lons_plot, indexing='ij')
    dx = Re * np.cos(np.deg2rad(lat2d)) * dlon
    dy = Re * dlat
    # Calculate gradients
    d_absv_dx = np.gradient(absv, axis=1) / dx
    d_absv_dy = np.gradient(absv, axis=0) / dy
    # Estimate wind from vorticity advection (approximate, as wind not available)
    # For demonstration, use a simple mean wind (10 m/s westerly)
    u = np.full_like(absv, 10.0)
    v = np.zeros_like(absv)
    # PVA = - (u * d(absv)/dx + v * d(absv)/dy)
    pva = -(u * d_absv_dx + v * d_absv_dy)
    # Only keep positive values, convert to 10^-5 s^-2/hr
    pva = np.where(pva > 0, pva, 0) * 1e5 * 3600
    return lats, lons_plot, pva

def generate_clean_png(file_path_absv, file_path_hgt, file_path_wind, step):
    ds_absv = xr.open_dataset(file_path_absv, engine="cfgrib")
    ds_hgt = xr.open_dataset(file_path_hgt, engine="cfgrib")
    ds_wind = xr.open_dataset(file_path_wind, engine="cfgrib")
    lats, lons_plot, pva = calc_pva(ds_absv)
    hgt = ds_hgt['gh'].values.squeeze()  # geopotential height in gpm

    # --- Smooth the data ---
    pva = scipy.ndimage.gaussian_filter(pva, sigma=1)
    hgt = scipy.ndimage.gaussian_filter(hgt, sigma=1)

    # Convert hgt from gpm to dam for plotting and labeling
    hgt_dam = hgt / 10.0

    Lon2d, Lat2d = np.meshgrid(lons_plot, lats)

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

    # --- Overlay 850mb height contours in dam ---
    hgt_contours = ax.contour(
        Lon2d, Lat2d, hgt_dam,
        levels=np.arange(120, 180, 3),
        colors='black', linewidths=1.2, linestyles='solid',
        transform=ccrs.PlateCarree()
    )
    ax.clabel(hgt_contours, fmt='%d', fontsize=5, colors='black', inline=True)

    # --- Plot wind barbs (subsample for clarity) ---
    try:
        u = ds_wind['u'].values.squeeze()
        v = ds_wind['v'].values.squeeze()
    except KeyError:
        # Some GFS files use 'u'/'v', others 'u850'/'v850'
        u = ds_wind[[k for k in ds_wind.data_vars if k.startswith('u')][0]].values.squeeze()
        v = ds_wind[[k for k in ds_wind.data_vars if k.startswith('v')][0]].values.squeeze()
    # Subsample for clarity (every 8th point)
    skip = (slice(None, None, 9), slice(None, None, 9))
    ax.barbs(
        Lon2d[skip], Lat2d[skip], u[skip], v[skip],
        length=6, linewidth=0.5, color='black', zorder=10, transform=ccrs.PlateCarree()
    )

    # --- Title block ---
    run_hour_map = {
        "00": 20, "06": 2, "12": 8, "18": 14
    }
    base_hour = run_hour_map.get(hour_str, 8)
    base_time = datetime.strptime(date_str + f"{base_hour:02d}", "%Y%m%d%H")
    valid_time = base_time + timedelta(hours=step)
    hour_str_fmt = valid_time.strftime('%I%p').lstrip('0').lower()
    day_of_week = valid_time.strftime('%A')
    run_str = f"{hour_str}z"
    title_str = (
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"850mb Positive Vorticity Advection (10⁻⁵ s⁻²/hr), 850mb Height (dam), 850mb Wind Barbs"
    )
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    # --- Plot PVA ---
    mesh = ax.contourf(
        Lon2d, Lat2d, pva,
        levels=pva_levels,
        cmap=custom_cmap,
        extend='max',
        transform=ccrs.PlateCarree()
    )

    # --- Add colorbar below plot ---
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom'
    )
    cbar.set_label("850mb Positive Vorticity Advection (10⁻⁵ s⁻²/hr)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    ax.set_axis_off()
    png_path = os.path.join(png_dir, f"vort850pva_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated clean PNG: {png_path}")
    return png_path

# Main process: Download and plot
forecast_steps = list(range(6, 385, 6))
if 264 not in forecast_steps:
    forecast_steps.append(264)
for step in forecast_steps:
    file_path_absv, file_path_hgt, file_path_wind = download_file(hour_str, step)
    if file_path_absv and file_path_hgt and file_path_wind:
        generate_clean_png(file_path_absv, file_path_hgt, file_path_wind, step)
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
