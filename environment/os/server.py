#!/usr/bin/env python3
"""Deterministic desktop service and versioned OS-ICL authoring API."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import tasks36
import workflows

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
EPISODES = DATA / "episodes"
VIDEOS = DATA / "videos"
RENDER_TEMP = DATA / "render-temp"
for directory in (EPISODES, VIDEOS, RENDER_TEMP):
    directory.mkdir(parents=True, exist_ok=True)

SESSIONS: dict[str, dict] = {}
LOCK = threading.RLock()
RENDER_JOBS = {}
PUBLIC_BASE_URL = os.environ.get("OS_ICL_PUBLIC_URL", os.environ.get("VIBE_PUBLIC_URL", "http://127.0.0.1:8790"))
RENDER_CONCURRENCY = max(1, int(os.environ.get("OS_ICL_RENDER_CONCURRENCY", os.environ.get("VIBE_RENDER_CONCURRENCY", "3"))))
RENDER_SLOTS = threading.Semaphore(RENDER_CONCURRENCY)


def now_ms() -> int:
    return int(time.time() * 1000)


def state_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def persist(session: dict) -> None:
    path = EPISODES / f"{session['id']}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def schedule_video_render(session_id: str, generation: int) -> None:
    """Render a successful semantic trajectory in an isolated browser.

    The worker visits the replay-only page, which contains neither the recorder
    brief nor evaluation controls. No display-capture permission is required.
    """
    def work() -> None:
        output = RENDER_TEMP / f"{session_id}-{generation}.webm"
        final_output = VIDEOS / f"{session_id}.webm"
        command = [
            sys.executable, str(ROOT / "render_video.py"),
            "--session", session_id, "--base-url", PUBLIC_BASE_URL,
            "--output", str(output),
        ]
        with RENDER_SLOTS:
            try:
                with LOCK:
                    session = SESSIONS.get(session_id)
                    if not session or session.get("render_generation") != generation:
                        return
                    session["video_status"] = "rendering"
                    persist(session)
                completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600)
                if completed.returncode != 0:
                    raise RuntimeError((completed.stderr or completed.stdout or "video renderer failed")[-2000:])
                with LOCK:
                    session = SESSIONS.get(session_id)
                    if session and session.get("render_generation") == generation and session.get("status") == "finished":
                        output.replace(final_output)
                        session["video"] = final_output.name
                        session["video_status"] = "ready"
                        session["video_error"] = None
                        if session.get("engine")=="v2":
                            session["video_provenance"]=workflows.artifact_provenance.video_metadata(session)
                        persist(session)
                    else:
                        output.unlink(missing_ok=True)
            except Exception as exc:
                output.unlink(missing_ok=True)
                with LOCK:
                    session = SESSIONS.get(session_id)
                    if session and session.get("render_generation") == generation:
                        session["video_status"] = "error"
                        session["video_error"] = str(exc)
                        persist(session)

    worker=threading.Thread(target=work, name=f"video-{session_id}", daemon=True)
    with LOCK:
        RENDER_JOBS[session_id]=worker
        worker.start()


class Handler(BaseHTTPRequestHandler):
    server_version = "OSICL/2.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, value: object, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 5_000_000:
            raise ValueError("request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/v1/") or parsed.path == "/legacy":
            return self.send_json({"error":"Legacy tasks retired; use /studio36"},410)
        if parsed.path == "/api/v2/cases":
            return self.send_json({'benchmark_version':workflows.VERSION,'catalogue_version':'36.1-dev','cases':tasks36.CASES})
        if parsed.path.startswith("/api/v2/sessions/"):
            sid = parsed.path.rsplit("/", 1)[-1]
            with LOCK:
                session = SESSIONS.get(sid)
                if session is None and (EPISODES / f"{sid}.json").is_file():
                    session = json.loads((EPISODES / f"{sid}.json").read_text())
                    if session.get('video_status') in {'queued','rendering'}:
                        session['video_status']='interrupted'
                        persist(session)
                    SESSIONS[sid] = session
                if session is None or session.get("engine") != "v2":
                    return self.send_json({"error": "session not found"}, 404)
                if session["episode"]["case"]["id"] not in tasks36.CASE_BY_ID:
                    return self.send_json({"error":"Legacy task retired"},410)
                return self.send_json(self.v2_payload(session))
        if parsed.path == "/api/health":
            return self.send_json({"ok":True,"service":"os-icl-bench","benchmark_version":workflows.VERSION,"catalogue_version":"36.1-dev","cases":36,"legacy_cases":0})
        if parsed.path.startswith("/artifacts/"):
            name = Path(parsed.path[len("/artifacts/"):]).name
            return self.serve_file(VIDEOS / name)
        path = STATIC / ("index.html" if parsed.path in {"", "/", "/studio", "/studio36"} else parsed.path.lstrip("/"))
        return self.serve_file(path)

    def serve_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if STATIC.resolve() not in resolved.parents and VIDEOS.resolve() not in resolved.parents:
                raise FileNotFoundError
            data = resolved.read_bytes()
        except OSError:
            return self.send_error(404)
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/v2/sessions":
                return self.v2_create(self.read_json())
            if parsed.path.startswith("/api/v2/sessions/"):
                parts = parsed.path.strip("/").split("/")
                if len(parts) != 5:
                    return self.send_json({"error": "invalid endpoint"}, 404)
                return self.v2_command(parts[3], parts[4], self.read_json())
            if parsed.path.startswith("/api/v1/"):
                return self.send_json({"error":"Legacy tasks retired; use /api/v2/sessions"},410)
            return self.send_json({"error": "not found"}, 404)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:  # keep standalone service diagnosable
            return self.send_json({"error": f"internal error: {exc}"}, 500)

    def v2_payload(self, session):
        result = workflows.public(session["episode"], session["mode"])
        result.update(id=session["id"], mode=session["mode"], status=session["status"],
                      launch_url=f"/?session={session['id']}", video_status=session.get("video_status"),
                      video_url=f"/artifacts/{session['video']}" if session.get("video") else None,
                      video_error=session.get("video_error"), result=session.get("result"),
                      external_task_id=session.get("external_task_id"))
        result['compatible']=self.v2_compatible(session)
        return result

    @staticmethod
    def v2_compatible(session):
        episode=session['episode']
        return (episode.get('benchmark_version')==workflows.VERSION and
                episode.get('schema_version')==workflows.SCHEMA_VERSION and
                episode.get('implementation',{}).get('fingerprint')==workflows.IMPLEMENTATION['fingerprint'])

    def v2_create(self, body):
        mode = body.get("mode", "evaluation")
        if mode not in {"evaluation", "demo", "practice"}:
            raise ValueError("invalid session mode")
        # Rule assignment belongs to the runner, not to the visual agent.
        case_id=body.get('case_id','OS-E-01')
        if case_id not in tasks36.CASE_BY_ID:
            raise ValueError('Retired or unknown task; use the current 36-task catalogue')
        if mode == 'demo' and case_id.startswith(('OS-E-','OS-M-','OS-H-')):
            body['plan_variant']='module-demo'
        episode = workflows.generate(case_id,
            int(body.get("convention", secrets.randbelow(3))), int(body.get("seed", secrets.randbelow(1_000_000))),body.get('plan_variant','standard'))
        session = {"id": "osl_" + secrets.token_hex(8), "engine": "v2", "mode": mode,
                   "status": "active", "created_at": now_ms(), "episode": episode,
                   "ui_events": [], "actions": [], "result": None, "video": None,
                   "external_task_id": body.get("external_task_id"),
                   "external_user_id": body.get("external_user_id"),
                   "recording_actor": body.get('recording_actor','not-attested')}
        with LOCK:
            SESSIONS[session["id"]] = session
            persist(session)
        self.send_json(self.v2_payload(session), 201)

    def v2_command(self, sid, command, body):
        should_render = False
        with LOCK:
            session = SESSIONS.get(sid)
            if session is None and (EPISODES / f"{sid}.json").is_file():
                session = json.loads((EPISODES / f"{sid}.json").read_text())
                if session.get('video_status') in {'queued','rendering'}:
                    session['video_status']='interrupted'
                    persist(session)
                SESSIONS[sid] = session
            if session is None or session.get("engine") != "v2":
                return self.send_json({"error": "session not found"}, 404)
            if session["episode"]["case"]["id"] not in tasks36.CASE_BY_ID:
                return self.send_json({"error":"Legacy task retired"},410)
            compatible=self.v2_compatible(session)
            if not compatible and command != "reset":
                return self.send_json({"error":"This episode belongs to an earlier development version. Create a new episode or reset it before continuing."},409)
            if command in {"action", "ui-event"} and session["status"] != "active":
                return self.send_json({"error": "session is not active"}, 409)
            if command == "action":
                event = workflows.transition(session["episode"], body)
                event["at"] = now_ms()
                session["actions"].append(event)
                payload = self.v2_payload(session)
                payload["last_event"] = event
            elif command == "ui-event":
                if len(session["ui_events"]) >= 20000:
                    raise ValueError("interaction trace is too large")
                if body.get("type") not in {"click", "dblclick", "contextmenu", "change", "input", "submit", "keydown", "drag", "scroll"}:
                    raise ValueError("invalid interaction type")
                session["ui_events"].append({**body, "at": now_ms()})
                payload = {"ok": True}
            elif command == "reset":
                if not compatible:
                    old=session["episode"]
                    session["episode"]=workflows.generate(old["case"]["id"],old["convention"],old["seed"],old.get('plan_variant','standard'))
                session["episode"]["state"] = json.loads(json.dumps(session["episode"]["initial"]))
                session["episode"]["events"] = []
                session.update(status="active", actions=[], ui_events=[], result=None, video=None,
                               video_status=None, video_error=None)
                session["render_generation"] = int(session.get("render_generation", 0)) + 1
                payload = self.v2_payload(session)
            elif command == "judge":
                if body:
                    raise ValueError('Judge reads the persisted session only; caller-supplied states, targets and results are not accepted.')
                payload={'session_id':sid,'status':session['status'],'result':workflows.evaluate(session['episode'])}
            elif command == "finish":
                if session["status"] != "finished":
                    session.update(status="finished", result=workflows.evaluate(session["episode"]))
                if session["mode"] == "demo" and session["result"]["success"] and session["ui_events"] and not session.get("video") and session.get("video_status") not in {"queued", "rendering"}:
                    session["render_generation"] = int(session.get("render_generation", 0)) + 1
                    session["video_status"] = "queued"
                    should_render = True
                payload = self.v2_payload(session)
            elif command == "replay":
                if session["mode"] != "demo" or not (session.get("result") or {}).get("success"):
                    return self.send_json({"error": "only successful demonstrations can be replayed"}, 403)
                workflows.artifact_provenance.assert_unchanged(session['episode']['implementation'])
                import copy
                clone = copy.deepcopy(session)
                clone.update(id="osl_" + secrets.token_hex(8), mode="practice", status="active", actions=[], ui_events=[], result=None, video=None)
                clone["episode"]["state"] = copy.deepcopy(clone["episode"]["initial"])
                clone["episode"]["events"] = []
                SESSIONS[clone["id"]] = clone
                payload = {"session": self.v2_payload(clone), "trace": session["ui_events"],
                           "expected_hash": workflows.digest(session["episode"]["state"])}
            else:
                return self.send_json({"error": "unknown command"}, 404)
            persist(session)
        if should_render:
            schedule_video_render(sid, session["render_generation"])
        self.send_json(payload)


def main() -> None:
    global PUBLIC_BASE_URL
    parser = argparse.ArgumentParser(description="Run the OS-ICL desktop simulator")
    parser.add_argument("--host", default=os.environ.get("OS_ICL_HOST", os.environ.get("VIBE_HOST", "0.0.0.0")))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OS_ICL_PORT", os.environ.get("VIBE_PORT", "8790"))))
    args = parser.parse_args()
    PUBLIC_BASE_URL = os.environ.get("OS_ICL_PUBLIC_URL", os.environ.get("VIBE_PUBLIC_URL", f"http://127.0.0.1:{args.port}"))
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"OS-ICL Desktop running at http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
