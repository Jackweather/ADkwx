import os
import requests
from datetime import datetime, timedelta
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature

BASE_DIR = '/var/data'
output_dir = os.path.join(BASE_DIR, "GFS")
crain_dir = os.path.join(output_dir, "static", "CRAIN")
grib_dir = os.path.join(crain_dir, "grib_files")
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(crain_dir, exist_ok=True)

base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_crain = "CRAIN"
variable_csnow = "CSNOW"
variable_cfrzr = "CFRZR"
variable_cicep = "CICEP"  # Add CICEP variable

# Use current UTC time minus 6 hours for nearest GFS cycle
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)
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

def get_crain_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"crain_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_crain}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_csnow_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"csnow_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_csnow}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_cfrzr_grib(step):
    # Use 0.25-degree GFS for CFRZR
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"cfrzr_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_cfrzr}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def get_cicep_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"cicep_{file_name}")
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&lev_surface=on&var_{variable_cicep}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

def plot_crain(crain_path, csnow_path, cfrzr_path, cicep_path, step):
    try:
        ds = xr.open_dataset(crain_path, engine="cfgrib", filter_by_keys={"stepType": "instant"})
    except Exception as e:
        print(f"Error opening CRAIN dataset: {e}")
        return None

    crain = ds['crain'].values
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        crain2d = crain.squeeze()
    else:
        Lon2d, Lat2d = lons_plot, lats
        crain2d = crain.squeeze()

    # --- CSNOW overlay ---
    csnow2d = None
    if csnow_path and os.path.exists(csnow_path):
        try:
            ds_snow = xr.open_dataset(csnow_path, engine="cfgrib", filter_by_keys={"stepType": "instant"})
            csnow = ds_snow['csnow'].values
            if lats.ndim == 1 and lons.ndim == 1:
                csnow2d = csnow.squeeze()
            else:
                csnow2d = csnow.squeeze()
        except Exception as e:
            print(f"Error opening CSNOW dataset: {e}")
            csnow2d = None

    # --- CFRZR overlay (0.25-degree grid) ---
    cfrzr2d = None
    if cfrzr_path and os.path.exists(cfrzr_path):
        try:
            ds_cfrzr = xr.open_dataset(cfrzr_path, engine="cfgrib", filter_by_keys={"stepType": "instant"})
            cfrzr = ds_cfrzr['cfrzr'].values
            if lats.ndim == 1 and lons.ndim == 1:
                cfrzr2d = cfrzr.squeeze()
            else:
                cfrzr2d = cfrzr.squeeze()
        except Exception as e:
            print(f"Error opening CFRZR dataset: {e}")
            cfrzr2d = None

    # --- CICEP overlay (purple, for every step) ---
    cicep2d = None
    if cicep_path and os.path.exists(cicep_path):
        try:
            ds_cicep = xr.open_dataset(cicep_path, engine="cfgrib", filter_by_keys={"stepType": "instant"})
            cicep = ds_cicep['cicep'].values
            if lats.ndim == 1 and lons.ndim == 1:
                cicep2d = cicep.squeeze()
            else:
                cicep2d = cicep.squeeze()
        except Exception as e:
            print(f"Error opening CICEP dataset: {e}")
            cicep2d = None

    # Use constrained_layout to minimize whitespace
    fig = plt.figure(figsize=(10, 7), dpi=300, facecolor='white', constrained_layout=True)
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # --- Title block (move down to touch the top of the plot, no extra space) ---
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
        f"GFS Model {valid_time.strftime('%y%m%d')} {hour_str_fmt}  {day_of_week}  Forecast Hour: {step}  Run: {run_str}\n"
        f"Rain (Green), Snow (Blue), Freezing Rain (Pink), Ice Pellets (Purple)"
    )
    # Use ax.set_title instead of suptitle for tight layout
    ax.set_title(title_str, fontsize=12, fontweight='bold', loc='center', pad=8)

    # Basemap features
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    # --- Combined mask: blue for snow, green for rain, no gap ---
    combined = np.full_like(crain2d, np.nan, dtype=float)
    if csnow2d is not None:
        combined[(csnow2d == 1)] = 2
    combined[(crain2d == 1) & ~(combined == 2)] = 1

    from matplotlib.colors import ListedColormap, BoundaryNorm
    cmap = ListedColormap(['green', 'blue'])
    bounds = [1, 2, 3]
    norm = BoundaryNorm(bounds, cmap.N)

    img = ax.contourf(
        Lon2d, Lat2d, combined,
        levels=[0.5, 1.5, 2.5],
        cmap=cmap,
        norm=norm,
        alpha=0.7,
        transform=ccrs.PlateCarree(),
        zorder=2
    )

    # Overlay purple where CICEP==1 (on 0.25-degree grid, for every step) -- always on top
    overlay_handles = []
    overlay_labels = []
    if cicep2d is not None:
        cicep_mask = (cicep2d == 1)
        cicep_plot = np.where(cicep_mask, 1, np.nan)
        cmap_cicep = ListedColormap(['purple'])
        overlay = ax.contourf(
            Lon2d, Lat2d, cicep_plot,
            levels=[0.5, 1.5],
            cmap=cmap_cicep,
            alpha=0.7,
            transform=ccrs.PlateCarree(),
            zorder=20
        )
        overlay_handles.append(plt.Rectangle((0,0),1,1, color='purple', alpha=0.7))
        overlay_labels.append('Ice Pellets')

    # Overlay dark pink where CFRZR==1 (on 0.25-degree grid) -- above everything except CICEP
    if cfrzr2d is not None:
        cfrzr_mask = (cfrzr2d == 1)
        cfrzr_plot = np.where(cfrzr_mask, 1, np.nan)
        cmap_cfrzr = ListedColormap(['#d1006f'])  # dark pink
        overlay = ax.contourf(
            Lon2d, Lat2d, cfrzr_plot,
            levels=[0.5, 1.5],
            cmap=cmap_cfrzr,
            alpha=0.7,
            transform=ccrs.PlateCarree(),
            zorder=15
        )
        overlay_handles.append(plt.Rectangle((0,0),1,1, color='#d1006f', alpha=0.7))
        overlay_labels.append('Freezing Rain')

    # --- Custom horizontal colorbar for all precip types (Rain, Snow, Freezing Rain, Ice Pellets) ---
    from matplotlib.patches import Rectangle
    # Move colorbar up to just below the plot (reduce bottom margin)
    legend_cax = fig.add_axes([0.15, 0.04, 0.7, 0.04])  # [left, bottom, width, height]
    legend_cax.axis('off')
    bar_width = 0.18
    spacing = 0.04
    y0 = 0.25

    legend_cax.add_patch(Rectangle((0.0, y0), bar_width, 0.5, color='green', alpha=0.7, transform=legend_cax.transAxes, clip_on=False))
    legend_cax.text(0.0 + bar_width/2, y0 + 0.25, "Rain", color='black', fontsize=8, ha='center', va='center', transform=legend_cax.transAxes)
    legend_cax.add_patch(Rectangle((bar_width + spacing, y0), bar_width, 0.5, color='blue', alpha=0.7, transform=legend_cax.transAxes, clip_on=False))
    legend_cax.text(bar_width + spacing + bar_width/2, y0 + 0.25, "Snow", color='black', fontsize=8, ha='center', va='center', transform=legend_cax.transAxes)
    legend_cax.add_patch(Rectangle((2*(bar_width + spacing), y0), bar_width, 0.5, color='#d1006f', alpha=0.7, transform=legend_cax.transAxes, clip_on=False))
    legend_cax.text(2*(bar_width + spacing) + bar_width/2, y0 + 0.25, "Freezing Rain", color='black', fontsize=8, ha='center', va='center', transform=legend_cax.transAxes)
    legend_cax.add_patch(Rectangle((3*(bar_width + spacing), y0), bar_width, 0.5, color='purple', alpha=0.7, transform=legend_cax.transAxes, clip_on=False))
    legend_cax.text(3*(bar_width + spacing) + bar_width/2, y0 + 0.25, "Ice Pellets", color='black', fontsize=8, ha='center', va='center', transform=legend_cax.transAxes)

    # Remove the default colorbar and overlay legend
    # --- Colorbar for precip type at the bottom ---
    # cax = fig.add_axes([0.15, 0.12, 0.7, 0.02])
    # cbar = plt.colorbar(img, cax=cax, orientation='horizontal', ticks=[1, 2])
    # cbar.ax.set_xticklabels(['Rain', 'Snow'])
    # cbar.set_label("Precipitation Type", fontsize=8)
    # cbar.ax.tick_params(labelsize=8)
    # cbar.ax.set_facecolor('white')
    # cbar.outline.set_edgecolor('black')

    # --- Overlay legend as a colorbar-like box below the main colorbar ---
    # if overlay_handles:
    #     from matplotlib.legend import Legend
    #     legend = Legend(ax, overlay_handles, overlay_labels, loc='lower center', bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False, fontsize=8)
    #     ax.add_artist(legend)

    ax.set_axis_off()
    png_path = os.path.join(crain_dir, f"usa_gfs_crain_{step:03d}.png")
    plt.savefig(
        png_path,
        bbox_inches='tight',
        pad_inches=0,  # No extra padding
        transparent=False,
        dpi=300,
        facecolor='white'
    )
    plt.close(fig)
    print(f"Generated CRAIN+CSNOW+CFRZR+CICEP PNG: {png_path}")
    return png_path

# Main process
for step in forecast_steps:
    crain_grib = get_crain_grib(step)
    csnow_grib = get_csnow_grib(step)
    cfrzr_grib = get_cfrzr_grib(step)
    cicep_grib = get_cicep_grib(step)
    if crain_grib:
        plot_crain(crain_grib, csnow_grib, cfrzr_grib, cicep_grib, step)

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

for f in os.listdir(crain_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(crain_dir, f))

print("All PNGs optimized.")

