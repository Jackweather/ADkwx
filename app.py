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
import signal

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
        print(f"[DEBUG] Trying to serve: {abs_path}")
        if not os.path.isfile(abs_path):
            print(f"[DEBUG] File not found: {abs_path}")
            abort(404, description=f"File not found: {abs_path}")
        return send_from_directory(directory, filename)
    print(f"[DEBUG] No mapping for prefix: {prefix}")
    abort(404, description=f"No mapping for prefix: {prefix}")

@app.route("/run-task1")
def run_task1():
    def run_all_scripts():
        print("Flask is running as user:", getpass.getuser())
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

        # persistent run-log file and limits
        LOG_FILE = 'script_runs.json'
        MAX_ATTEMPTS = 3
        SLICE_SECONDS = 60
        COOLDOWN_SECONDS = 8

        def load_runs():
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', encoding='utf-8') as fh:
                        return json.load(fh)
                except Exception:
                    return {}
            return {}

        def save_runs(runs):
            try:
                with open(LOG_FILE, 'w', encoding='utf-8') as fh:
                    json.dump(runs, fh)
            except Exception as e:
                print(f"[ERROR] saving runs log: {e}")

        runs = load_runs()

        # Build pending list: skip scripts already completed
        pending = []
        for script, cwd in scripts:
            info = runs.get(script, {})
            if info.get('completed'):
                print(f"[SKIP] already completed: {script}")
                continue
            attempts = info.get('attempts', 0)
            if attempts >= MAX_ATTEMPTS:
                print(f"[ABORT] script {script} already reached max attempts ({attempts}). Not starting run.")
                return  # do not start if any script already exhausted attempts
            pending.append((script, cwd))

        abort_all = False

        def run_batch(batch):
            nonlocal abort_all, runs
            # start processes and pause them immediately
            procs = []
            next_allowed = []
            for script, cwd in batch:
                name = os.path.basename(script)
                info = runs.get(script, {})
                attempts = info.get('attempts', 0)
                if attempts >= MAX_ATTEMPTS:
                    print(f"[ABORT-DET] {script} already at max attempts ({attempts}) - aborting batch")
                    abort_all = True
                    break
                try:
                    p = subprocess.Popen(["python", script], cwd=cwd)
                    procs.append({'proc': p, 'name': name, 'script': script})
                    try:
                        os.kill(p.pid, signal.SIGSTOP)
                    except Exception:
                        pass
                    next_allowed.append(time.time())  # allow immediate resume on first round
                    print(f"[STARTED & PAUSED] {name} (pid={p.pid})")
                except Exception as e:
                    print(f"[ERROR] Could not start {script}: {e}")
                    # treat as failed attempt
                    info = runs.setdefault(script, {})
                    info['attempts'] = info.get('attempts', 0) + 1
                    info['last_attempt'] = time.time()
                    save_runs(runs)
                    if info['attempts'] >= MAX_ATTEMPTS:
                        abort_all = True

            if abort_all:
                # kill any started procs
                for pinfo in procs:
                    try:
                        pinfo['proc'].terminate()
                    except Exception:
                        pass
                return [], []  # no requeue

            # Round-robin with slices until all in this batch finish
            unfinished = {i for i in range(len(procs))}
            requeue = []  # scripts that failed but still have attempts left
            while unfinished and not abort_all:
                progressed = False
                for i in list(unfinished):
                    if time.time() < next_allowed[i]:
                        continue
                    pinfo = procs[i]
                    p = pinfo['proc']
                    name = pinfo['name']
                    script = pinfo['script']
                    if p.poll() is not None:
                        rc = p.returncode
                        if rc == 0:
                            print(f"[FINISHED] {name} (rc={rc})")
                            runs.setdefault(script, {})['completed'] = True
                            runs.setdefault(script, {})['attempts'] = runs.get(script, {}).get('attempts', 0)
                            save_runs(runs)
                        else:
                            # failed attempt
                            info = runs.setdefault(script, {})
                            info['attempts'] = info.get('attempts', 0) + 1
                            info['last_attempt'] = time.time()
                            save_runs(runs)
                            print(f"[FAILED] {name} (rc={rc}) attempts={info['attempts']}")
                            if info['attempts'] >= MAX_ATTEMPTS:
                                print(f"[ABORT-CONDITION] {script} reached max attempts -> aborting all")
                                abort_all = True
                            else:
                                requeue.append((script, cwd))
                        unfinished.discard(i)
                        continue

                    # resume process
                    try:
                        os.kill(p.pid, signal.SIGCONT)
                        print(f"[RESUME] {name} (pid={p.pid}) for {SLICE_SECONDS}s")
                        progressed = True
                    except Exception as e:
                        print(f"[ERROR] Could not resume {name}: {e}")
                        if p.poll() is not None:
                            unfinished.discard(i)
                        continue

                    start = time.time()
                    while time.time() - start < SLICE_SECONDS:
                        if p.poll() is not None:
                            rc = p.returncode
                            print(f"[FINISHED DURING SLICE] {name} (rc={rc})")
                            break
                        time.sleep(1)

                    if p.poll() is None:
                        try:
                            os.kill(p.pid, signal.SIGSTOP)
                            next_allowed[i] = time.time() + COOLDOWN_SECONDS
                            print(f"[PAUSED] {name} (pid={p.pid}) after {SLICE_SECONDS}s; next resume after {next_allowed[i]:.1f}")
                        except Exception as e:
                            print(f"[ERROR] Could not pause {name}: {e}")
                    else:
                        # process finished during slice; will be processed in next iteration
                        pass

                if not progressed:
                    time.sleep(0.5)

            # finalize batch: gather requeue list (only those with attempts < MAX_ATTEMPTS)
            final_requeue = []
            for pinfo in procs:
                p = pinfo['proc']
                script = pinfo['script']
                name = pinfo['name']
                # ensure waited
                try:
                    p.wait(timeout=1)
                except Exception:
                    pass
                rc = p.returncode
                if rc is None:
                    # if still running and we're aborting, try to terminate
                    if abort_all:
                        try:
                            p.terminate()
                            time.sleep(0.5)
                            if p.poll() is None:
                                p.kill()
                        except Exception:
                            pass
                    else:
                        # should not happen, but wait
                        try:
                            p.wait()
                        except Exception:
                            pass
                        rc = p.returncode
                if rc != 0 and not runs.get(script, {}).get('completed'):
                    attempts = runs.get(script, {}).get('attempts', 0)
                    if attempts < MAX_ATTEMPTS:
                        final_requeue.append((script, cwd))
            return final_requeue, procs

        # Process scripts in batches of 3
        batch_size = 10
        while pending and not abort_all:
            batch = pending[:batch_size]
            pending = pending[batch_size:]
            print(f"[BATCH START] processing {len(batch)} scripts")
            requeue, procs = run_batch(batch)
            if abort_all:
                print("[ABORT] aborting run_all_scripts due to failure threshold")
                # ensure all procs killed
                for pinfo in (procs or []):
                    try:
                        p = pinfo['proc']
                        if p.poll() is None:
                            p.terminate()
                            time.sleep(0.5)
                            if p.poll() is None:
                                p.kill()
                    except Exception:
                        pass
                break
            # append requeue scripts to pending end (retry later)
            if requeue:
                pending.extend(requeue)
            print(f"[BATCH DONE] batch complete; pending remaining: {len(pending)}")

        if abort_all:
            print("[RUN ABORTED] One or more scripts exceeded max retries. Exiting run_all_scripts.")
        else:
            print("[RUN COMPLETE] All scripts processed.")

    threading.Thread(target=run_all_scripts, daemon=True).start()
    return "All scripts started in batched round-robin with retry and abort-on-failure logic. Check logs.", 200

@app.route('/save-chat', methods=['POST'])
def save_chat():
    data = request.get_json()
    text = data.get('text', '').strip()
    if text:
        eastern = pytz.timezone('America/New_York')
        now = datetime.now(eastern)
        ts = now.strftime('%I:%M %p').lstrip('0')
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
                    messages.append({'text': line, 'timestamp': ''})
    return jsonify({'messages': messages})

if __name__ == '__main__':
    app.run(debug=True)

