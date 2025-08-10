import matplotlib
matplotlib.use('Agg')
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader

fig = plt.figure(figsize=(10, 7), dpi=850)
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([-126, -69, 24, 50], crs=ccrs.PlateCarree())

# Base map
ax.add_feature(cfeature.LAND, facecolor='lightgray')
ax.add_feature(cfeature.OCEAN, facecolor='white')
ax.add_feature(cfeature.COASTLINE, linewidth=0.7)
ax.add_feature(cfeature.BORDERS, linewidth=0.5)
ax.add_feature(cfeature.STATES, linewidth=0.3)
ax.add_feature(cfeature.RIVERS, linewidth=0.4, edgecolor='blue')
ax.add_feature(cfeature.LAKES, facecolor='lightblue', edgecolor='blue', linewidth=0.3)

# Counties shapefile path (relative)
shapefile_path = r"shapefile\tl_2023_us_county.shp"

# Read and add counties
reader = shpreader.Reader(shapefile_path)
counties = cfeature.ShapelyFeature(reader.geometries(), ccrs.PlateCarree())

ax.add_feature(counties, facecolor='none', edgecolor='black', linewidth=0.1)

# Final touches
ax.set_axis_off()
plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
plt.savefig("cartopy_base1.png", bbox_inches='tight', pad_inches=0, transparent=True)
plt.close(fig)
print("cartopy_base.png with counties generated.")