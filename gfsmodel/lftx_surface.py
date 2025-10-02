import os
import requests
from datetime import datetime, timedelta
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
lftx_dir = os.path.join(BASE_DIR, "GFS", "static", "LFTX")
grib_dir = os.path.join(lftx_dir, "grib_files")
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(lftx_dir, exist_ok=True)

# GFS 0.25-degree URL and variables
base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_lftx = "LFTX"
variable_mslp = "MSLET"

# Current UTC time minus 6 hours (nearest available GFS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps (every 6 hours up to 384)
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

def get_lftx_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"lftx_surface_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_lftx}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_mslp_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"mslp_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_mean_sea_level=on&var_{variable_mslp}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def plot_lftx_surface(grib_path, step, mslp_grib_path=None):
    try:
        ds = xr.open_dataset(grib_path, engine="cfgrib")
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None

    lftx = ds['lftx'].values.squeeze()
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        lftx2d = lftx
    else:
        Lon2d, Lat2d = lons_plot, lats
        lftx2d = lftx

    # LFTX colormap and levels (typical: -10 to +10)
    lftx_levels = np.arange(-10, 11, 1)
    lftx_colors = plt.cm.RdYlBu_r(np.linspace(0, 1, len(lftx_levels)))
    lftx_cmap = LinearSegmentedColormap.from_list("lftx_cmap", lftx_colors, N=len(lftx_colors))
    lftx_norm = BoundaryNorm(lftx_levels, lftx_cmap.N)

    # --- Open MSLP if provided ---
    mslp2d = None
    if mslp_grib_path and os.path.exists(mslp_grib_path):
        try:
            ds_mslp = xr.open_dataset(mslp_grib_path, engine="cfgrib")
            mslp = ds_mslp['mslet'].values / 100.0  # Pa to hPa
            mslp_lats = ds_mslp['latitude'].values
            mslp_lons = ds_mslp['longitude'].values
            mslp_lons_plot = np.where(mslp_lons > 180, mslp_lons - 360, mslp_lons)
            if mslp_lats.ndim == 1 and mslp_lons.ndim == 1:
                Lon2d, Lat2d = np.meshgrid(mslp_lons_plot, mslp_lats)
                mslp2d = mslp.squeeze()
            else:
                Lon2d, Lat2d = mslp_lons_plot, mslp_lats
                mslp2d = mslp.squeeze()
        except Exception as e:
            print(f"Error opening MSLP dataset: {e}")
            mslp2d = None

    fig = plt.figure(figsize=(12, 8), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]  # updated extent
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 7}
    gl.ylabel_style = {'size': 7}
    gl.xlocator = plt.MaxNLocator(8)
    gl.ylocator = plt.MaxNLocator(6)

    mesh = ax.contourf(
        Lon2d, Lat2d, lftx2d,
        levels=lftx_levels,
        cmap=lftx_cmap,
        norm=lftx_norm,
        extend='both',
        transform=ccrs.PlateCarree(),
        alpha=0.65,
        zorder=2
    )

    # --- Plot MSLP contours and L/H if available ---
    if mslp2d is not None:
        mslp_levels = np.arange(960, 1050+2, 2)
        cs = ax.contour(
            Lon2d, Lat2d, mslp2d,
            levels=mslp_levels,
            colors='black',
            linewidths=0.7,
            transform=ccrs.PlateCarree()
        )
        ax.clabel(cs, fmt='%d', fontsize=5, colors='black', inline=True)

        # --- Highs and Lows detection (from mslp_prate.py) ---
        import scipy.ndimage as ndimage
        def in_extent(lon, lat):
            return (extent[0] <= lon <= extent[1]) and (extent[2] <= lat <= extent[3])

        data2d = mslp2d
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
                zorder=3, path_effects=[
                    plt.matplotlib.patheffects.Stroke(linewidth=1, foreground='white'),
                    plt.matplotlib.patheffects.Normal()
                ]
            )
            ax.text(
                lon, lat-0.7, f"{data2d[y, x]:.0f}",
                color='blue', fontsize=5, fontweight='bold',
                ha='center', va='top', transform=ccrs.PlateCarree(),
                zorder=3, path_effects=[
                    plt.matplotlib.patheffects.Stroke(linewidth=0.5, foreground='white'),
                    plt.matplotlib.patheffects.Normal()
                ]
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
                zorder=3, path_effects=[
                    plt.matplotlib.patheffects.Stroke(linewidth=1, foreground='white'),
                    plt.matplotlib.patheffects.Normal()
                ]
            )
            ax.text(
                lon, lat-0.7, f"{data2d[y, x]:.0f}",
                color='red', fontsize=5, fontweight='bold',
                ha='center', va='top', transform=ccrs.PlateCarree(),
                zorder=3, path_effects=[
                    plt.matplotlib.patheffects.Stroke(linewidth=0.5, foreground='white'),
                    plt.matplotlib.patheffects.Normal()
                ]
            )
            plotted_low_points.append((y, x))
            lows_plotted += 1

    run_str = f"{hour_str}z"
    valid_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H") + timedelta(hours=step)
    init_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H")
    utc = pytz.utc
    eastern = pytz.timezone('US/Eastern')
    valid_time_utc = utc.localize(valid_time)
    valid_time_est = valid_time_utc.astimezone(eastern)
    title_str = (
        f"GFS 0.25° | Surface Lifted Index (LFTX, °C)  (Neg=Unstable, Pos=Stable)\n"
        f"Valid: {valid_time_est:%Y-%m-%d %I:%M %p %Z}  |  "
        f"Init: {init_time:%Y-%m-%d %H:%M UTC}  |  Forecast Hour: {step:03d}  |  Run: {run_str}"
    )
    plt.title(title_str, fontsize=11, fontweight='bold', y=1.01, loc='left')  # Move title closer to plot

    # --- Adjust layout to reduce white space and gap ---
    plt.subplots_adjust(left=0.03, right=0.97, top=0.93, bottom=0.18, hspace=0)  # Tighten layout

    # --- Colorbar: move closer to plot and reduce white space ---
    cax = fig.add_axes([0.13, 0.13, 0.74, 0.025])  # [left, bottom, width, height] - move up
    cbar = plt.colorbar(mesh, cax=cax, orientation='horizontal', ticks=lftx_levels)
    cbar.set_label("Surface Lifted Index (°C)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    ax.set_axis_off()
    png_path = os.path.join(lftx_dir, f"lftx_surface_gfs_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0.05, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated LFTX Surface PNG: {png_path}")
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
    lftx_grib = get_lftx_grib(step)
    mslp_grib = get_mslp_grib(step)
    if lftx_grib and mslp_grib:
        plot_lftx_surface(lftx_grib, step, mslp_grib_path=mslp_grib)
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
for f in os.listdir(lftx_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(lftx_dir, f))

print("All LFTX Surface PNGs optimized.")
