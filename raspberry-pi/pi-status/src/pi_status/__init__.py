"""Single-page Raspberry Pi status server (stdlib only)."""

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from . import collect

MAX_BODY = 64 * 1024  # POST bodies: 500 thread ids fit in about 14 KB, an 8000-character draft in under 50 KB

ROUTES = {
    "/api/status": collect.status,
    "/api/agents": collect.agents,
    "/api/dashboards": collect.dashboards,
    "/api/lab": collect.lab,
    "/api/websites": collect.websites,
    "/api/rei": collect.rei,
    "/api/emails": collect.emails,
    "/api/docker": collect.docker,
    "/api/services": collect.services,
    "/api/processes": collect.top_processes,
    "/api/ports": collect.ports,
    "/api/network": collect.network,
    "/api/auth": collect.auth_status,
    "/api/version": collect.version,
}


class Handler(BaseHTTPRequestHandler):
    def send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def respond(self) -> tuple[int, str, bytes]:
        path = self.path.split("?")[0]
        if path in ROUTES:
            try:
                return 200, "application/json", json.dumps(ROUTES[path]()).encode()
            except Exception as e:  # keep the server alive; the page shows the error
                return 500, "application/json", json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
        if path in ("/", "/index.html"):
            return 200, "text/html; charset=utf-8", files(__package__).joinpath("index.html").read_bytes()
        return 404, "text/plain", b"not found"

    def do_GET(self) -> None:
        try:
            self.send(*self.respond())
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser navigated away mid-request

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        restart = False
        agent = re.fullmatch(r"/api/agents/([\w.@-]+)/(start|stop)", path)
        mail = re.fullmatch(r"/api/emails/(decide|accept|reason|undo|trash|draft|draft-save|draft-drop)", path)
        if path != "/api/restart" and not agent and not mail:
            code, body = 404, {"error": "not found"}
        elif self.headers.get("X-Requested-With") != "pi-status":
            # A custom header can't be sent cross-site without a CORS preflight (which we never allow), so
            # another website can't make your browser restart this server, start and stop agents or touch mail.
            code, body = 403, {"error": "missing X-Requested-With header"}
        elif mail:
            code, body = self.mail(mail[1])
        elif agent:
            code, body = collect.control_agent(agent[1], agent[2])
        elif not collect.can_restart():
            code, body = 409, {"error": "not running under systemd; restart it by hand"}
        else:
            code, body, restart = 202, {"restarting": True}, True
        try:
            self.send(code, "application/json", json.dumps(body).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass
        if restart:
            collect.restart_service()  # after the reply, because this process is about to be stopped

    def mail(self, action: str) -> tuple[int, dict]:
        """A choice from the Emails tab: a small JSON body, checked and run by collect.mail_action."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return 413 if length > MAX_BODY else 400, {"ok": False, "error": f"send a JSON body of at most {MAX_BODY} bytes"}
        try:
            body = json.loads(self.rfile.read(length))
        except ValueError:
            return 400, {"ok": False, "error": "the body isn't valid JSON"}
        return collect.mail_action(action, body)

    def log_message(self, format: str, *args) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi status page")
    parser.add_argument("--host", help="address to bind (default: Tailscale IPv4, else 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    host = args.host or collect.run("tailscale", "ip", "-4") or "127.0.0.1"
    collect.version()  # remember which code this process loaded, to flag a stale server later
    threading.Thread(target=collect.refresh_auth, daemon=True).start()  # warm the sign-in cache
    print(f"Serving on http://{host}:{args.port}", flush=True)
    ThreadingHTTPServer((host, args.port), Handler).serve_forever()
