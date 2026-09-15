"""Loopback adaptive Team board; all mutations go through the runtime."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit, parse_qs

from .adaptive import ConflictError, ident
from .adaptive_runner import Runner, reconcile


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, engine, port):
        self.engine = engine
        self.token = secrets.token_urlsafe(32)
        self.jobs = {}
        self.jobs_lock = threading.RLock()
        super().__init__(("127.0.0.1", port), Handler)

    def job(self, run_id, action):
        with self.jobs_lock:
            for job in self.jobs.values():
                if job["run_id"] == run_id and job["status"] == "running":
                    return dict(job)
            job = {"id": ident("job"), "run_id": run_id, "action": action, "status": "running"}
            self.jobs[job["id"]] = job
        def execute():
            try:
                result = Runner(self.engine, run_id).run() if action == "run" else reconcile(self.engine, run_id)
                with self.jobs_lock:
                    job.update(status="finished", result=result)
            except Exception as exc:
                with self.jobs_lock:
                    job.update(status="failed", error=str(exc))
        threading.Thread(target=execute, name=job["id"], daemon=True).start()
        return dict(job)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, value, mime="application/json; charset=utf-8"):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def _host(self):
        port = self.server.server_port
        host = self.headers.get("Host", "")
        if host not in {"127.0.0.1:" + str(port), "localhost:" + str(port)}:
            raise PermissionError("Unexpected host")
        return "http://" + host

    def do_GET(self):
        try:
            self._host()
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            root = Path(__file__).with_name("static")
            static = {"/": ("adaptive.html", "text/html; charset=utf-8"),
                      "/adaptive.js": ("adaptive.js", "text/javascript; charset=utf-8"),
                      "/adaptive.css": ("adaptive.css", "text/css; charset=utf-8")}
            if parsed.path in static:
                name, mime = static[parsed.path]
                self.respond(200, (root / name).read_bytes(), mime)
            elif parsed.path == "/api/runs":
                with self.server.jobs_lock:
                    jobs = [dict(job) for job in self.server.jobs.values()]
                self.respond(200, {"runs": self.server.engine.store.list("adaptive-run"), "token": self.server.token, "jobs": jobs})
            elif parsed.path == "/api/snapshot":
                self.respond(200, self.server.engine.snapshot(query["run"][0]))
            elif parsed.path == "/api/history":
                self.respond(200, self.server.engine.history(query["run"][0], query.get("q", [""])[0],
                             after=int(query.get("after", ["0"])[0]), limit=20))
            elif parsed.path == "/api/result":
                data = self.server.engine.run(query["run"][0])["data"]
                work = data["works"][query["work"][0]]
                if not work.get("result"):
                    raise ValueError("Work has no result yet")
                self.respond(200, self.server.engine.read_artifact(work["result"]))
            else:
                self.respond(404, {"error": "not-found"})
        except PermissionError as exc:
            self.respond(403, {"error": str(exc)})
        except (ValueError, KeyError, OSError, ConflictError) as exc:
            self.respond(400, {"error": str(exc)})

    def do_POST(self):
        try:
            origin = self._host()
            if self.headers.get("Origin") != origin or not secrets.compare_digest(self.headers.get("X-Team-Token", ""), self.server.token):
                raise PermissionError("Same-origin action token required")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("JSON request required")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024 * 1024:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            parts = urlsplit(self.path).path.split("/")
            if len(parts) != 4 or parts[:2] != ["", "api"]:
                self.respond(404, {"error": "not-found"})
                return
            run_id, action = parts[2:]
            self.server.engine.run(run_id)
            if action in {"run", "reconcile"}:
                result = self.server.job(run_id, action)
                self.respond(202, result)
                return
            if action in {"pause", "cancel"}:
                result = self.server.engine.stop(run_id, "pause" if action == "pause" else "cancel")
            elif action == "message":
                result = self.server.engine.message(run_id, payload["text"], operation_id=payload["operation_id"])
            else:
                self.respond(404, {"error": "not-found"})
                return
            self.respond(200, result)
        except PermissionError as exc:
            self.respond(403, {"error": str(exc)})
        except ConflictError as exc:
            self.respond(409, {"error": str(exc)})
        except (ValueError, KeyError, OSError) as exc:
            self.respond(400, {"error": str(exc)})


def make_server(engine, port=0):
    return Server(engine, port)


def serve(engine, port=8766):
    server = make_server(engine, port)
    print("Codex Team: http://127.0.0.1:" + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
