import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

def main():
    if len(sys.argv) != 6:
        print("Usage: make_map.py min_lat max_lat min_lon max_lon output_path")
        sys.exit(1)
    min_lat = float(sys.argv[1])
    max_lat = float(sys.argv[2])
    min_lon = float(sys.argv[3])
    max_lon = float(sys.argv[4])
    out_path = sys.argv[5]

    fig = plt.figure(figsize=(8, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor='#f0eada')
    ax.add_feature(cfeature.OCEAN, facecolor='#b3d1ff')
    ax.add_feature(cfeature.BORDERS, linewidth=0.7)
    ax.add_feature(cfeature.LAKES, facecolor='#b3d1ff', edgecolor='k', linewidth=0.5)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5)
    ax.set_title("Custom Map Extent", fontsize=14, pad=12)
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches='tight')
    plt.close(fig)
    print(f"Map saved to {out_path}")

if __name__ == "__main__":
    main()
