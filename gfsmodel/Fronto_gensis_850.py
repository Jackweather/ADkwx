import os
import requests
from datetime import datetime, timedelta
import pytz
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import time
import gc
from PIL import Image

BASE_DIR = '/var/data'
out_dir = os.path.join(BASE_DIR, "GFS", "static", "TMP850")
grib_dir = os.path.join(out_dir, "grib_files")
os.makedirs(grib_dir, exist_ok=True)
os.makedirs(out_dir, exist_ok=True)

base_url_0p25 = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
variable_tmp = "TMP"
level_850 = "lev_850_mb"
# add wind variables
variable_ugrd = "UGRD"
variable_vgrd = "VGRD"

# Current UTC time minus 6 hours (nearest available GFS cycle)
current_utc_time = datetime.utcnow() - timedelta(hours=6)
date_str = current_utc_time.strftime("%Y%m%d")
hour_str = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps (every 6 hours up to 384)
forecast_steps = [0] + list(range(6, 385, 6))

# --- smoothing configuration: increase SMOOTH_SIGMA for heavier smoothing,
#     and SMOOTH_ITER to apply gaussian smoothing multiple times ---
#SMOOTH_SIGMA = 6
#SMOOTH_ITER = 2
# make smoothing lighter: smaller sigma and a single pass
SMOOTH_SIGMA = 3
SMOOTH_ITER = 1


def download_grib(url, file_path):
    resp = requests.get(url, stream=True, timeout=60)
    if resp.status_code == 200:
        with open(file_path, 'wb') as fh:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    fh.write(chunk)
        print(f"Downloaded {os.path.basename(file_path)}")
        return file_path
    else:
        print(f"Failed to download {os.path.basename(file_path)} (Status Code: {resp.status_code})")
        return None

def get_tmp_grib(step):
    if step == 0:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f000"
    else:
        file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(grib_dir, f"tmp850_{file_name}")
    # request TMP, UGRD and VGRD at 850 mb in one file
    url = (
        f"{base_url_0p25}?file={file_name}"
        f"&{level_850}=on&var_{variable_tmp}=on&var_{variable_ugrd}=on&var_{variable_vgrd}=on"
        f"&subregion=&leftlon=220&rightlon=300&toplat=55&bottomlat=20"
        f"&dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
    )
    return download_grib(url, file_path)

# helper to find wind variable names in dataset
def find_var_by_candidates(ds, candidates):
	for c in candidates:
		if c in ds.data_vars:
			return c
	for var in ds.data_vars:
		attrs = ds[var].attrs
		if any(k in attrs and 'wind' in str(attrs[k]).lower() for k in ('long_name','standard_name','name')):
			return var
	return None

def find_temperature_variable(ds):
    # Try common names first, otherwise pick the first data variable
    candidates = ['t', 'tmp', 'temperature', 'air_temperature']
    for c in candidates:
        if c in ds.data_vars:
            return c
    # try variables whose long_name or standard_name contains "temperature"
    for var in ds.data_vars:
        attrs = ds[var].attrs
        if any(k in attrs and 'temper' in str(attrs[k]).lower() for k in ('long_name','standard_name','name')):
            return var
    # fallback to first data variable
    return list(ds.data_vars.keys())[0]

def plot_tmp850(grib_path, step):
    try:
        ds = xr.open_dataset(grib_path, engine="cfgrib")
    except Exception as e:
        print(f"Error opening dataset: {e}")
        return None

    # --- extract temperature variable ---
    temp_var = find_temperature_variable(ds)
    tmp = ds[temp_var].values.squeeze()  # likely in Kelvin
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons_plot = np.where(lons > 180, lons - 360, lons)
    if lats.ndim == 1 and lons.ndim == 1:
        Lon2d, Lat2d = np.meshgrid(lons_plot, lats)
        tmp2d = tmp
    else:
        Lon2d, Lat2d = lons_plot, lats
        tmp2d = tmp

    # Convert Kelvin to Celsius if values are > 200K on average
    if np.nanmean(tmp2d) > 200:
        tmp2d = tmp2d - 273.15

    # --- extract wind components (UGRD, VGRD) if present ---
    u = None; v = None
    u_cand = find_var_by_candidates(ds, ['u', 'ugrd', 'ugrd_850mb', 'u-component_of_wind','eastward_wind'])
    v_cand = find_var_by_candidates(ds, ['v', 'vgrd', 'vgrd_850mb', 'northward_wind'])
    if u_cand and v_cand:
        try:
            u = ds[u_cand].values.squeeze()
            v = ds[v_cand].values.squeeze()
        except Exception:
            u = None; v = None

    # If grid is 1D/2D ensure shapes align
    if u is not None and (lats.ndim == 1 and lons.ndim == 1):
        # u/v should already align with Lon2d/Lat2d; no regridding attempted here
        pass

    # --- Compute frontogenesis proxy if winds available ---
    frontogen = None
    if u is not None and v is not None:
        # convert degree spacing to meters
        R = 6371000.0  # Earth radius (m)
        # radians arrays
        lon_rad = np.deg2rad(Lon2d)
        lat_rad = np.deg2rad(Lat2d)
        # compute metric distances dx (zonal) and dy (meridional) for each grid cell
        # dx ~ R * cos(lat) * dlon, dy ~ R * dlat
        dlon = np.gradient(lon_rad, axis=1)
        dlat = np.gradient(lat_rad, axis=0)
        # handle shapes: if gradient returns scalars for 1D, broadcast
        if dlon.ndim == 0:
            dlon = np.full_like(Lon2d, dlon)
        if dlat.ndim == 0:
            dlat = np.full_like(Lat2d, dlat)
        dx = R * np.cos(lat_rad) * dlon
        dy = R * dlat

        # temperature gradients in x (zonal) and y (meridional)
        # gradient returns per-index differences; align axes: axis=1 -> zonal, axis=0 -> meridional
        dT_dlon = np.gradient(tmp2d, axis=1)
        dT_dlat = np.gradient(tmp2d, axis=0)
        # divide by metres
        with np.errstate(invalid='ignore', divide='ignore'):
            dTdx = dT_dlon / dx
            dTdy = dT_dlat / dy

        # magnitude of horizontal temp gradient
        gradT = np.sqrt(np.nan_to_num(dTdx)**2 + np.nan_to_num(dTdy)**2)

        # compute divergence of the horizontal wind: dudx + dvdy
        du_dlon = np.gradient(u, axis=1)
        dv_dlat = np.gradient(v, axis=0)
        with np.errstate(invalid='ignore', divide='ignore'):
            dudx = du_dlon / dx
            dvdy = dv_dlat / dy
        div = dudx + dvdy

        # frontogenesis proxy: positive when convergence (div negative) and strong temp gradient
        # Use: frontogen = - gradT * div  (units K/m * 1/s)
        frontogen = - gradT * div

        # --- iterative nan-aware Gaussian smoothing of frontogenesis (strong smoothing) ---
        try:
            from scipy.ndimage import gaussian_filter

            def _smooth_nan(data, sigma):
                # nan-aware gaussian smoothing: convolve values and weights, then divide
                mask = np.isfinite(data).astype(float)
                data_filled = np.where(np.isfinite(data), data, 0.0)
                num = gaussian_filter(data_filled, sigma=sigma, mode='nearest')
                den = gaussian_filter(mask, sigma=sigma, mode='nearest')
                with np.errstate(invalid='ignore', divide='ignore'):
                    out = num / den
                out[den == 0] = np.nan
                return out

            # apply smoothing iteratively for a stronger low-pass effect
            for _ in range(max(1, SMOOTH_ITER)):
                frontogen = _smooth_nan(frontogen, SMOOTH_SIGMA)
        except Exception:
            # scipy not available or smoothing failed — proceed without smoothing
            pass

    # Temperature contour mesh (keep as optional background)
    levels = np.arange(-40, 41, 1)
    cmap = plt.get_cmap('RdYlBu_r')
    norm = BoundaryNorm(levels, ncolors=cmap.N, clip=True)

    fig = plt.figure(figsize=(12,8), dpi=300, facecolor='white')
    ax = plt.axes(projection=ccrs.PlateCarree(), facecolor='white')
    extent = [-130, -65, 20, 54]
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 8}
    gl.ylabel_style = {'size': 8}

    # Plot frontogenesis proxy if available
    if frontogen is not None:
        # create symmetric levels around zero based on max absolute value for stable plotting
        maxabs = np.nanmax(np.abs(frontogen))
        if not np.isfinite(maxabs) or maxabs == 0:
            print(f"Frontogenesis invalid or zero for step {step}, skipping.")
            plt.close(fig)
            return None

        # --- mask small near-zero values so they don't plot ---
        # threshold: fraction of peak (e.g., 2%) or a tiny absolute floor
        frac_threshold = 0.02
        abs_floor = 1e-12
        threshold = max(maxabs * frac_threshold, abs_floor)
        frontogen_masked = np.where(np.abs(frontogen) < threshold, np.nan, frontogen)

        # if everything got masked, skip plotting
        if not np.any(np.isfinite(frontogen_masked)):
            print(f"Frontogenesis values below threshold for step {step}, skipping.")
            plt.close(fig)
            return None

        # use masked data to define levels (symmetric)
        maxabs_masked = np.nanmax(np.abs(frontogen_masked))
        f_levels = np.linspace(-maxabs_masked, maxabs_masked, 21)
        fcmap = plt.get_cmap('seismic')
        fmesh = ax.contourf(
            Lon2d, Lat2d, frontogen_masked,
            levels=f_levels,
            cmap=fcmap,
            extend='both',
            transform=ccrs.PlateCarree(),
            alpha=0.9,
            zorder=2
        )
        # No wind barbs/quivers — frontogenesis-only output per request
        # place colorbar lower so it doesn't force extra whitespace above the axes
        cbax = fig.add_axes([0.13, 0.06, 0.74, 0.02])
        cbar = plt.colorbar(fmesh, cax=cbax, orientation='horizontal')
        cbar.set_label("Frontogenesis proxy (K/m * 1/s; positive = frontogenesis)", fontsize=8)
        cbar.ax.tick_params(labelsize=7)
    else:
        # no frontogenesis possible without winds — skip saving as user requested frontogenesis-only PNGs
        print(f"No wind/components for frontogenesis at step {step}, skipping.")
        plt.close(fig)
        return None

    # Optional: add temperature contours on top for reference
    # temperature contour lines every 3°C (include 0)
    temp_levels = np.arange(-40, 40+1, 3)
    # color mapping: blue for 0 and all negative levels; red for positive levels (3,6,9,...)
    temp_colors = ['blue' if lev <= 0 else 'red' for lev in temp_levels]
    cs = ax.contour(
         Lon2d, Lat2d, tmp2d,
         levels=temp_levels,
         colors=temp_colors,
         linewidths=0.6,
         transform=ccrs.PlateCarree(),
         zorder=4
     )
     # label contours with matching colors
     # slightly larger labels for readability; use matching colors
    try:
        ax.clabel(cs, fmt='%d', fontsize=8, colors=temp_colors)
    except Exception:
         ax.clabel(cs, fmt='%d', fontsize=8)

    run_str = f"{hour_str}z"
    valid_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H") + timedelta(hours=step)
    init_time = datetime.strptime(date_str + hour_str, "%Y%m%d%H")
    utc = pytz.utc
    eastern = pytz.timezone('US/Eastern')
    valid_time_utc = utc.localize(valid_time)
    valid_time_est = valid_time_utc.astimezone(eastern)
    title_str = (
        f"GFS 0.25° | 850 mb Frontogenesis proxy (and wind)\n"
        f"Valid: {valid_time_est:%Y-%m-%d %I:%M %p %Z}  |  "
        f"Init: {init_time:%Y-%m-%d %H:%M UTC}  |  Forecast Hour: {step:03d}  |  Run: {run_str}"
    )
    # Place a compact figure-level title immediately above the axes (no extra white band)
    fig.suptitle(title_str, fontsize=11, fontweight='bold', x=0.01, ha='left', y=0.995)

    # Tighten the top margin so the map fills up to just below the suptitle;
    # only the suptitle area remains white above the map
    plt.subplots_adjust(left=0.03, right=0.97, top=0.985, bottom=0.12, hspace=0)
    ax.set_axis_off()
    png_path = os.path.join(out_dir, f"tmp850_frontogen_gfs_{step:03d}.png")
    plt.savefig(png_path, bbox_inches='tight', pad_inches=0.05, transparent=False, dpi=300, facecolor='white')
    plt.close(fig)
    print(f"Generated TMP850 Frontogenesis PNG: {png_path}")
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
    grib = get_tmp_grib(step)
    if grib:
        png = plot_tmp850(grib, step)
        gc.collect()
        time.sleep(1)

# Clean up GRIBs
for f in os.listdir(grib_dir):
    fp = os.path.join(grib_dir, f)
    if os.path.isfile(fp):
        try:
            os.remove(fp)
        except Exception:
            pass

# Optimize PNGs
for f in os.listdir(out_dir):
    if f.lower().endswith('.png'):
        optimize_png(os.path.join(out_dir, f))

print("TMP850 processing complete.")