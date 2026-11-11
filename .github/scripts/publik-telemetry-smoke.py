#!/usr/bin/env python3
"""Tests of the publik module (Sign in with publik + usage counts) in the BUILT app. Standard library only.

    python3 publik-telemetry-smoke.py <app executable> <app version> <slug> [--out=result.json]
    python3 publik-telemetry-smoke.py <app executable> <app version> <slug> --self-test [--out=result.json]

publik itself is a fake publik on 127.0.0.1 (a free port), given to the app with PUBLIK_ORIGIN. It answers
POST /api/v1/installs, GET /api/v1/wallet (the install is signed in) and POST /api/v1/telemetry. The test never
talks to publikhq.com. The app runs with a temporary home folder, so no real publik file is read or written.

--self-test: starts the app once with PUBLIK_SELF_TEST=1 and no PUBLIK_APP_TOKEN in the environment. The app must
       print "publik self-test: ok <slug> <version>" and exit 0 by itself, after POST /installs with the app
       token that the build baked in (the test says only "baked"; it never prints a token) and GET /wallet.
default: Run 1 starts the app with a fixture app token and waits up to 30 seconds for ONE correct "app_opened"
       request with the install key: the gate passed and usage counting started. Run 2 starts the app again with
       DO_NOT_TRACK=1: the gate still runs, and NO usage-count request may arrive.
It stops only the processes that it started. Exit code 0 = every run passed.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED = {"v", "app", "install_id", "event", "app_version", "os", "arch"}
UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
WANT_OS = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(platform.system(), "?")
KEY = "pk_self_test_fixture"
FIXTURE_TOKEN = "pat_self_test_fixture"


def fake_publik(slug):
    """A fake publik. Each request is kept as method, path, whether it carried the key, and its body (telemetry only).
    For /installs it keeps only which app token came: "fixture", "baked" (another pat_ token) or "missing"."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _json(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _record(self, body=""):
            entry = {"method": self.command, "path": self.path, "with_key": self.headers.get("Authorization") == "Bearer " + KEY,
                     "headers": {k.lower(): v for k, v in self.headers.items() if k.lower() != "authorization"}}
            requests.append(entry)
            return entry

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
            entry = self._record()
            origin = "http://127.0.0.1:%d" % self.server.server_address[1]
            if self.path == "/api/v1/installs":
                try:
                    sent = json.loads(body)
                except ValueError:
                    sent = {}
                token = str(sent.get("app_token", ""))
                entry["token"] = "fixture" if token == FIXTURE_TOKEN else "baked" if token.startswith("pat_") else "missing"
                entry["app_slug"] = sent.get("app_slug")
                if entry["token"] == "missing" or sent.get("app_slug") != slug:
                    return self._json(401, {"error": {"type": "invalid_app_token", "message": "This app token is not valid."}})
                return self._json(201, {"key": KEY, "install_id": sent.get("install_id"), "claim_url": origin + "/claim/self-test",
                                        "claim_state": "anonymous", "base_url": origin + "/api/v1"})
            if self.path == "/api/v1/telemetry":
                entry["body"] = body
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            return self._json(404, {"error": {"type": "not_found", "message": "no such route"}})

        def do_GET(self):
            entry = self._record()
            origin = "http://127.0.0.1:%d" % self.server.server_address[1]
            if self.path == "/api/v1/wallet":
                if not entry["with_key"]:
                    return self._json(401, {"error": {"type": "invalid_key", "message": "This key is not valid."}})
                return self._json(200, {"claim_state": "claimed", "claim_url": origin + "/claim/self-test", "account": {"handle": "ci"},
                                        "plan": {"kind": "none", "label": None}, "balance_micros": 0,
                                        "top_up_url": origin + "/wallet", "linked_at": None})
            return self._json(404, {"error": {"type": "not_found", "message": "no such route"}})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # port 0 = a free port
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return server, requests


def app_env(origin, home, extra):
    """The runner's environment (Windows needs SystemRoot and the rest), with a temporary home and the fake publik."""
    env = dict(os.environ)
    for name in ("DO_NOT_TRACK", "PUBLIK_TELEMETRY", "PUBLIK_TELEMETRY_URL", "PUBLIK_API_KEY", "PUBLIK_API_BASE_URL",
                 "PUBLIK_APP_TOKEN", "PUBLIK_SELF_TEST"):
        env.pop(name, None)
    env.update({
        "HOME": home,
        "USERPROFILE": home,
        "XDG_CONFIG_HOME": os.path.join(home, ".config"),
        "LOCALAPPDATA": os.path.join(home, "AppData", "Local"),
        "CFFIXED_USER_HOME": home,
        "PUBLIK_ORIGIN": origin,
        "PUBLIK_TELEMETRY_DEBUG": "1",
    })
    os.makedirs(env["XDG_CONFIG_HOME"], exist_ok=True)
    os.makedirs(env["LOCALAPPDATA"], exist_ok=True)
    env.update(extra)
    return env


def check_opened(request, slug, version):
    """Returns the list of faults of one app_opened request. Empty list = the request matches the contract."""
    faults = []
    if request["method"] != "POST":
        faults.append("method is %s" % request["method"])
    if "origin" in request["headers"]:
        faults.append("the request has an Origin header (it did not come from native code)")
    if request["headers"].get("content-type", "").split(";")[0].strip() != "application/json":
        faults.append("content-type is %r" % request["headers"].get("content-type"))
    if not request["with_key"]:
        faults.append("the request did not carry the install key (Authorization: Bearer pk_...)")
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


def summary(requests):
    return [{k: v for k, v in r.items() if k in ("method", "path", "with_key", "token", "app_slug")} for r in requests]


def self_test(exe, version, slug):
    server, requests = fake_publik(slug)
    home = tempfile.mkdtemp(prefix="publik-self-test-home-")
    env = app_env("http://127.0.0.1:%d" % server.server_address[1], home, {"PUBLIK_SELF_TEST": "1", "DO_NOT_TRACK": "1"})
    started = time.time()
    try:
        proc = subprocess.run([exe], env=env, cwd=home, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        output, code = proc.stdout.decode("utf-8", "replace"), proc.returncode
    except subprocess.TimeoutExpired as e:
        output, code = (e.stdout or b"").decode("utf-8", "replace"), "timeout"
    seconds = round(time.time() - started, 1)
    time.sleep(0.3)
    server.shutdown()
    server.server_close()
    shutil.rmtree(home, ignore_errors=True)

    lines = [line.strip() for line in output.splitlines() if line.startswith("publik self-test:")]
    want = "publik self-test: ok %s %s" % (slug, version)
    paths = [(r["method"], r["path"]) for r in requests]
    faults = []
    if want not in lines:
        faults.append("want the line %r, got %r" % (want, lines))
    if code != 0:
        faults.append("the app did not exit with 0 (got %s)" % code)
    if paths != [("POST", "/api/v1/installs"), ("GET", "/api/v1/wallet")]:
        faults.append("want POST /installs then GET /wallet and nothing else, got %r" % paths)
    installs = [r for r in requests if r["path"] == "/api/v1/installs"]
    if installs and installs[0].get("token") != "baked":
        faults.append("the app sent no app token of its own (token: %s); the build did not bake PUBLIK_APP_TOKEN" % installs[0].get("token"))
    if any(r["path"] == "/api/v1/wallet" and not r["with_key"] for r in requests):
        faults.append("GET /wallet did not carry the minted key")
    result = {"mode": "self-test", "seconds": seconds, "exit_code": code, "self_test_lines": lines, "requests": summary(requests),
              "faults": faults, "pass": not faults}
    if faults:
        result["app_output_tail"] = [line for line in output.splitlines()[-40:] if "pat_" not in line]
    return result


def launch(exe, slug, extra_env, wait, stop_on_telemetry):
    server, requests = fake_publik(slug)
    home = tempfile.mkdtemp(prefix="publik-smoke-home-")
    env = app_env("http://127.0.0.1:%d" % server.server_address[1], home, dict({"PUBLIK_APP_TOKEN": FIXTURE_TOKEN}, **extra_env))
    process = subprocess.Popen([exe], env=env, cwd=home, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    started = time.time()
    while time.time() - started < wait:
        if stop_on_telemetry and any(r["path"] == "/api/v1/telemetry" for r in requests):
            break
        if process.poll() is not None:
            break
        time.sleep(0.2)
    seconds = round(time.time() - started, 1)
    if stop_on_telemetry:
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
    shutil.rmtree(home, ignore_errors=True)
    lines = [line for line in stderr.decode("utf-8", "replace").splitlines() if line.startswith(("publik-telemetry", "publik:")) and "pat_" not in line]
    return {"requests": list(requests), "seconds": seconds, "alive_at_end": alive, "exit_code_before_stop": exit_code, "app_lines": lines}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--out=")), None)
    if len(args) != 3:
        print(__doc__)
        return 2
    exe, version, slug = args
    exe = os.path.abspath(exe)  # the app runs in a temporary folder, so a relative path would not resolve
    result = {"app": slug, "version": version, "executable": exe, "system": platform.system(), "machine": platform.machine()}

    if "--self-test" in sys.argv[1:]:
        result["self_test"] = self_test(exe, version, slug)
        result["pass"] = result["self_test"]["pass"]
        for line in result["self_test"]["self_test_lines"]:
            print(line)
    else:
        first = launch(exe, slug, {}, wait=30, stop_on_telemetry=True)
        paths = [r["path"] for r in first["requests"]]
        opened = [r for r in first["requests"] if r["path"] == "/api/v1/telemetry" and '"app_opened"' in r.get("body", "")]
        faults = ["no app_opened request arrived in 30 seconds"] if not opened else check_opened(opened[0], slug, version)
        if len(opened) > 1:
            faults.append("%d app_opened requests arrived, expected 1" % len(opened))
        if opened and not ("/api/v1/wallet" in paths and paths.index("/api/v1/wallet") < paths.index("/api/v1/telemetry")):
            faults.append("app_opened came before the gate read GET /wallet: %r" % paths)
        if not first["alive_at_end"]:
            faults.append("the app was not running at the end (exit code %s)" % first["exit_code_before_stop"])
        result["app_opened"] = {"pass": not faults, "faults": faults, **dict(first, requests=summary(first["requests"]))}

        time.sleep(3)  # the first process must be gone: the app allows one instance only
        second = launch(exe, slug, {"DO_NOT_TRACK": "1"}, wait=12, stop_on_telemetry=False)
        sent = [r for r in second["requests"] if r["path"] == "/api/v1/telemetry"]
        faults = ["%d usage-count requests arrived with DO_NOT_TRACK=1" % len(sent)] if sent else []
        if not any(r["path"] == "/api/v1/wallet" for r in second["requests"]):
            faults.append("the gate did not run with DO_NOT_TRACK=1 (no GET /wallet)")
        result["opt_out"] = {"pass": not faults, "faults": faults, **dict(second, requests=summary(second["requests"]))}
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
