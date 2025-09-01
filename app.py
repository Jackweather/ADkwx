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

@app.route('/')
def index():
    with open('gfs.html', 'r', encoding='utf-8') as f:
        html = f.read()
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'PRATEGFS')
    images_html = ''.join(
        f'<img src="/PRATEGFS/{png}" alt="{png}"><br>\n'
        for png in sorted(f for f in os.listdir(directory) if f.endswith('.png'))
    )
    return html.replace('<!--IMAGES-->', images_html)

@app.route('/PRATEGFS/<path:filename>')
def serve_prate_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'PRATEGFS')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/tmp_surface/<path:filename>')
def serve_tmp_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'tmp_surface')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/6hour_precip_total/<path:filename>')
def serve_precip6_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', '6hour_precip_total')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/24hour_precip_total/<path:filename>')
def serve_precip24_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', '24hour_precip_total')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/12hour_precip_total/<path:filename>')
def serve_precip12_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', '12hour_precip_total')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)


@app.route('/total_precip/<path:filename>')
def serve_total_precip_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'total_precip')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)
    

@app.route('/total_lcdc/<path:filename>')
def serve_total_lcdc_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'total_lcdc')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/snow_depth/<path:filename>')
def serve_snow_depth_png(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'snow_depth')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/totalsnowfall_10to1/<path:filename>')
def serve_totalsnowfall_10to1_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'totalsnowfall_10to1')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/totalsnowfall_3to1/<path:filename>')
def serve_totalsnowfall_3to1_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'totalsnowfall_3to1')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/totalsnowfall_5to1/<path:filename>')
def serve_totalsnowfall_5to1_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'totalsnowfall_5to1')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/totalsnowfall_20to1/<path:filename>')
def serve_totalsnowfall_20to1_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'totalsnowfall_20to1')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/totalsnowfall_8to1/<path:filename>')
def serve_totalsnowfall_8to1_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'totalsnowfall_8to1')
    abs_path = os.path.join(directory, filename)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(directory, filename)

@app.route('/GFS/static/totalsnowfall_12to1/<path:filename>')
def serve_totalsnowfall_12to1_image(filename):
    directory = os.path.join(BASE_DATA_DIR, 'GFS', 'static', 'totalsnowfall_12to1')
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
