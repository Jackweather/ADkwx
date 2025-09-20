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
    # Handle nested prefixes for snow_depth, totalsnowfall, etc.
    full_prefix = prefix
    # Try to match the longest possible prefix in the mapping
    for key in sorted(IMAGE_ROUTE_MAP.keys(), key=lambda x: -len(x)):
        if prefix.startswith(key):
            full_prefix = key
            break
    if full_prefix in IMAGE_ROUTE_MAP:
        directory = os.path.join(BASE_DATA_DIR, *IMAGE_ROUTE_MAP[full_prefix])
        # If the prefix is nested (e.g., GFS/static/snow_depth), remove the matched part from filename
        if full_prefix != prefix:
            # Remove the matched prefix from filename
            subpath = prefix[len(full_prefix):].lstrip('/')
            filename = os.path.join(subpath, filename) if subpath else filename
        abs_path = os.path.join(directory, filename)
        if not os.path.isfile(abs_path):
            abort(404)
        return send_from_directory(directory, filename)
    abort(404)

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
        # --- Run gfsmodel/mslp_prate.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/mslp_prate.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("mslp_prate.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running mslp_prate.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/tmp_surface_clean.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/tmp_surface_clean.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("tmp_surface_clean.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running tmp_surface_clean.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/6hourmaxprecip.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/6hourmaxprecip.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("6hourmaxprecip.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running 6hourmaxprecip.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/12hour_precip.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/12hour_precip.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("12hour_precip.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running 12hour_precip.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/24hour_precip.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/24hour_precip.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("24hour_precip.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running 24hour_precip.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/total_precip.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/total_precip.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("total_precip.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running total_precip.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/total_cloud_cover.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/total_cloud_cover.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("total_cloud_cover.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running total_cloud_cover.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/snow_depth.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/snowdepth.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("snowdepth.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running snowdepth.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            
        # --- Run gfsmodel/totalsnowfall_3to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_3to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_3to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_3to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)

        # --- Run gfsmodel/totalsnowfall_5to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_5to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_5to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_5to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)

        # --- Run gfsmodel/totalsnowfall_20to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_20to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_20to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_20to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)

        # --- Run gfsmodel/totalsnowfall_8to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_8to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_8to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_8to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)

        # --- Run gfsmodel/totalsnowfall_12to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_12to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_12to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_12to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)

        # --- Run gfsmodel/totalsnowfall_15to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_15to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_15to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_15to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)

        # --- Run gfsmodel/totalsnowfall_10to1.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/totalsnowfall_10to1.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("totalsnowfall_10to1.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running totalsnowfall_10to1.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/thickness_1000_500.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/thickness_1000_500.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("thickness_1000_500.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running thickness_1000_500.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/wind_200.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/wind_200.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("wind_200.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running wind_200.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/sunsd_surface_clean.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/sunsd_surface_clean.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("sunsd_surface_clean.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running sunsd_surface_clean.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run gfsmodel/gfs_850mb_plot.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/gfsmodel/gfs_850mb_plot.py"],
                check=True, cwd="/opt/render/project/src/gfsmodel",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("gfs_850mb_plot.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running gfs_850mb_plot.py:\n{error_trace}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
        # --- Run Gifs/gif.py ---
        try:
            result = subprocess.run(
                ["python", "/opt/render/project/src/Gifs/gif.py"],
                check=True, cwd="/opt/render/project/src/Gifs",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            print("gif.py ran successfully!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            error_trace = traceback.format_exc()
            print(f"Error running gif.py:\n{error_trace}")
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
