import os
import requests
from datetime import datetime, timedelta
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import numpy as np
import cartopy.crs as ccrs
import matplotlib.patheffects as path_effects
import scipy.ndimage as ndimage
import scipy.interpolate as interp  # <-- add this import
import time
import gc
import cartopy.io.shapereader as shpreader
import cartopy.feature as cfeature

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Clean up old files in grib_files, pngs, and combined_mslp_prate directories ---
for folder in [
    os.path.join(BASE_DIR, "GFS", "static", "PRATEGFS", "grib_files"),
    os.path.join(BASE_DIR, "GFS", "static", "pngs"),
    os.path.join(BASE_DIR, "GFS", "static", "PRATEGFS")
]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

# Directories
output_dir = os.path.join(BASE_DIR, "GFS")
combined_dir = os.path.join(output_dir, "static", "PRATEGFS")
grib_dir = os.path.join(combined_dir, "grib_files")
png_dir = combined_dir
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(png_dir, exist_ok=True)

# Output directory for combined PNGs
# combined_dir = os.path.join(BASE_DIR, "GFS", "static", "combined_mslp_prate")
# os.makedirs(combined_dir, exist_ok=True)

# GFS 0.25-degree URL and variables
base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_mslp = "MSLET"
variable_prate = "PRATE"

# Current UTC time minus 6 hours (nearest available GFS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)  # nearest 6-hour slot

# Levels and colormaps
mslp_levels = np.arange(960, 1050+2, 2)
mslp_cmap = LinearSegmentedColormap.from_list(
    "mslp_cmap",
    [
        "#08306b", "#2171b5", "#6baed6", "#b3cde3", "#ffffff",
        "#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"
    ],
    N=256
)
prate_levels = [0.1, 0.25, 0.5, 0.75, 1.5, 2, 2.5, 3, 4, 6, 10, 16, 24]
prate_colors = [
    "#b6ffb6",  # very light green
    "#54f354",  # light green
    "#19a319",  # medium green
    "#016601",  # dark green
    "#c9c938",  # bright yellow
    "#f5f825",  # dark yellow
    "#ffd700",  # gold
    "#ffa500",  # orange
    "#ff7f50",  # coral
    "#ff4500",  # orange-red
    "#ff1493",  # deep pink
    "#9400d3"   # dark violet
]
prate_cmap = LinearSegmentedColormap.from_list("prate_custom", prate_colors, N=len(prate_colors))
prate_norm = BoundaryNorm(prate_levels, prate_cmap.N)

# Forecast steps
forecast_steps = [0] + list(range(6, 385, 6))

# Download functions
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

def get_prate_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"prate_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_prate}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

# Plotting function
def plot_combined(mslp_path, prate_path, step):
    try:
        ds_mslp = xr.open_dataset(mslp_path, engine="cfgrib")
        ds_prate = xr.open_dataset(prate_path, engine="cfgrib", filter_by_keys={"stepType": "instant"})
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None

    mslp = ds_mslp['mslet'].values / 100.0  # Pa to hPa
    prate = ds_prate['prate'].values * 3600  # mm/s to mm/hr

    lats = ds_mslp['latitude'].values
    lons = ds_mslp['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        mslp2d = mslp.squeeze()
        prate2d = prate.squeeze()
    else:
        Lon2d, Lat2d = lons_plot, lats
        mslp2d = mslp.squeeze()
        prate2d = prate.squeeze()

    data2d = mslp2d

    # --- Begin custom basemap integration ---
    fig = plt.figure(figsize=(10, 7), dpi=600, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    margin = 1.0  # degrees margin to avoid plotting on the very edge

    # --- Title block ---
    # Map GFS run hour to local base time for f000
    run_hour_map = {
        "00": 20,  # 00z run: f000 = 8pm previous day
        "06": 2,   # 06z run: f000 = 2am
        "12": 8,   # 12z run: f000 = 8am
        "18": 14   # 18z run: f000 = 2pm
    }
    base_hour = run_hour_map.get(hour_str, 8)  # default to 8am if unknown
    base_time = datetime.strptime(date_str + f"{base_hour:02d}", "%Y%m%d%H")
    valid_time = base_time + timedelta(hours=step)
    hour_str_fmt = valid_time.strftime('%I%p').lstrip('0').lower()  # '08AM' -> '8am'
    day_of_week = valid_time.strftime('%A')
    run_str = f"{hour_str}z"  # Add run time string (e.g., "12z")
    # Add forecast hour (just the number, no 'f')
    title_str = (
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"Precipitation Rate & Mean Sea Level Pressure"
    )
    # Add title above plot
    plt.title(title_str, fontsize=12, fontweight='bold', y=1.03)

    def in_extent(lon, lat):
        return (extent[0] + margin <= lon <= extent[1] - margin) and (extent[2] + margin <= lat <= extent[3] - margin)

    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # Base map
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)
    # --- End custom basemap integration ---

    # Plot PRATE as filled contours
    mesh = ax.contourf(
        Lon2d, Lat2d, prate2d,
        levels=prate_levels,
        cmap=prate_cmap,
        norm=prate_norm,
        extend='max',
        transform=ccrs.PlateCarree(),
        alpha=0.7
    )

    # Add ADKWX.com to bottom right
    fig.text(
        0.99, 0.01, "adkwx.com",
        fontsize=10, color="black", ha="right", va="bottom",
        alpha=0.7, fontweight="bold"
    )

    # Add colorbar for PRATE, tightly below the plot
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0.01)
    cbar = plt.colorbar(
        mesh, ax=ax, orientation='horizontal',
        pad=0.01, aspect=25, shrink=0.65, fraction=0.035,
        anchor=(0.5, 0.0), location='bottom',
        ticks=prate_levels, boundaries=prate_levels
    )
    cbar.set_label("Precipitation Rate (mm/hr)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    cbar.ax.set_facecolor('white')
    cbar.outline.set_edgecolor('black')

    # --- MSLP plotting ---
    cs = ax.contour(
        Lon2d, Lat2d, mslp2d,
        levels=mslp_levels,
        colors='black',
        linewidths=0.7,  # thinner lines
        transform=ccrs.PlateCarree()
    )
    ax.clabel(cs, fmt='%d', fontsize=4, colors='black', inline=True)

    # --- Highs and Lows detection ---
    # Only search for extrema within the plotted region
    mask = (
        (Lon2d >= extent[0]) & (Lon2d <= extent[1]) &
        (Lat2d >= extent[2]) & (Lat2d <= extent[3])
    )
    data_masked = np.where(mask, data2d, np.nan)

    # Find local maxima (Highs) >= 1020 hPa
    max_filt = ndimage.maximum_filter(data_masked, size=25, mode='constant', cval=np.nan)
    highs = (data_masked == max_filt) & ~np.isnan(data_masked) & (data_masked >= 1020)
    high_y, high_x = np.where(highs)
    highs_plotted = 0
    max_highs = 4
    min_high_distance = 60  # minimum grid points between plotted highs
    plotted_high_points = []
    for y, x in zip(high_y, high_x):
        if highs_plotted >= max_highs:
            break
        lon, lat = Lon2d[y, x], Lat2d[y, x]
        if not in_extent(lon, lat):
            continue
        # Check if this high is too close to any already plotted high
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

    # Find local minima (Lows) <= 1006 hPa (lowered threshold for hurricanes)
    min_filt = ndimage.minimum_filter(data_masked, size=25, mode='constant', cval=np.nan)
    lows = (data_masked == min_filt) & ~np.isnan(data_masked) & (data_masked <= 1006)
    low_y, low_x = np.where(lows)
    lows_plotted = 0
    max_lows = 4
    min_low_distance = 60  # increased minimum grid points between plotted lows
    plotted_low_points = []

    for y, x in zip(low_y, low_x):
        if lows_plotted >= max_lows:
            break
        if (y, x) in plotted_high_points:
            continue  # Skip if already plotted as a High
        lon, lat = Lon2d[y, x], Lat2d[y, x]
        if not in_extent(lon, lat):
            continue
        # Check if this low is too close to any already plotted low
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

    # Always plot the absolute minimum pressure as "L" if not already plotted and not too close to existing lows
    flat_data = data2d.flatten()
    min_idx = np.nanargmin(flat_data)
    min_y_full, min_x_full = np.unravel_index(min_idx, data2d.shape)

    if in_extent(Lon2d[min_y_full, min_x_full], Lat2d[min_y_full, min_x_full]):
        window = 2
        y0, x0 = min_y_full, min_x_full
        y1, y2 = max(0, y0 - window), min(data2d.shape[0], y0 + window + 1)
        x1, x2 = max(0, x0 - window), min(data2d.shape[1], x0 + window + 1)
        local_patch = data2d[y1:y2, x1:x2]
        grad_y, grad_x = np.gradient(local_patch)
        grad_mag = np.sqrt(grad_y**2 + grad_x**2)
        max_grad = np.nanmax(grad_mag)
        close_contour_threshold = 2.0  # hPa/grid, tune as needed

        already_plotted = any(np.hypot(min_y_full - py, min_x_full - px) < min_low_distance for py, px in plotted_low_points)
        if (not already_plotted) or (max_grad > close_contour_threshold and not already_plotted):
            if not already_plotted:
                ax.text(
                    Lon2d[min_y_full, min_x_full], Lat2d[min_y_full, min_x_full], "L",
                    color='red', fontsize=16, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(),
                    zorder=3, path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()]
                )
                ax.text(
                    Lon2d[min_y_full, min_x_full], Lat2d[min_y_full, min_x_full]-0.7, f"{data2d[min_y_full, min_x_full]:.0f}",
                    color='red', fontsize=5, fontweight='bold',
                    ha='center', va='top', transform=ccrs.PlateCarree(),
                    zorder=3, path_effects=[path_effects.Stroke(linewidth=0.5, foreground='white'), path_effects.Normal()]
                )
                plotted_low_points.append((min_y_full, min_x_full))

    # Always plot an L at the location of the tightest pressure gradient (if extreme and not too close to existing lows)
    grad_y_full, grad_x_full = np.gradient(data2d)
    grad_mag_full = np.sqrt(grad_y_full**2 + grad_x_full**2)
    max_grad_idx = np.nanargmax(grad_mag_full)
    grad_y, grad_x = np.unravel_index(max_grad_idx, grad_mag_full.shape)
    max_grad_value = grad_mag_full[grad_y, grad_x]
    tight_gradient_threshold = 3.0  # hPa/grid, adjust as needed

    window = 2
    y1, y2 = max(0, grad_y - window), min(data2d.shape[0], grad_y + window + 1)
    x1, x2 = max(0, grad_x - window), min(data2d.shape[1], grad_x + window + 1)
    local_patch = data2d[y1:y2, x1:x2]
    if np.any(~np.isnan(local_patch)):
        local_min_idx = np.nanargmin(local_patch)
        local_min_y, local_min_x = np.unravel_index(local_min_idx, local_patch.shape)
        abs_min_y = y1 + local_min_y
        abs_min_x = x1 + local_min_x

        if (extent[0] <= Lon2d[abs_min_y, abs_min_x] <= extent[1] and
            extent[2] <= Lat2d[abs_min_y, abs_min_x] <= extent[3]):
            already_plotted = any(np.hypot(abs_min_y - py, abs_min_x - px) < min_low_distance for py, px in plotted_low_points)
            if (max_grad_value > tight_gradient_threshold) and not already_plotted:
                ax.text(
                    Lon2d[abs_min_y, abs_min_x], Lat2d[abs_min_y, abs_min_x], "L",
                    color='red', fontsize=16, fontweight='bold',
                    ha='center', va='center', transform=ccrs.PlateCarree(),
                    zorder=3, path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()]
                )
                ax.text(
                    Lon2d[abs_min_y, abs_min_x], Lat2d[abs_min_y, abs_min_x]-0.7, f"{data2d[abs_min_y, abs_min_x]:.0f}",
                    color='red', fontsize=5, fontweight='bold',
                    ha='center', va='top', transform=ccrs.PlateCarree(),
                    zorder=3, path_effects=[path_effects.Stroke(linewidth=0.5, foreground='white'), path_effects.Normal()]
                )
                plotted_low_points.append((abs_min_y, abs_min_x))

    ax.set_axis_off()
    png_path = os.path.join(combined_dir, f"prate_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0, transparent=False, dpi=600, facecolor='white')
    plt.close(fig)
    print(f"Generated combined PNG: {png_path}")
    return png_path

# Main process
for step in forecast_steps:
    mslp_grib = get_mslp_grib(step)
    prate_grib = get_prate_grib(step)
    if mslp_grib and prate_grib:
        plot_combined(mslp_grib, prate_grib, step)
        gc.collect()
        time.sleep(3)

        print("All combined PNG creation tasks complete!")
        time.sleep(3)

# --- Delete all GRIB files in grib_dir after PNGs are made ---
for f in os.listdir(grib_dir):
    file_path = os.path.join(grib_dir, f)
    if os.path.isfile(file_path):
        os.remove(file_path)
print("All GRIB files deleted from grib_dir.")
