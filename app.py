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

# Suppress 404 logging for image directories
logging.getLogger('werkzeug').addFilter(
    lambda record: not (
        (('GET /PRATEGFS/' in record.getMessage() or 'GET /tmp_surface/' in record.getMessage()) and '404' in record.getMessage())
    )
)

BASE_DATA_DIR = '/var/data'

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
    'northeast_tmp_pngs': ['GFS', 'static', 'northeast_tmp_pngs'],
    'northeast_precip_pngs': ['GFS', 'static', 'northeast_precip_pngs'],
    'northeast_12hour_precip_pngs': ['GFS', 'static', 'northeast_12hour_precip_pngs'],
    'northeast_24hour_precip_pngs': ['GFS', 'static', 'northeast_24hour_precip_pngs'],
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
        print(f"[DEBUG] Trying to serve: {abs_path}")
        if not os.path.isfile(abs_path):
            print(f"[DEBUG] File not found: {abs_path}")
            abort(404, description=f"File not found: {abs_path}")
        return send_from_directory(directory, filename)
    print(f"[DEBUG] No mapping for prefix: {prefix}")
    abort(404, description=f"No mapping for prefix: {prefix}")

# --- Scheduler Section ---
SCHEDULER_THREAD = None
SCHEDULER_LOCK = threading.Lock()
TIMESLICE_SECONDS = 30
SCHEDULER_RUNNING = False
WORKER_COUNT = 2
MAX_PROCESS_RUNTIME = 600  # 10 minutes safety limit

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
    ("/opt/render/project/src/Gifs/gif.py", "/opt/render/project/src/Gifs"),
]

def _safe_signal(proc, sig):
    try:
        if proc and proc.poll() is None and proc.pid:
            os.kill(proc.pid, sig)
    except Exception:
        pass

def _collect_finished(active_list):
    """Collect finished processes and kill stuck ones."""
    still_active = []
    now = time.time()
    for entry in active_list:
        proc = entry['proc']
        start_time = entry.setdefault('start_time', now)
        if proc.poll() is None:
            if now - start_time > MAX_PROCESS_RUNTIME:
                print(f"[SCHED] Killing stuck PID {proc.pid}")
                _safe_signal(proc, signal.SIGKILL)
            else:
                still_active.append(entry)
        else:
            try:
                out, err = proc.communicate(timeout=2)
            except Exception:
                out, err = ("", "")
            rc = proc.returncode
            print(f"[SCHED][{entry['idx']}/{entry['total']}] {os.path.basename(entry['script'])} finished (rc={rc})")
            if out:
                print(out)
            if err:
                print(err)
    return still_active

def _start_process_entry(entry):
    idx, script, cwd, total = entry
    try:
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        print(f"[SCHED] Started PID {proc.pid} for {os.path.basename(script)} ({idx}/{total})")
        return {'proc': proc, 'idx': idx, 'script': script, 'cwd': cwd, 'total': total}
    except Exception:
        print(f"[SCHED] Failed to start {script}:\n{traceback.format_exc()}")
        return None

def _timeslice_scheduler(tasks):
    global SCHEDULER_RUNNING, SCHEDULER_THREAD
    try:
        print("[SCHED] Scheduler started with", len(tasks), "tasks")
        pending = deque(tasks)
        active = []
        current_idx = 0

        while len(active) < WORKER_COUNT and pending:
            entry = pending.popleft()
            started = _start_process_entry(entry)
            if started:
                active.append(started)

        for i, e in enumerate(active):
            if i == 0:
                _safe_signal(e['proc'], signal.SIGCONT)
            else:
                _safe_signal(e['proc'], signal.SIGSTOP)

        while active or pending:
            time.sleep(TIMESLICE_SECONDS)
            active = _collect_finished(active)

            while len(active) < WORKER_COUNT and pending:
                entry = pending.popleft()
                started = _start_process_entry(entry)
                if started:
                    _safe_signal(started['proc'], signal.SIGSTOP)
                    active.append(started)

            if not active:
                continue

            if len(active) > 1:
                prev = current_idx % len(active)
                next_idx = (current_idx + 1) % len(active)
                _safe_signal(active[prev]['proc'], signal.SIGSTOP)
                _safe_signal(active[next_idx]['proc'], signal.SIGCONT)
                current_idx = next_idx
            else:
                _safe_signal(active[0]['proc'], signal.SIGCONT)

            active = _collect_finished(active)

        print("[SCHED] All tasks finished; exiting scheduler.")

    except Exception as e:
        print("[SCHED] CRASHED:", e)
        traceback.print_exc()
    finally:
        with SCHEDULER_LOCK:
            SCHEDULER_RUNNING = False
            SCHEDULER_THREAD = None
        print("[SCHED] Scheduler reset complete.")

@app.route("/run-task1")
def run_task1():
    global SCHEDULER_THREAD, SCHEDULER_RUNNING
    print("RUN-TASK1 triggered by", getpass.getuser())
    with SCHEDULER_LOCK:
        print("SCHEDULER_RUNNING =", SCHEDULER_RUNNING)
        if SCHEDULER_RUNNING:
            return jsonify({'status': 'scheduler_already_running'}), 200
        SCHEDULER_RUNNING = True
        scripts = [(i, s, c, len(SCRIPTS_RAW)) for i, (s, c) in enumerate(SCRIPTS_RAW, start=1)]
        SCHEDULER_THREAD = threading.Thread(target=_timeslice_scheduler, args=(scripts,))
        SCHEDULER_THREAD.start()
        return jsonify({'status': 'scheduler_started', 'tasks': len(scripts), 'timeslice_seconds': TIMESLICE_SECONDS}), 200

# --- Extra routes ---
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
                    messages.append({'text': line, 'timestamp': ''})
    return jsonify({'messages': messages})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
