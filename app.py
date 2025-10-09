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
    'northeast_24hour_precip_pngs': ['GFS', 'static', 'northeast_24hour_precip_pngs'],
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
            ("/opt/render/project/src/Gifs/gif.py", "/opt/render/project/src/Gifs"),
        ]
        for script, cwd in scripts:
            try:
                result = subprocess.run(
                    ["python", script],
                    check=True, cwd=cwd,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                print(f"{os.path.basename(script)} ran successfully!")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
            except subprocess.CalledProcessError as e:
                error_trace = traceback.format_exc()
                print(f"Error running {os.path.basename(script)}:\n{error_trace}")
                print("STDOUT:", e.stdout)
                print("STDERR:", e.stderr)
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

if __name__ == '__main__':
    app.run(debug=True)
