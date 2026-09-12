"""本机 Team Auto 控制台的 HTTP 适配层。

看板只负责把 HTTP 请求映射到 :class:`Engine` 的公开方法。它不读写
SQLite、artifact，也不执行命令。测试可以传入一个明确标注的轻量 Engine
替身，但服务本身不包含演示数据。
"""

from __future__ import annotations

import copy
import html
import ipaddress
import json
import secrets
import socket
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, unquote, urlsplit


__all__ = [
    "BoardHTTPServer",
    "BoardRequestHandler",
    "make_server",
    "serve",
]


_MAX_BODY_BYTES = 1024 * 1024
_MAX_PATH_BYTES = 8192
_MAX_ID_LENGTH = 256
_MAX_TEXT_LENGTH = 200_000
_STATIC_ROOT = Path(__file__).with_name("static")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _clone(value: Any) -> Any:
    """Make a detached value for the job registry and response assembly."""

    return copy.deepcopy(value)


class _HTTPError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class _JobRegistry:
    """Small in-process registry for long-running proposal calls.

    Jobs are deliberately process-local. Engine state remains the source of
    truth; this registry only prevents a proposal request from blocking the
    HTTP worker and makes failures observable to the browser.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def submit(self, work: Callable[[], Any]) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = _utc_now()
        job: dict[str, Any] = {
            "id": job_id,
            "kind": "propose",
            "status": "queued",
            "created_at": now,
        }
        with self._lock:
            self._jobs[job_id] = job
        worker = threading.Thread(
            target=self._run,
            args=(job_id, work),
            name=f"team-board-job-{job_id[:8]}",
            daemon=True,
        )
        worker.start()
        return _clone(job)

    def _run(self, job_id: str, work: Callable[[], Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["status"] = "running"
            job["started_at"] = _utc_now()
        try:
            result = work()
            # Validate at the boundary so a non-JSON Engine result is visible
            # as a failed job rather than an apparent success.
            json.dumps(result, ensure_ascii=False, allow_nan=False)
        except Exception as exc:  # noqa: BLE001 - the job must expose failures
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job["status"] = "failed"
                    job["error"] = {
                        "type": type(exc).__name__,
                        "message": str(exc) or "提案失败",
                    }
                    job["finished_at"] = _utc_now()
            return
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job["status"] = "succeeded"
                job["result"] = _clone(result)
                job["finished_at"] = _utc_now()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return _clone(job) if job is not None else None


class BoardHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server carrying the injected Engine and board token."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        engine: Any,
        token: str,
        handler_class: type[BaseHTTPRequestHandler] | None = None,
    ) -> None:
        self.engine = engine
        self.token = token
        # Alias is useful to callers without making the token part of a URL.
        self.board_token = token
        self.jobs = _JobRegistry()
        super().__init__(server_address, handler_class or BoardRequestHandler)


class _IPv6BoardHTTPServer(BoardHTTPServer):
    address_family = socket.AF_INET6


def _normalise_loopback_host(host: str) -> tuple[str, int]:
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host 必须是 loopback 地址")
    value = host.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if value.lower() == "localhost":
        return "127.0.0.1", socket.AF_INET
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("host 必须是 loopback 地址") from exc
    if not address.is_loopback:
        raise ValueError("看板只允许绑定到 loopback 地址")
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    return value, family


def make_server(engine: Any, host: str = "127.0.0.1", port: int = 0) -> BoardHTTPServer:
    """Create a local, threaded Team console server.

    ``port=0`` is supported for tests and callers that want the OS to select a
    free port. Binding to a non-loopback address fails before any socket is
    opened.
    """

    bind_host, family = _normalise_loopback_host(host)
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port 必须是 0 到 65535 的整数")
    server_class = _IPv6BoardHTTPServer if family == socket.AF_INET6 else BoardHTTPServer
    token = secrets.token_urlsafe(32)
    return server_class((bind_host, port), engine, token)


def serve(engine: Any, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the blocking local console loop until interrupted."""

    server = make_server(engine, host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"重复字段: {key}")
        result[key] = value
    return result


class BoardRequestHandler(BaseHTTPRequestHandler):
    """HTTP routes for the browser board."""

    server_version = "CodexTeamBoard/0.2"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Do not write request paths or headers (which could contain user data)
        # to the process log by default. Errors remain visible in JSON.
        return

    @property
    def board_server(self) -> BoardHTTPServer:
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._dispatch("POST")

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "此接口不支持 HEAD")

    def _dispatch(self, method: str) -> None:
        try:
            if len(self.path.encode("utf-8", "replace")) > _MAX_PATH_BYTES:
                raise _HTTPError(414, "uri_too_long", "请求路径过长")
            parsed = urlsplit(self.path)
            path = parsed.path or "/"
            if parsed.scheme or parsed.netloc:
                raise _HTTPError(400, "invalid_path", "请求路径无效")
            if any(part == ".." for part in path.split("/")):
                raise _HTTPError(400, "invalid_path", "请求路径无效")
            query = self._query(parsed.query)
            is_api = path.startswith("/api/")
            if is_api:
                if not self._check_request_origin(require_origin=method == "POST"):
                    return
                if method == "POST" and not self._check_token():
                    return
                if method == "GET":
                    self._handle_api_get(path, query)
                elif method == "POST":
                    self._handle_api_post(path)
                else:
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "不支持的 HTTP 方法")
                return
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "静态页面只支持 GET")
                return
            if not self._check_request_origin(require_origin=False):
                return
            self._handle_static(path, query)
        except _HTTPError as exc:
            self._send_error(exc.status, exc.code, exc.message)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001 - last-resort HTTP boundary
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                f"服务内部错误：{type(exc).__name__}",
            )

    def _query(self, raw_query: str) -> dict[str, str]:
        values = parse_qs(raw_query, keep_blank_values=True, strict_parsing=False)
        if any(key.lower() in {"token", "auth", "x-team-token", "board_token"} for key in values):
            raise _HTTPError(400, "token_in_query", "token 必须通过请求头传递")
        result: dict[str, str] = {}
        for key, items in values.items():
            if len(items) != 1:
                raise _HTTPError(400, "duplicate_query", f"重复查询参数: {key}")
            result[key] = items[0]
        return result

    def _expected_port(self) -> int:
        return int(self.board_server.server_address[1])

    @staticmethod
    def _host_is_loopback(hostname: str) -> bool:
        if hostname.lower().rstrip(".") == "localhost":
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False

    def _parse_host_header(self, raw: str | None) -> tuple[str, int] | None:
        if not raw:
            return None
        try:
            parsed = urlsplit("//" + raw)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            return None
        if not hostname or parsed.username or parsed.password or parsed.path not in ("", "/"):
            return None
        if port is None:
            port = 80
        return hostname.rstrip("."), port

    def _check_request_origin(self, *, require_origin: bool) -> bool:
        host = self._parse_host_header(self.headers.get("Host"))
        if host is None or not self._host_is_loopback(host[0]) or host[1] != self._expected_port():
            self._send_error(HTTPStatus.FORBIDDEN, "invalid_host", "只允许访问本机看板")
            return False
        origin = self.headers.get("Origin")
        if not origin:
            if require_origin:
                self._send_error(HTTPStatus.FORBIDDEN, "origin_required", "写操作需要同源 Origin")
            return not require_origin
        parsed = None
        try:
            parsed = urlsplit(origin)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            hostname = None
            port = None
        if (
            parsed is None
            or parsed.scheme.lower() != "http"
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or not hostname
            or not self._host_is_loopback(hostname)
            or (80 if port is None else port) != self._expected_port()
        ):
            self._send_error(HTTPStatus.FORBIDDEN, "cross_origin", "请求必须来自本机同源页面")
            return False
        return True

    def _check_token(self) -> bool:
        token = self.headers.get("X-Team-Token")
        if not token:
            token = self.headers.get("X-Board-Token")
        if not token or not secrets.compare_digest(token, self.board_server.token):
            self._send_error(HTTPStatus.FORBIDDEN, "invalid_token", "缺少或无效的看板 token")
            return False
        return True

    def _handle_static(self, path: str, query: Mapping[str, str]) -> None:
        if query:
            # The UI does not use query parameters. Keeping static URLs clean
            # avoids accidentally turning them into a token transport.
            raise _HTTPError(400, "unexpected_query", "静态资源不接受查询参数")
        if path in ("/", "/index.html"):
            try:
                source = (_STATIC_ROOT / "index.html").read_text(encoding="utf-8")
            except OSError as exc:
                raise _HTTPError(500, "static_unavailable", "看板页面不可用") from exc
            # The token is emitted only in the page body, never in a URL.
            token = html.escape(self.board_server.token, quote=True)
            content = source.replace("__TEAM_TOKEN__", token)
            self._send_bytes(content.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            asset = path[len("/static/") :]
            assets = {
                "app.js": "application/javascript; charset=utf-8",
                "styles.css": "text/css; charset=utf-8",
            }
            if asset not in assets:
                raise _HTTPError(404, "not_found", "资源不存在")
            try:
                content = (_STATIC_ROOT / asset).read_bytes()
            except OSError as exc:
                raise _HTTPError(500, "static_unavailable", "看板资源不可用") from exc
            self._send_bytes(content, assets[asset])
            return
        raise _HTTPError(404, "not_found", "页面不存在")

    def _handle_api_get(self, path: str, query: Mapping[str, str]) -> None:
        if path in ("/api/snapshot", "/api/state"):
            run_id = query.get("run_id") or None
            if run_id:
                self._validate_id(run_id, "run_id")
            self._call_engine(lambda: self.board_server.engine.snapshot(run_id))
            return
        if path in {"/api/notes", "/api/history"}:
            run_id = self._validate_id(query.get("run_id"), "run_id")
            package_id = query.get("package_id") or None
            if package_id:
                self._validate_id(package_id, "package_id")
            name = "get_note" if path == "/api/notes" else "search_history"
            method = getattr(self.board_server.engine, name, None)
            if not callable(method):
                raise _HTTPError(501, "unavailable", "当前 Engine 暂未提供此能力")
            if path == "/api/notes":
                if not package_id:
                    raise _HTTPError(400, "missing_field", "package_id 必须提供")
                self._call_engine(lambda: method(run_id, package_id))
            else:
                search = self._required_string(query, "query", max_length=2000)
                try:
                    limit = int(query.get("limit", "20"))
                except ValueError as exc:
                    raise _HTTPError(400, "invalid_limit", "limit 必须是整数") from exc
                if not 1 <= limit <= 100:
                    raise _HTTPError(400, "invalid_limit", "limit 必须在 1 到 100 之间")
                self._call_engine(lambda: method(run_id, search, package_id=package_id, limit=limit))
            return
        if path.startswith("/api/jobs/"):
            job_id = self._path_id(path, "/api/jobs/")
            job = self.board_server.jobs.get(job_id)
            if job is None:
                raise _HTTPError(404, "job_not_found", "任务不存在或已过期")
            self._send_success(job)
            return
        raise _HTTPError(404, "not_found", "接口不存在")

    def _handle_api_post(self, path: str) -> None:
        if path == "/api/propose":
            self._api_propose()
            return
        if path.startswith("/api/plans/") and path.endswith("/approve"):
            plan_id = self._path_id(path, "/api/plans/", "/approve")
            body = self._request_json()
            digest = self._required_string(body, "expected_digest", max_length=_MAX_TEXT_LENGTH)
            self._call_engine(lambda: self.board_server.engine.approve(plan_id, digest))
            return
        if path.startswith("/api/runs/"):
            self._api_run_post(path)
            return
        raise _HTTPError(404, "not_found", "接口不存在")

    def _api_propose(self) -> None:
        body = self._request_json()
        repository = self._required_string(body, "repository", max_length=_MAX_TEXT_LENGTH)
        brief = self._required_string(body, "brief", max_length=_MAX_TEXT_LENGTH)
        answers = body.get("answers")
        policy = body.get("policy")
        if answers is not None and not isinstance(answers, dict):
            raise _HTTPError(400, "invalid_answers", "answers 必须是对象")
        if policy is not None and not isinstance(policy, dict):
            raise _HTTPError(400, "invalid_policy", "policy 必须是对象")
        job = self.board_server.jobs.submit(
            lambda: self.board_server.engine.propose(
                repository,
                brief,
                answers=answers,
                policy=policy,
            )
        )
        self._send_success({"job": job, "job_id": job["id"], "status": job["status"]}, HTTPStatus.ACCEPTED)

    def _api_run_post(self, path: str) -> None:
        prefix = "/api/runs/"
        rest = path[len(prefix) :]
        if "/" not in rest:
            raise _HTTPError(404, "not_found", "接口不存在")
        run_id, action = rest.split("/", 1)
        run_id = self._validate_id(unquote(run_id), "run_id")
        if action in {"start", "pause", "resume", "cancel"}:
            body = self._request_json()
            if body:
                raise _HTTPError(400, "unexpected_body", "此操作不接受请求体")
            method = getattr(self.board_server.engine, action)
            self._call_engine(lambda: method(run_id))
            return
        if action == "limits":
            body = self._request_json()
            policy = body.get("policy")
            if not isinstance(policy, dict) or not policy:
                raise _HTTPError(400, "invalid_policy", "policy 必须是非空对象")
            digest = self._required_string(body, "expected_digest", max_length=_MAX_TEXT_LENGTH)
            method = getattr(self.board_server.engine, "amend_limits", None)
            if not callable(method):
                raise _HTTPError(501, "unavailable", "当前 Engine 暂未提供预算修改")
            self._call_engine(lambda: method(run_id, policy, digest))
            return
        if action in {"collaboration", "collaborations"}:
            body = self._request_json()
            from_package = self._required_string(body, "from_package", max_length=_MAX_ID_LENGTH)
            to_package = self._required_string(body, "to_package", max_length=_MAX_ID_LENGTH)
            question = self._required_string(body, "question", max_length=_MAX_TEXT_LENGTH)
            request_id = body.get("request_id")
            if request_id is not None:
                request_id = self._validate_id(request_id, "request_id")
            self._call_engine(
                lambda: self.board_server.engine.request_collaboration(
                    run_id,
                    from_package,
                    to_package,
                    question,
                    request_id=request_id,
                )
            )
            return
        if action in {"steer", "correction"}:
            body = self._request_json()
            package_id = self._required_string(body, "package_id", max_length=_MAX_ID_LENGTH)
            message = self._required_string(body, "message", max_length=_MAX_TEXT_LENGTH)
            steer = getattr(self.board_server.engine, "steer", None)
            if not callable(steer):
                raise _HTTPError(501, "unsupported", "当前 Engine 不支持运行中纠偏")
            self._call_engine(lambda: steer(run_id, package_id, message))
            return
        if action.startswith("requests/") and action.endswith("/resolve"):
            request_id = self._path_id(action, "requests/", "/resolve")
            body = self._request_json()
            answer = self._required_string(body, "answer", max_length=_MAX_TEXT_LENGTH)
            self._call_engine(lambda: self.board_server.engine.resolve_request(run_id, request_id, answer))
            return
        if action in {"checkpoint/accept", "checkpoint", "accept-checkpoint"}:
            body = self._request_json()
            digest = self._required_string(body, "expected_digest", max_length=_MAX_TEXT_LENGTH)
            self._call_engine(lambda: self.board_server.engine.accept_checkpoint(run_id, digest))
            return
        raise _HTTPError(404, "not_found", "接口不存在")

    def _request_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            length = 0
        else:
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise _HTTPError(400, "invalid_content_length", "Content-Length 无效") from exc
        if length < 0:
            raise _HTTPError(400, "invalid_content_length", "Content-Length 无效")
        if length > _MAX_BODY_BYTES:
            raise _HTTPError(413, "body_too_large", "请求体过大")
        content_type = self.headers.get("Content-Type", "")
        if content_type and not content_type.lower().split(";", 1)[0].strip() == "application/json":
            raise _HTTPError(415, "unsupported_media_type", "请求体必须是 application/json")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise _HTTPError(400, "invalid_body", "请求体不完整")
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_pairs, parse_constant=self._reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise _HTTPError(400, "invalid_json", "请求体必须是有效 JSON 对象") from exc
        if not isinstance(value, dict):
            raise _HTTPError(400, "invalid_json", "请求体必须是 JSON 对象")
        return value

    @staticmethod
    def _reject_constant(value: str) -> Any:
        raise ValueError(f"不允许 JSON 常量: {value}")

    @staticmethod
    def _required_string(body: Mapping[str, Any], key: str, *, max_length: int) -> str:
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            raise _HTTPError(400, "missing_field", f"{key} 必须是非空字符串")
        if len(value) > max_length:
            raise _HTTPError(400, "field_too_large", f"{key} 过长")
        return value.strip()

    @staticmethod
    def _validate_id(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value or len(value) > _MAX_ID_LENGTH:
            raise _HTTPError(400, "invalid_id", f"{label} 无效")
        if any(char in value for char in ("/", "\\", "\x00", "\r", "\n")):
            raise _HTTPError(400, "invalid_id", f"{label} 无效")
        return value

    @classmethod
    def _path_id(cls, path: str, prefix: str, suffix: str = "") -> str:
        if not path.startswith(prefix) or (suffix and not path.endswith(suffix)):
            raise _HTTPError(404, "not_found", "接口不存在")
        value = path[len(prefix) : len(path) - len(suffix) if suffix else None]
        if not value or "/" in value:
            raise _HTTPError(400, "invalid_id", "标识符无效")
        return cls._validate_id(unquote(value), "id")

    def _call_engine(self, call: Callable[[], Any]) -> None:
        try:
            result = call()
        except Exception as exc:  # noqa: BLE001 - map Engine boundary errors
            status = self._engine_error_status(exc)
            code = "conflict" if status == HTTPStatus.CONFLICT else "engine_error"
            message = str(exc) or "操作失败"
            self._send_error(status, code, message)
            return
        self._send_success(result)

    @staticmethod
    def _engine_error_status(exc: Exception) -> int:
        name = type(exc).__name__.lower()
        if "conflict" in name or isinstance(exc, RuntimeError) and "state" in str(exc).lower():
            return HTTPStatus.CONFLICT
        if isinstance(exc, (ValueError, KeyError, TypeError, LookupError, PermissionError)):
            return HTTPStatus.BAD_REQUEST
        return HTTPStatus.INTERNAL_SERVER_ERROR

    def _send_success(self, result: Any, status: int = HTTPStatus.OK) -> None:
        body: dict[str, Any] = {"ok": True, "data": result}
        if isinstance(result, dict):
            # Preserve the natural Engine shape for small clients while keeping
            # a stable data envelope for callers that prefer one.
            for key, value in result.items():
                body.setdefault(key, value)
        self._send_json(body, status)

    def _send_error(self, status: int, code: str, message: str) -> None:
        body = {
            "ok": False,
            "error": {"code": code, "message": message},
            "code": code,
            "message": message,
        }
        try:
            self._send_json(body, status)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_json(self, value: Mapping[str, Any], status: int) -> None:
        try:
            content = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise _HTTPError(500, "non_json_result", "Engine 返回了不可序列化结果") from exc
        self._send_bytes(content, "application/json; charset=utf-8", status)

    def _send_bytes(self, content: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(int(status))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)
