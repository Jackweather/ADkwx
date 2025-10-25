import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Run mslp_prate.py with specified working directory.")
    parser.add_argument(
        "--script",
        default="/opt/render/project/src/gfsmodel/mslp_prate.py",
        help="Path to the script to run (default: /opt/render/project/src/gfsmodel/mslp_prate.py)"
    )
    parser.add_argument(
        "--cwd",
        default="/opt/render/project/src/gfsmodel",
        help="Working directory to run the script in (default: /opt/render/project/src/gfsmodel)"
    )
    args = parser.parse_args()

    script_path = args.script
    work_dir = args.cwd

    if not os.path.isfile(script_path):
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(work_dir):
        print(f"Error: working directory not found: {work_dir}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, script_path]

    try:
        proc = subprocess.run(cmd, cwd=work_dir, env=os.environ.copy())
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        print("Execution interrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Failed to run script: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
