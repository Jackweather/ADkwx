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
import shutil

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
        scripts = [
            ("/opt/render/project/src/gfsmodel/mslp_prate.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/tmp_surface_clean.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/6hourmaxprecip.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/12hour_precip.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/24hour_precip.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/total_precip.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/total_cloud_cover.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/snowdepth.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_3to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_5to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_20to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_8to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_12to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_15to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/totalsnowfall_10to1.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/thickness_1000_500.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/wind_200.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/sunsd_surface_clean.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/gfs_850mb_plot.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/vort850_surface_clean.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/dzdt_850.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/lftx_surface.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/gfs_gust_northeast.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/gfsmodel/Fronto_gensis_850.py", "/opt/render/project/src/gfsmodel"),
            ("/opt/render/project/src/Gifs/gif.py", "/opt/render/project/src/Gifs"),
        ]

        # Helper to run a single script with CPU affinity (cpu 0) and lower niceness.
        def run_script(script, cwd, cpu=0):
            base_cmd = ["python", script]
            # Prefer preexec_fn approach (os.sched_setaffinity), fallback to taskset wrapper if needed.
            preexec = None
            cmd = list(base_cmd)
            if hasattr(os, "sched_setaffinity"):
                def _preexec():
                    try:
                        # bind child to single CPU and lower priority
                        os.sched_setaffinity(0, {cpu})
                    except Exception as e:
                        print("sched_setaffinity failed:", e)
                    try:
                        os.nice(10)
                    except Exception:
                        pass
                preexec = _preexec
            elif shutil.which("taskset"):
                # use taskset and nice if sched_setaffinity not available
                cmd = ["taskset", "-c", str(cpu), "nice", "-n", "10"] + base_cmd
            else:
                # no affinity mechanism available; just lower niceness
                try:
                    os.nice(10)
                except Exception:
                    pass

            def _launch(cmd, preexec, cwd):
                try:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        preexec_fn=preexec
                    )
                    out, err = proc.communicate()
                    return proc.returncode, out, err
                except Exception as e:
                    return 1, "", f"Exception launching process: {e}"

            # First attempt
            rc, out, err = _launch(cmd, preexec, cwd)
            # Detect cartopy/shapefile corruption or incomplete downloads (common symptom: struct.error unpack)
            bad_signals = ("unpack requires a buffer", "struct.error", "Downloading:", "DownloadWarning", "shapereader")
            def _is_cartopy_error(text):
                if not text:
                    return False
                low = text.lower()
                return any(s in low for s in [b.lower() for b in bad_signals])

            if rc != 0 and _is_cartopy_error(err):
                print(f"[DEBUG] Detected possible corrupted cartopy data when running {os.path.basename(script)}. Cleaning cache and retrying...")
                # common cartopy cache locations to remove
                home = os.path.expanduser("~")
                candidates = [
                    os.path.join(home, ".local", "share", "cartopy"),
                    os.path.join(home, ".cache", "cartopy"),
                    os.path.join(home, ".local", "share", "natural_earth"),
                    os.path.join("/opt/render", ".cache", "cartopy"),
                    os.path.join("/tmp", "cartopy"),
                ]
                for path in candidates:
                    try:
                        if os.path.exists(path):
                            print(f"[DEBUG] Removing cartopy cache: {path}")
                            shutil.rmtree(path, ignore_errors=True)
                    except Exception as e:
                        print(f"[DEBUG] Failed to remove {path}: {e}")
                # small delay to let remote downloads stabilize
                time.sleep(2)
                # retry once
                rc2, out2, err2 = _launch(cmd, preexec, cwd)
                # If retry still shows a cartopy-related failure, log and treat as non-fatal (return success)
                if rc2 != 0 and _is_cartopy_error(err2):
                    print(f"[WARNING] {os.path.basename(script)} failed due to cartopy/shapefile issue after retry. Continuing pipeline.")
                    # return success but include stderr so logs show the issue
                    return 0, out2 or out, err2 or err
                # otherwise return retry result
                return rc2, out2, err2
            # If initial error was cartopy-related but didn't enter retry block (edge cases), treat non-fatal
            if rc != 0 and _is_cartopy_error(err):
                print(f"[WARNING] {os.path.basename(script)} failed due to cartopy/shapefile issue. Continuing pipeline.")
                return 0, out, err
            return rc, out, err

        # Run at most 2 scripts concurrently; all processes are affined to CPU 0 so combined usage ~1 CPU
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {ex.submit(run_script, script, cwd): (script, cwd) for script, cwd in scripts}
            for fut in as_completed(futures):
                script, cwd = futures[fut]
                try:
                    rc, out, err = fut.result()
                    if rc == 0:
                        print(f"{os.path.basename(script)} ran successfully!")
                    else:
                        print(f"{os.path.basename(script)} failed with rc={rc}")
                    if out:
                        print("STDOUT:", out)
                    if err:
                        print("STDERR:", err)
                except Exception as e:
                    print(f"Error running {os.path.basename(script)}: {e}")

    threading.Thread(target=run_all_scripts).start()
    return "Task started in background! Check logs folder for output.", 200

@app.route('/save-chat', methods=['POST'])
def save_chat():
    data = request.get_json()
    text = data.get('text', '').strip()
    if text:
        # Get current time in US Eastern Time and format as "h:mm AM/PM"
        eastern = pytz.timezone('America/New_York')
        now = datetime.now(eastern)
        ts = now.strftime('%I:%M %p').lstrip('0')  # e.g., "3:45 PM"
        msg_obj = {'text': text, 'timestamp': ts}
        with open('chatlog.txt', 'a', encoding='utf-8') as f:
            f.write(json.dumps(msg_obj) + '\n')
        return jsonify({'status': 'ok'}), 200
    return jsonify({'status': 'error', 'message': 'No text'}), 400

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
