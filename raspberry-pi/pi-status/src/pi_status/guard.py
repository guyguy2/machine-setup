"""Who may POST, and the audit log of every POST (agent-lab/reviews R-033).

The server listens on 127.0.0.1 only; people reach it through `tailscale serve`, which deletes any
Tailscale-User-* headers a client sends and sets Tailscale-User-Login to the tailnet login of the device's owner
(not for tagged devices). A POST must carry the login of this Pi's own owner, read from `tailscale status --json` at
run time (none in git: the repo is public). PI_STATUS_LOGINS (comma-separated) replaces that list, for tests.
"""

import json
import os
import threading
import time
from email.header import decode_header, make_header
from pathlib import Path

from . import collect

LOGINS_ENV = "PI_STATUS_LOGINS"
AUDIT_ENV = "PI_STATUS_AUDIT"
AUDIT_MAX = 1024 * 1024  # then the log moves to audit.log.1 (one old file kept)
_lock = threading.Lock()
_owner: set[str] = set()


def audit_path() -> Path:
    if os.environ.get(AUDIT_ENV):
        return Path(os.environ[AUDIT_ENV])
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(collect.HOME, ".local", "state")
    return Path(state) / "pi-status" / "audit.log"


def owner_logins() -> set[str]:
    """The tailnet login(s) allowed to POST: the owner of this node (cached once known)."""
    if os.environ.get(LOGINS_ENV):
        return {x.strip().lower() for x in os.environ[LOGINS_ENV].split(",") if x.strip()}
    if not _owner:
        try:
            data = json.loads(collect.run("tailscale", "status", "--json") or "{}")
        except ValueError:
            data = {}
        uid = str((data.get("Self") or {}).get("UserID", ""))
        login = ((data.get("User") or {}).get(uid) or {}).get("LoginName", "")
        if login:
            _owner.add(login.lower())
    return set(_owner)


def header_login(value: str | None) -> str:
    """Tailscale-User-Login as sent (RFC 2047 Q-encoded when not ASCII), decoded; "" when missing."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (ValueError, LookupError):
        return value.strip()


def check(login: str) -> tuple[int, str] | None:
    """None when this login may POST, else (status code, error message)."""
    allowed = owner_logins()
    if not allowed:
        return 503, "can't tell who owns this Pi (is Tailscale up?), so changes are refused"
    if not login:
        return 403, "no Tailscale-User-Login header: open the page through its tailnet HTTPS address"
    if login.lower() not in allowed:
        return 403, f"{login} isn't this Pi's owner"
    return None


def write(entry: dict) -> None:
    """Append one JSON line to the audit log. Never raises: a full disk mustn't break the page."""
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **entry}
    path = audit_path()
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > AUDIT_MAX:
                path.replace(path.with_name(path.name + ".1"))
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def mail_detail(body: object) -> dict:
    """What a mail POST was about, without its text: thread id, queue, how many ids. Drafts and reasons stay out."""
    if not isinstance(body, dict):
        return {}
    out: dict = {k: body[k] for k in ("thread", "queue") if isinstance(body.get(k), str)}
    for k in ("ids", "items"):
        if isinstance(body.get(k), list):
            out[k] = len(body[k])
    return out
