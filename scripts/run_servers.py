#!/usr/bin/env python3
"""Start MCP servers (WTA, Weather) in separate processes.

WTA server includes geocode tool (Google Maps API). No separate geocode server needed.

Usage:
    python3 scripts/run_servers.py          # Start all, logs to stdout (Ctrl+C to stop)
    python3 scripts/run_servers.py --background   # Start in background, logs to servers.log

Or run each in its own terminal for isolated logs:
    Terminal 1: python3 -m beta_graph.servers.wta.server --http
    Terminal 2: python3 -m beta_graph.servers.weather.server --http

Ports: WTA=8001, Weather=8003 (override via WTA_MCP_PORT, etc.)
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

SERVERS = [
    ("wta", "beta_graph.servers.wta.server", 8001, "WTA_MCP_PORT"),
    ("weather", "beta_graph.servers.weather.server", 8003, "WEATHER_MCP_PORT"),
]


def main():
    parser = argparse.ArgumentParser(description="Start MCP servers")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run in background, log to servers.log",
    )
    args = parser.parse_args()

    procs = []
    log_file = open("servers.log", "w") if args.background else None

    def cleanup(signum=None, frame=None):
        for p in procs:
            p.terminate()
        if log_file:
            log_file.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    for name, module, default_port, env_var in SERVERS:
        port = int(os.getenv(env_var, str(default_port)))
        cmd = ["python3", "-m", module, "--http"]
        env = os.environ.copy()
        env[env_var] = str(port)
        kwargs = {"env": env, "cwd": Path(__file__).resolve().parent.parent}
        if args.background:
            kwargs["stdout"] = log_file
            kwargs["stderr"] = subprocess.STDOUT
        else:
            kwargs["stdout"] = sys.stdout
            kwargs["stderr"] = sys.stderr
        p = subprocess.Popen(cmd, **kwargs)
        procs.append(p)
        dest = "servers.log" if args.background else "terminal"
        print(f"Started {name} on port {port} (logs -> {dest})", file=sys.stderr)

    if args.background:
        print("\nServers running in background. Logs: tail -f servers.log", file=sys.stderr)
        print("Stop: pkill -f 'beta_graph.servers.*server --http'\n", file=sys.stderr)
        return 0

    print("\nServers running. Press Ctrl+C to stop all.\n", file=sys.stderr)
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    cleanup()


if __name__ == "__main__":
    sys.exit(main() or 0)
