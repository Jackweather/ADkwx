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
from queue import Queue, Empty
import sys
import signal
from collections import deque

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

# Scheduler globals for timesliced execution
SCHEDULER_THREAD = None
SCHEDULER_LOCK = threading.Lock()
TIMESLICE_SECONDS = 30  # run each process for 30s before switching
# keep a flag so repeated /run-task1 calls don't start multiple schedulers
SCHEDULER_RUNNING = False

# Worker count and scripts list (GIF last)
WORKER_COUNT = 2
SCRIPTS_RAW = [
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
    ("/opt/render/project/src/Gifs/gif.py", "/opt/render/project/src/Gifs"),  # GIF last
]


def _start_process_entry(entry):
    idx, script, cwd, total = entry
    try:
        # start process; preexec_fn to create new session so signals can be sent to process group if needed
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid  # Unix only; safe on POSIX
        )
        print(f"[SCHED] Started PID {proc.pid} for {os.path.basename(script)} ({idx}/{total})")
        return {'proc': proc, 'idx': idx, 'script': script, 'cwd': cwd, 'total': total}
    except Exception:
        print(f"[SCHED] Failed to start {script}:\n{traceback.format_exc()}")
        return None


def _safe_signal(proc, sig):
    try:
        if proc and proc.poll() is None and proc.pid:
            os.kill(proc.pid, sig)
    except Exception:
        # ignore platform or process gone errors
        pass


def _collect_finished(active_list):
    """Check active_list for finished processes, collect outputs, remove finished entries."""
    still_active = []
    for entry in active_list:
        proc = entry['proc']
        if proc.poll() is None:
            still_active.append(entry)
        else:
            # process finished: collect output
            try:
                out, err = proc.communicate(timeout=2)
            except Exception:
                out, err = ("", "")
            rc = proc.returncode
            print(f"[SCHED][{entry['idx']}/{entry['total']}] {os.path.basename(entry['script'])} finished (rc={rc})")
            if out:
                print(f"[SCHED][{entry['idx']}/{entry['total']}] STDOUT: {out}")
            if err:
                print(f"[SCHED][{entry['idx']}/{entry['total']}] STDERR: {err}")
    return still_active


def _timeslice_scheduler(tasks):
    """Main scheduler: start up to WORKER_COUNT processes and rotate execution every TIMESLICE_SECONDS."""
    global SCHEDULER_RUNNING, SCHEDULER_THREAD
    with SCHEDULER_LOCK:
        if SCHEDULER_RUNNING:
            print("[SCHED] Scheduler already running; ignoring new request")
            return
        SCHEDULER_RUNNING = True

    pending = deque(tasks)
    active = []
    current_idx = 0  # index in active that is currently running

    # start initial processes up to WORKER_COUNT
    while len(active) < WORKER_COUNT and pending:
        entry = pending.popleft()
        started = _start_process_entry(entry)
        if started:
            active.append(started)
    # ensure only first active is running
    for i, e in enumerate(active):
        if i == 0:
            _safe_signal(e['proc'], signal.SIGCONT)
        else:
            _safe_signal(e['proc'], signal.SIGSTOP)

    try:
        while active or pending:
            # sleep for a timeslice while the current process runs
            time.sleep(TIMESLICE_SECONDS)

            # collect any finished processes
            active = _collect_finished(active)

            # fill empty slots
            while len(active) < WORKER_COUNT and pending:
                entry = pending.popleft()
                started = _start_process_entry(entry)
                if started:
                    # new started process should be paused by default (we'll rotate it in)
                    _safe_signal(started['proc'], signal.SIGSTOP)
                    active.append(started)

            if not active:
                # nothing active right now; loop will start new ones if pending exists
                while len(active) < WORKER_COUNT and pending:
                    entry = pending.popleft()
                    started = _start_process_entry(entry)
                    if started:
                        active.append(started)
                # ensure only first is resumed
                for i, e in enumerate(active):
                    if i == 0:
                        _safe_signal(e['proc'], signal.SIGCONT)
                    else:
                        _safe_signal(e['proc'], signal.SIGSTOP)
                current_idx = 0
                continue

            # rotate if more than one active; otherwise keep running the single active
            if len(active) > 1:
                prev = current_idx % len(active)
                next_idx = (current_idx + 1) % len(active)
                # pause previous and resume next
                _safe_signal(active[prev]['proc'], signal.SIGSTOP)
                _safe_signal(active[next_idx]['proc'], signal.SIGCONT)
                current_idx = next_idx
            else:
                # only one active; ensure it's running
                _safe_signal(active[0]['proc'], signal.SIGCONT)

            # small loop to immediately collect any that finished while we were switching
            active = _collect_finished(active)

    finally:
        # ensure we clean up and print any remaining outputs
        for e in active:
            p = e['proc']
            try:
                # resume so it can finish if paused
                _safe_signal(p, signal.SIGCONT)
                out, err = p.communicate(timeout=5)
            except Exception:
                try:
                    out, err = p.communicate(timeout=1)
                except Exception:
                    out, err = ("", "")
            rc = p.returncode
            print(f"[SCHED][FINAL][{e['idx']}/{e['total']}] {os.path.basename(e['script'])} rc={rc}")
            if out:
                print(f"[SCHED][FINAL][{e['idx']}/{e['total']}] STDOUT: {out}")
            if err:
                print(f"[SCHED][FINAL][{e['idx']}/{e['total']}] STDERR: {err}")
        with SCHEDULER_LOCK:
            SCHEDULER_RUNNING = False
            SCHEDULER_THREAD = None
        print("[SCHED] All tasks complete; scheduler exiting.")


@app.route("/run-task1")
def run_task1():
    """Start the timesliced scheduler for SCRIPTS_RAW. Safe to call repeatedly; only one scheduler runs at a time."""
    global SCHEDULER_THREAD
    print("Request to run run-task1 received by", getpass.getuser())
    with SCHEDULER_LOCK:
        if SCHEDULER_RUNNING:
            return jsonify({'status': 'scheduler_already_running'}), 200
        # prepare tasks with indices
        scripts = [(i, s, c, len(SCRIPTS_RAW)) for i, (s, c) in enumerate(SCRIPTS_RAW, start=1)]
        # start scheduler thread
        SCHEDULER_THREAD = threading.Thread(target=_timeslice_scheduler, args=(scripts,), daemon=True)
        SCHEDULER_THREAD.start()
        return jsonify({'status': 'scheduler_started', 'tasks': len(scripts), 'timeslice_seconds': TIMESLICE_SECONDS}), 200

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
    # Call the map generator
