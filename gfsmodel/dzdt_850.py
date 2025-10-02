import os
import requests
from datetime import datetime, timedelta
# Add timezone support
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

BASE_DIR = '/var/data'

# Output directories
dzdt_dir = os.path.join(BASE_DIR, "GFS", "static", "DZDT850")
grib_dir = os.path.join(dzdt_dir, "grib_files")
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(dzdt_dir, exist_ok=True)

# GFS 0.25-degree URL and variable
base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_dzdt = "DZDT"

# Current UTC time minus 6 hours (nearest available GFS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps
forecast_steps = [0] + list(range(6, 385, 6))

# Colormap and levels for DZDT (customize as needed)
# Only positive DZDT levels for colorbar
dzdt_levels = np.linspace(0.01, 0.5, 11)  # start just above zero to avoid all-NaN
dzdt_colors = plt.cm.seismic(np.linspace(0.5, 1, len(dzdt_levels)))  # upper half of colormap
dzdt_cmap = LinearSegmentedColormap.from_list("dzdt_cmap", dzdt_colors, N=len(dzdt_colors))
dzdt_norm = BoundaryNorm(dzdt_levels, dzdt_cmap.N)

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

def get_dzdt_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"dzdt850_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_850_mb=on&var_{variable_dzdt}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_hgt_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"hgt850_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_850_mb=on&var_HGT=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_prate_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"prate_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_PRATE=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def plot_dzdt850(grib_path, step, hgt_grib_path=None, prate_grib_path=None):
    try:
        ds = xr.open_dataset(grib_path, engine="cfgrib")
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None

    dzdt = ds['wz'].values.squeeze()
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        dzdt2d = dzdt
    else:
        Lon2d, Lat2d = lons_plot, lats
        dzdt2d = dzdt

    # Only plot positive values
    dzdt2d = np.where(dzdt2d > 0, dzdt2d, np.nan)

    # --- Read HGT if provided ---
    hgt2d = None
    if hgt_grib_path and os.path.exists(hgt_grib_path):
        try:
            ds_hgt = xr.open_dataset(hgt_grib_path, engine="cfgrib")
            hgt = ds_hgt['gh'].values.squeeze()
            # HGT units: geopotential meters (gpm)
            if lats.ndim == 1 and lons.ndim == 1:
                hgt2d = hgt
            else:
                hgt2d = hgt
        except Exception as e:
            print(f"Error opening HGT dataset: {e}")
            hgt2d = None

    # --- Read PRATE if provided ---
    prate2d = None
    if prate_grib_path and os.path.exists(prate_grib_path):
        try:
            # Try to open with stepType='instant', fallback to 'avg'
            try:
                ds_prate = xr.open_dataset(prate_grib_path, engine="cfgrib", filter_by_keys={"stepType": "instant"})
            except Exception:
                ds_prate = xr.open_dataset(prate_grib_path, engine="cfgrib", filter_by_keys={"stepType": "avg"})
            prate = ds_prate['prate'].values.squeeze() * 3600  # mm/s to mm/hr
            if lats.ndim == 1 and lons.ndim == 1:
                prate2d = prate
            else:
                prate2d = prate
        except Exception as e:
            print(f"Error opening PRATE dataset: {e}")
            prate2d = None

    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]  # USA view, matches tmp_surface_clean.py
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # Basemap features
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    # Add latitude/longitude gridlines with labels
    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 7}
    gl.ylabel_style = {'size': 7}
    gl.xlocator = plt.MaxNLocator(8)
    gl.ylocator = plt.MaxNLocator(6)

    # --- Plot PRATE as a transparent layer if available ---
    prate_cbar = None
    if prate2d is not None:
        prate_levels = [0.1, 0.25, 0.5, 0.75, 1.5, 2, 2.5, 3, 4, 6, 10, 16, 24]
        prate_colors = [
            "#b6ffb6", "#54f354", "#19a319", "#016601", "#c9c938", "#f5f825", "#ffd700",
            "#ffa500", "#ff7f50", "#ff4500", "#ff1493", "#9400d3"
        ]
        prate_cmap = LinearSegmentedColormap.from_list("prate_custom", prate_colors, N=len(prate_colors))
        prate_norm = BoundaryNorm(prate_levels, prate_cmap.N)
        prate_mesh = ax.contourf(
            Lon2d, Lat2d, prate2d,
            levels=prate_levels,
            cmap=prate_cmap,
            norm=prate_norm,
            extend='max',
            transform=ccrs.PlateCarree(),
            alpha=0.35,  # semi-transparent
            zorder=1
        )

    mesh = ax.contourf(
        Lon2d, Lat2d, dzdt2d,
        levels=dzdt_levels,
        cmap=dzdt_cmap,
        norm=dzdt_norm,
        extend='max',
        transform=ccrs.PlateCarree(),
        alpha=0.85,
        zorder=2
    )

    # --- Overlay HGT contours if available ---
    if hgt2d is not None:
        hgt_levels = np.arange(1200, 1800+60, 60)
        cs = ax.contour(
            Lon2d, Lat2d, hgt2d,
            levels=hgt_levels,
            colors='black',
            linewidths=0.7,
            transform=ccrs.PlateCarree(),
            zorder=3
        )
        ax.clabel(cs, fmt='%d', fontsize=6, colors='black', inline=True)

    # Improved, more detailed title
    run_str = f"{hour_str}z"
    valid_time = (datetime.strptime(date_str + hour_str, "%Y%m%d%H") + timedelta(hours=step))
    init_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H")
    # --- Convert valid_time to US Eastern Time ---
    utc = pytz.utc
    eastern = pytz.timezone('US/Eastern')
    valid_time_utc = utc.localize(valid_time)
    valid_time_est = valid_time_utc.astimezone(eastern)
    # --- Add PRATE to title if available ---
    prate_in_title = " | PRATE Overlay" if prate2d is not None else ""
    title_str = (
        f"GFS 0.25° | 850mb Vertical Velocity (w, m/s/hr) | Geopotential Height Contours{prate_in_title}\n"
        f"Valid: {valid_time_est:%Y-%m-%d %I:%M %p %Z}  |  "
        f"Init: {init_time:%Y-%m-%d %H:%M UTC}  |  Forecast Hour: {step:03d}  |  Run: {run_str}"
    )
    plt.title(title_str, fontsize=11, fontweight='bold', y=1.04, loc='left')

    # Colorbar (only positive)
    cax = fig.add_axes([0.15, 0.12, 0.7, 0.02])
    cbar = plt.colorbar(mesh, cax=cax, orientation='horizontal', ticks=dzdt_levels)
    cbar.set_label("850mb Vertical Velocity (w, m/s/hr, upward only)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    # Add PRATE colorbar below if PRATE is plotted
    if prate2d is not None:
        cax_prate = fig.add_axes([0.15, 0.07, 0.7, 0.02])
        prate_cbar = plt.colorbar(prate_mesh, cax=cax_prate, orientation='horizontal', ticks=prate_levels)
        prate_cbar.set_label("Surface Precipitation Rate (mm/hr)", fontsize=8)
        prate_cbar.ax.tick_params(labelsize=7)
        prate_cbar.ax.set_facecolor('white')
        prate_cbar.outline.set_edgecolor('black')

    ax.set_axis_off()
    png_path = os.path.join(dzdt_dir, f"dzdt850_gfs_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated DZDT850 PNG: {png_path}")
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
    dzdt_grib = get_dzdt_grib(step)
    hgt_grib = get_hgt_grib(step)
    prate_grib = get_prate_grib(step)
    if dzdt_grib:
        plot_dzdt850(dzdt_grib, step, hgt_grib_path=hgt_grib, prate_grib_path=prate_grib)
        gc.collect()
        time.sleep(2)

# Delete all GRIB files after PNGs are made
for f in os.listdir(grib_dir):
    file_path = os.path.join(grib_dir, f)
    if os.path.isfile(file_path):
        os.remove(file_path)
        gc.collect()
        time.sleep(1)

# Optimize PNGs
for f in os.listdir(dzdt_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(dzdt_dir, f))

print("All DZDT850 PNGs optimized.")
