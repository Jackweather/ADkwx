from flask import Flask, send_from_directory, abort, request, jsonify
import os
import subprocess
import traceback
import getpass
import logging
import threading
import json
from datetime import datetime
import pytz
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Suppress 404 logging for /PRATEGFS/ and /tmp_surface/ image requests in werkzeug logger
logging.getLogger('werkzeug').addFilter(
    lambda record: not (
        (('GET /PRATEGFS/' in record.getMessage() or 'GET /tmp_surface/' in record.getMessage()) and '404' in record.getMessage())
    )
)

BASE_DATA_DIR = '/var/data'

# Mapping of URL prefix to subdirectory path
IMAGE_ROUTE_MAP = {
    'PRATEGFS': ['GFS', 'static', 'PRATEGFS'],
    'tmp_surface': ['GFS', 'static', 'tmp_surface'],
    '6hour_precip_total': ['GFS', 'static', '6hour_precip_total'],
    '24hour_precip_total': ['GFS', 'static', '24hour_precip_total'],
    '12hour_precip_total': ['GFS', 'static', '12hour_precip_total'],
    'total_precip': ['GFS', 'static', 'total_precip'],
    'total_lcdc': ['GFS', 'static', 'total_lcdc'],
    'GFS/static/snow_depth': ['GFS', 'static', 'snow_depth'],
    'GFS/static/totalsnowfall_10to1': ['GFS', 'static', 'totalsnowfall_10to1'],
    'GFS/static/totalsnowfall_3to1': ['GFS', 'static', 'totalsnowfall_3to1'],
    'GFS/static/totalsnowfall_5to1': ['GFS', 'static', 'totalsnowfall_5to1'],
    'GFS/static/totalsnowfall_20to1': ['GFS', 'static', 'totalsnowfall_20to1'],
    'GFS/static/totalsnowfall_8to1': ['GFS', 'static', 'totalsnowfall_8to1'],
    'GFS/static/totalsnowfall_12to1': ['GFS', 'static', 'totalsnowfall_12to1'],
    'GFS/static/totalsnowfall_15to1': ['GFS', 'static', 'totalsnowfall_15to1'],
    'THICKNESS': ['GFS', 'static', 'THICKNESS'],
    'usa_pngs': ['GFS', 'static', 'usa_pngs'],
    'northeast_pngs': ['GFS', 'static', 'northeast_pngs'],
    'WIND_200': ['GFS', 'static', 'WIND_200'],
    'sunsd_surface': ['GFS', 'static', 'sunsd_surface'],
    'gfs_850mb': ['GFS', 'static', 'gfs_850mb'],
    'vort850_surface': ['GFS', 'static', 'vort850_surface'],
    'DZDT850': ['GFS', 'static', 'DZDT850'],
    'LFTX': ['GFS', 'static', 'LFTX'],
    'northeast_tmp_pngs': ['GFS', 'static', 'northeast_tmp_pngs'],
    'northeast_precip_pngs': ['GFS', 'static', 'northeast_precip_pngs'],
    'northeast_12hour_precip_pngs': ['GFS', 'static', 'northeast_12hour_precip_pngs'],
    'northeast_24hour_precip_pngs': ['GFS', 'static', 'northeast_24hour_precip_pngps'],
    'northeast_total_precip_pngs': ['GFS', 'static', 'northeast_total_precip_pngs'],
    'northeast_gust_pngs': ['GDAS', 'static', 'GUST_NE'],
    'GFS/static/TMP850': ['GFS', 'static', 'TMP850'],
    'TMP850': ['GFS', 'static', 'TMP850'],
}

@app.route('/')
def index():
    with open('parent.html', 'r', encoding='utf-8') as f:
        html = f.read()
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'PRATEGFS')
    images_html = ''.join(
        f'<img src="/PRATEGFS/{png}" alt="{png}"><br>\n'
        for png in sorted(f for f in os.listdir(directory) if f.endswith('.png'))
    )
    return html.replace('<!--IMAGES-->', images_html)

@app.route('/<path:prefix>/<path:filename>')
def serve_image(prefix, filename):
    matched_key = None
    matched_subpath = None
    for key in sorted(IMAGE_ROUTE_MAP.keys(), key=lambda x: -len(x)):
        if prefix == key or prefix.startswith(key + '/'):
            matched_key = key
            matched_subpath = prefix[len(key):].lstrip('/')
            break
    if matched_key:
        directory = os.path.join(BASE_DATA_DIR, *IMAGE_ROUTE_MAP[matched_key])
        if matched_subpath:
            filename = os.path.join(matched_subpath, filename)
        abs_path = os.path.join(directory, filename)
        print(f"[DEBUG] Trying to serve: {abs_path}")  # <--- Add this line
        if not os.path.isfile(abs_path):
            print(f"[DEBUG] File not found: {abs_path}")  # <--- Add this line
            abort(404, description=f"File not found: {abs_path}")
        return send_from_directory(directory, filename)
    print(f"[DEBUG] No mapping for prefix: {prefix}")  # <--- Add this line
    abort(404, description=f"No mapping for prefix: {prefix}")

@app.route('/GFS/static/<path:filename>')
def serve_gfs_static(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/gifs.html')
def gifs_html():
    with open('gifs.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/gfs.html')
def serve_gfs_html():
    return send_from_directory(os.path.dirname(__file__), 'gfs.html')

@app.route('/updates.html')
def serve_updates_html():
    return send_from_directory(os.path.dirname(__file__), 'updates.html')

@app.route('/community.html')
def serve_community_html():
    return send_from_directory(os.path.dirname(__file__), 'community.html')

@app.route('/snow.html')
def serve_snow_html():
    return send_from_directory(os.path.dirname(__file__), 'snow.html')

@app.route('/parent.html')
def serve_parent_html():
    return send_from_directory(os.path.dirname(__file__), 'parent.html')

@app.route('/snowparent.html')
def serve_snowparent_html():
    return send_from_directory(os.path.dirname(__file__), 'snowparent.html')

@app.route('/plotter.html')
def serve_plotter_html():
    return send_from_directory(os.path.dirname(__file__), 'plotter.html')

@app.route('/Gifs/<path:filename>')
def serve_gif(filename):
    directory = '/var/data'  # GIFs are saved here
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route("/run-task1")
def run_task1():
    def run_all_scripts():
        print("Flask is running as user:", getpass.getuser())  # Print user for debugging
        scripts_raw = [
            ("/opt/render/project/src/gfsmodel/mslp_prate.py", "/opt/render/project/src/gfsmodel"),                 # 1
            ("/opt/render/project/src/gfsmodel/tmp_surface_clean.py", "/opt/render/project/src/gfsmodel"),          # 2
            ("/opt/render/project/src/gfsmodel/6hourmaxprecip.py", "/opt/render/project/src/gfsmodel"),            # 3
            ("/opt/render/project/src/gfsmodel/12hour_precip.py", "/opt/render/project/src/gfsmodel"),             # 4
            ("/opt/render/project/src/gfsmodel/24hour_precip.py", "/opt/render/project/src/gfsmodel"),             # 5
            ("/opt/render/project/src/gfsmodel/total_precip.py", "/opt/render/project/src/gfsmodel"),              # 6
            ("/opt/render/project/src/gfsmodel/total_cloud_cover.py", "/opt/render/project/src/gfsmodel"),         # 7
            ("/opt/render/project/src/gfsmodel/snowdepth.py", "/opt/render/project/src/gfsmodel"),                 # 8
            ("/opt/render/project/src/gfsmodel/totalsnowfall_3to1.py", "/opt/render/project/src/gfsmodel"),       # 9
            ("/opt/render/project/src/gfsmodel/totalsnowfall_5to1.py", "/opt/render/project/src/gfsmodel"),       # 10
            ("/opt/render/project/src/gfsmodel/totalsnowfall_20to1.py", "/opt/render/project/src/gfsmodel"),      # 11
            ("/opt/render/project/src/gfsmodel/totalsnowfall_8to1.py", "/opt/render/project/src/gfsmodel"),       # 12
            ("/opt/render/project/src/gfsmodel/totalsnowfall_12to1.py", "/opt/render/project/src/gfsmodel"),      # 13
            ("/opt/render/project/src/gfsmodel/totalsnowfall_15to1.py", "/opt/render/project/src/gfsmodel"),      # 14
            ("/opt/render/project/src/gfsmodel/totalsnowfall_10to1.py", "/opt/render/project/src/gfsmodel"),      # 15
            ("/opt/render/project/src/gfsmodel/thickness_1000_500.py", "/opt/render/project/src/gfsmodel"),       # 16
            ("/opt/render/project/src/gfsmodel/wind_200.py", "/opt/render/project/src/gfsmodel"),                  # 17
            ("/opt/render/project/src/gfsmodel/sunsd_surface_clean.py", "/opt/render/project/src/gfsmodel"),       # 18
            ("/opt/render/project/src/gfsmodel/gfs_850mb_plot.py", "/opt/render/project/src/gfsmodel"),            # 19
            ("/opt/render/project/src/gfsmodel/vort850_surface_clean.py", "/opt/render/project/src/gfsmodel"),    # 20
            ("/opt/render/project/src/gfsmodel/dzdt_850.py", "/opt/render/project/src/gfsmodel"),                  # 21
            ("/opt/render/project/src/gfsmodel/lftx_surface.py", "/opt/render/project/src/gfsmodel"),             # 22
            ("/opt/render/project/src/gfsmodel/gfs_gust_northeast.py", "/opt/render/project/src/gfsmodel"),       # 23
            ("/opt/render/project/src/gfsmodel/Fronto_gensis_850.py", "/opt/render/project/src/gfsmodel"),        # 24
            ("/opt/render/project/src/Gifs/gif.py", "/opt/render/project/src/Gifs"),                              # 25 (GIF)
        ]
        # tag with original indices
        scripts = [(i, s, c) for i, (s, c) in enumerate(scripts_raw, start=1)]
        total = len(scripts)

        # show numbered list before running
        print("Scripts to run:")
        for idx, s, _ in scripts:
            print(f"{idx}. {os.path.basename(s)}")

        # separate GIF (last entry) to run after parallel sequences
        gif_entry = scripts[-1]  # (idx, path, cwd)
        work_entries = scripts[:-1]

        # split into odds and evens by original index
        odds = [entry for entry in work_entries if entry[0] % 2 == 1]
        evens = [entry for entry in work_entries if entry[0] % 2 == 0]

        def run_sequence(label, entries):
            for idx, script, cwd in entries:
                task_label = f"{idx}/{total}"
                print(f"[{label}][{task_label}] Running: {os.path.basename(script)} (cwd: {cwd})")
                try:
                    result = subprocess.run(
                        ["python", script],
                        check=True, cwd=cwd,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    print(f"[{label}][{task_label}] {os.path.basename(script)} ran successfully!")
                    if result.stdout:
                        print(f"[{label}][{task_label}] STDOUT: {result.stdout}")
                    if result.stderr:
                        print(f"[{label}][{task_label}] STDERR: {result.stderr}")
                except subprocess.CalledProcessError as e:
                    error_trace = traceback.format_exc()
                    print(f"[{label}][{task_label}] Error running {os.path.basename(script)}:\n{error_trace}")
                    if hasattr(e, "stdout") and e.stdout:
                        print(f"[{label}][{task_label}] STDOUT: {e.stdout}")
                    if hasattr(e, "stderr") and e.stderr:
                        print(f"[{label}][{task_label}] STDERR: {e.stderr}")

        # start two threads: one for odds, one for evens (they run sequentially within each thread)
        thread_odd = threading.Thread(target=run_sequence, args=("ODD", odds))
        thread_even = threading.Thread(target=run_sequence, args=("EVEN", evens))
        thread_odd.start()
        thread_even.start()
        # wait for both to finish
        thread_odd.join()
        thread_even.join()

        # finally run the GIF script (last)
        gif_idx, gif_script, gif_cwd = gif_entry
        gif_label = f"{gif_idx}/{total}"
        print(f"[GIF][{gif_label}] Running GIF: {os.path.basename(gif_script)} (cwd: {gif_cwd})")
        try:
            result = subprocess.run(
                ["python", gif_script],
                check=True, cwd=gif_cwd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print(f"[GIF][{gif_label}] {os.path.basename(gif_script)} ran successfully!")
            if result.stdout:
                print(f"[GIF][{gif_label}] STDOUT: {result.stdout}")
            if result.stderr:
                print(f"[GIF][{gif_label}] STDERR: {result.stderr}")
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"[GIF][{gif_label}] Error running {os.path.basename(gif_script)}:\n{error_trace}")
            if hasattr(e, "stdout") and e.stdout:
                print(f"[GIF][{gif_label}] STDOUT: {e.stdout}")
            if hasattr(e, "stderr") and e.stderr:
                print(f"[GIF][{gif_label}] STDERR: {e.stderr}")
    threading.Thread(target=run_all_scripts).start()
    return "Task started in background! Check logs folder for output.", 200

# Ensure chat retrieval and map routes are defined (matches your snippet)
@app.route('/get-chats', methods=['GET'])
def get_chats():
    messages = []
    if os.path.exists('chatlog.txt'):
        with open('chatlog.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg_obj = json.loads(line)
                    messages.append(msg_obj)
                except Exception:
                    # fallback for old format
                    messages.append({'text': line, 'timestamp': ''})
    return jsonify({'messages': messages})

@app.route('/make-map', methods=['POST'])
def make_map():
    data = request.get_json()
    min_lat = data.get('min_lat')
    max_lat = data.get('max_lat')
    min_lon = data.get('min_lon')
    max_lon = data.get('max_lon')
    # Validate input
    try:
        min_lat = float(min_lat)
        max_lat = float(max_lat)
        min_lon = float(min_lon)
        max_lon = float(max_lon)
    except Exception:
        return jsonify({'error': 'Invalid coordinates'}), 400
    # Output file path: create a timestamped filename so the top-right world_map.png is never overwritten
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"world_map_{timestamp}.png"
    out_path = os.path.join('plotter', filename)
    # Call the map generator script
    try:
        result = subprocess.run(
            ["python", "make_map.py", str(min_lat), str(max_lat), str(min_lon), str(max_lon), out_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("Map generated:", result.stdout)
    except Exception as e:
        print("Map generation error:", e)
        return jsonify({'error': 'Map generation failed'}), 500
    # Return the URL for the new map image
    return jsonify({'url': f'/plotter/{filename}'})

@app.route('/plotter/<path:filename>')
def serve_plotter_map(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'plotter'), filename)

if __name__ == '__main__':
    app.run(debug=True)
