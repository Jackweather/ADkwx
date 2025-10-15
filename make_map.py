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

    fig = plt.figure(figsize=(10, 7), dpi=850)
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

    # Base map
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

    # Final touches
    ax.set_axis_off()
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(out_path, bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close(fig)
    print(f"{out_path} generated.")

if __name__ == "__main__":
    main()
