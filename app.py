from flask import Flask, send_from_directory, abort, request
import os
import subprocess
import traceback
import getpass
import logging

app = Flask(__name__)

# Suppress 404 logging for /PRATEGFS/ image requests in werkzeug logger
class WerkzeugFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if 'GET /PRATEGFS/' in msg and '404' in msg:
            return False
        return True

logging.getLogger('werkzeug').addFilter(WerkzeugFilter())

@app.route('/')
def index():
    with open('gfs.html', 'r', encoding='utf-8') as f:
        html = f.read()
    directory = os.path.join(os.path.dirname(__file__), 'gfsmodel', 'GFS', 'static', 'PRATEGFS')
    images_html = ''.join(
        f'<img src="/PRATEGFS/{png}" alt="{png}"><br>\n'
        for png in sorted(f for f in os.listdir(directory) if f.endswith('.png'))
    )
    return html.replace('<!--IMAGES-->', images_html)

@app.route('/PRATEGFS/<path:filename>')
def serve_prate_image(filename):
    directory = os.path.join(os.path.dirname(__file__), 'gfsmodel', 'GFS', 'static', 'PRATEGFS')
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
    run_all_scripts()
    return "Task 1 executed."

if __name__ == '__main__':
    app.run(debug=True)
