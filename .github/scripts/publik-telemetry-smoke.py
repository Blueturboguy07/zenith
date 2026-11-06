#!/usr/bin/env python3
"""Launch test for the publik usage counts (telemetry v1). Standard library only.

    python3 publik-telemetry-smoke.py <app executable> <app version> <slug> [--out result.json]

Run 1: starts the app with PUBLIK_TELEMETRY_URL set to a listener on 127.0.0.1 (a free port) and waits
       up to 20 seconds for ONE correct "app_opened" request.
Run 2: starts the app again with DO_NOT_TRACK=1 and makes sure that NO request arrives.
The test never talks to publikhq.com. It stops only the process that it started.
Exit code 0 = both runs passed.
"""
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED = {"v", "app", "install_id", "event", "app_version", "os", "arch"}
UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
WANT_OS = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(platform.system(), "?")


def listener():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def _handle(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
            requests.append({"method": self.command, "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_POST = do_GET = do_PUT = do_OPTIONS = _handle

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # port 0 = a free port
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return server, requests


def check(request, slug, version):
    """Returns the list of faults of one request. Empty list = the request matches the contract."""
    faults = []
    if request["method"] != "POST":
        faults.append("method is %s" % request["method"])
    if request["path"] != "/api/v1/telemetry":
        faults.append("path is %s" % request["path"])
    if "origin" in request["headers"]:
        faults.append("the request has an Origin header (it did not come from native code)")
    if request["headers"].get("content-type", "").split(";")[0].strip() != "application/json":
        faults.append("content-type is %r" % request["headers"].get("content-type"))
    try:
        body = json.loads(request["body"])
    except ValueError:
        return faults + ["the body is not JSON"]
    extra = sorted(set(body) - ALLOWED)
    if extra:
        faults.append("fields that the contract does not have: %s" % extra)
    if body.get("v") != 1:
        faults.append("v is %r" % body.get("v"))
    if body.get("app") != slug:
        faults.append("app is %r, expected %r" % (body.get("app"), slug))
    if body.get("event") != "app_opened":
        faults.append("event is %r" % body.get("event"))
    if body.get("app_version") != version:
        faults.append("app_version is %r, expected %r" % (body.get("app_version"), version))
    if body.get("os") != WANT_OS:
        faults.append("os is %r, expected %r" % (body.get("os"), WANT_OS))
    if "arch" in body and body["arch"] not in ("arm64", "x64"):
        faults.append("arch is %r" % body["arch"])
    if not UUID4.match(str(body.get("install_id", ""))):
        faults.append("install_id is not a lowercase UUID v4")
    return faults


def launch(exe, url, extra_env, wait, stop_on_first):
    server, requests = listener()
    env = dict(os.environ)
    env.pop("DO_NOT_TRACK", None)
    env.pop("PUBLIK_TELEMETRY", None)
    env.update({"PUBLIK_TELEMETRY_URL": url % server.server_address[1], "PUBLIK_TELEMETRY_DEBUG": "1"})
    env.update(extra_env)
    process = subprocess.Popen([exe], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    started = time.time()
    while time.time() - started < wait:
        if stop_on_first and requests:
            break
        time.sleep(0.2)
    seconds = round(time.time() - started, 1)
    if stop_on_first:
        time.sleep(2)  # the app must still run a moment after its first send
    alive = process.poll() is None
    exit_code = process.returncode
    process.terminate()  # only the process that this test started
    try:
        _, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        _, stderr = process.communicate()
    server.shutdown()
    server.server_close()
    lines = [line for line in stderr.decode("utf-8", "replace").splitlines() if "publik-telemetry" in line]
    return {"requests": list(requests), "seconds": seconds, "alive_at_end": alive, "exit_code_before_stop": exit_code, "debug_lines": lines}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--out")]
    out = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--out=")), None)
    if len(args) != 3:
        print(__doc__)
        return 2
    exe, version, slug = args
    url = "http://127.0.0.1:%d/api/v1/telemetry"
    result = {"app": slug, "version": version, "executable": exe, "system": platform.system(), "machine": platform.machine()}

    first = launch(exe, url, {}, wait=20, stop_on_first=True)
    opened = [r for r in first["requests"] if '"app_opened"' in r["body"]]
    faults = ["no app_opened request arrived in 20 seconds"] if not opened else check(opened[0], slug, version)
    if len(opened) > 1:
        faults.append("%d app_opened requests arrived, expected 1" % len(opened))
    result["app_opened"] = {"pass": not faults, "faults": faults, **first}

    time.sleep(3)  # the first process must be gone: the app allows one instance only
    second = launch(exe, url, {"DO_NOT_TRACK": "1"}, wait=8, stop_on_first=False)
    result["opt_out"] = {"pass": not second["requests"], "faults": ["%d requests arrived with DO_NOT_TRACK=1" % len(second["requests"])] if second["requests"] else [], **second}

    result["pass"] = result["app_opened"]["pass"] and result["opt_out"]["pass"]
    text = json.dumps(result, indent=2)
    print(text)
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print("RESULT: %s" % ("PASS" if result["pass"] else "FAIL"))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
