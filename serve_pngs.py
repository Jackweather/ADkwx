from flask import Blueprint, send_from_directory, abort
import os

BASE_DATA_DIR = '/var/data'

png_bp = Blueprint('png_bp', __name__)

# Helper to register routes dynamically
def register_png_route(route, subdir):
    @png_bp.route(route + '/<path:filename>')
    def serve_png(filename, subdir=subdir):
        directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', subdir)
        abs_path = os.path.join(directory, filename)
        if not os.path.isfile(abs_path):
            abort(404)
        return send_from_directory(directory, filename)

# List of (route, subdir) pairs
png_routes = [
    ('/PRATEGFS', 'PRATEGFS'),
    ('/tmp_surface', 'tmp_surface'),
    ('/6hour_precip_total', '6hour_precip_total'),
    ('/24hour_precip_total', '24hour_precip_total'),
    ('/12hour_precip_total', '12hour_precip_total'),
    ('/total_precip', 'total_precip'),
    ('/total_lcdc', 'total_lcdc'),
    ('/GFS/static/snow_depth', 'snow_depth'),
    ('/GFS/static/totalsnowfall_10to1', 'totalsnowfall_10to1'),
    ('/GFS/static/totalsnowfall_3to1', 'totalsnowfall_3to1'),
    ('/GFS/static/totalsnowfall_5to1', 'totalsnowfall_5to1'),
    ('/GFS/static/totalsnowfall_20to1', 'totalsnowfall_20to1'),
    ('/GFS/static/totalsnowfall_8to1', 'totalsnowfall_8to1'),
    ('/GFS/static/totalsnowfall_12to1', 'totalsnowfall_12to1'),
    ('/GFS/static/totalsnowfall_15to1', 'totalsnowfall_15to1'),
    ('/THICKNESS', 'THICKNESS'),
    ('/usa_pngs', 'usa_pngs'),
    ('/northeast_pngs', 'northeast_pngs'),
    ('/WIND_200', 'WIND_200'),
    ('/sunsd_surface', 'sunsd_surface'),
    ('/gfs_850mb', 'gfs_850mb'),
]

for route, subdir in png_routes:
    register_png_route(route, subdir)
