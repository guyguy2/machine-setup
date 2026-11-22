#!/usr/bin/env python3
"""Resume a Claude Code session in tmux after its 5-hour usage limit resets.

Three parts, all in this file:

  record    Statusline hook. Reads the statusline JSON on stdin and saves the
            rate-limit windows (including five_hour.resets_at, a Unix epoch)
            for the session. Never prints anything.
  hook      StopFailure hook. Returns immediately and starts a detached
            "schedule" process that waits for the reset and then types
            "continue" + Enter into the tmux pane Claude runs in.
  schedule  Internal. Decides whether the 5-hour window is the blocker, waits
            until the reset, checks the session did not already move on, and
            sends the keys.
  status    Show waiters that are currently scheduled.
  send      Type a message + Enter into a tmux pane right now (--pane %8 "text").
            No state checks: it lands in whatever the pane is showing.

Wiring (see the repo CLAUDE.md for the exact snippets):
  - statusline script: pipe its stdin to `claude-resume.py record` in the background
  - settings.json: a StopFailure hook (no matcher) running `claude-resume.py hook`

Safety: before sending, the script skips if the session transcript shows new
real activity since scheduling (you, or Claude's built-in auto-continue, got
there first), if the pane is gone, or if it already sent to this pane in the
last few minutes. Only the 5-hour window is acted on; weekly and per-model
limits are ignored.

Exit codes: 0 success, 1 general error, 2 invalid input.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

EXIT_OK, EXIT_ERROR, EXIT_INVALID = 0, 1, 2

DEFAULT_TEXT = "continue"
DEFAULT_BUFFER = 45  # seconds to wait past the reset
DEFAULT_MAX_WAIT = 5.5 * 3600  # ignore resets further away than this (weekly limits)
DEFAULT_SETTLE = 3  # seconds for the TUI to draw the limit message
FIVE_HOUR_THRESHOLD = 95  # used_percentage that counts as "at the limit" (statusline can lag)
SEND_COOLDOWN = 300  # never send to the same pane twice within this many seconds
FOOTER_RE = re.compile(r"Usage limit reached|Continuing automatically|limit resets", re.I)
STATE_MAX_AGE = 3 * 86400
LOG_MAX_BYTES = 256 * 1024

VERBOSE = False


# ---------------------------------------------------------------------------
# State and logging
# ---------------------------------------------------------------------------

def state_dir() -> Path:
    override = os.environ.get("CLAUDE_RESUME_STATE")
    if override:
        return Path(override)
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "claude-resume"


def trim_log(path: Path, keep_bytes: int) -> None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    kept: list[str] = []
    size = 0
    for ln in reversed(lines):
        b = len(ln.encode("utf-8"))
        if kept and size + b > keep_bytes:
            break
        kept.append(ln)
        size += b
    kept.reverse()
    path.write_text("".join(kept), encoding="utf-8")


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{os.getpid()}] {msg}"
    if VERBOSE:
        print(line, file=sys.stderr)
    try:
        d = state_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = d / "log"
        if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
            trim_log(path, LOG_MAX_BYTES // 2)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


@contextlib.contextmanager
def waiter_lock(path: Path):
    lock_path = path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def parse_waiter(data: dict) -> tuple[int, float] | None:
    if isinstance(data.get("pid"), bool) or isinstance(data.get("wake"), bool):
        return None
    try:
        pid = int(data["pid"])
        wake = float(data["wake"])
    except (KeyError, TypeError, ValueError):
        return None
    return (pid, wake) if pid > 0 else None


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


# ---------------------------------------------------------------------------
# Pure logic (unit tested)
# ---------------------------------------------------------------------------

def parse_limits(statusline: dict) -> dict:
    """Extract {'five_hour': {'pct', 'resets_at'}, 'seven_day': {...}} from statusline JSON."""
    out: dict = {}
    windows = statusline.get("rate_limits")
    if not isinstance(windows, dict):
        return out
    for key in ("five_hour", "seven_day"):
        w = windows.get(key)
        if not isinstance(w, dict):
            continue
        try:
            out[key] = {
                "pct": float(w.get("used_percentage") or 0),
                "resets_at": float(w.get("resets_at") or 0),
            }
        except (TypeError, ValueError):
            continue
    return out


def pane_limit_kind(text: str) -> str | None:
    """Classify the most recent 'You've hit your X limit' message: session, weekly or model."""
    matches = re.findall(
        r"hit your ((?!\blimit\b)[A-Za-z0-9][A-Za-z0-9._-]*(?: (?!\blimit\b)[A-Za-z0-9][A-Za-z0-9._-]*){0,3}) limit",
        text, re.I)
    if not matches:
        return None
    word = matches[-1].lower()
    if word == "session":
        return "session"
    if word == "weekly":
        return "weekly"
    return "model"


def parse_pane_reset(text: str, now: float) -> float | None:
    """Parse 'resets 3:45pm' (local time) into the next matching epoch. Weekday forms return None."""
    matches = re.findall(
        r"resets\s+(?:(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)",
        text,
        re.I,
    )
    if not matches:
        return None
    weekday, hour, minute, meridiem = matches[-1]
    if weekday:
        return None
    h = int(hour) % 12 + (12 if meridiem.lower() == "pm" else 0)
    m = int(minute or 0)
    if h > 23 or m > 59:
        return None
    target = datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0)
    if target.timestamp() <= now:
        target += timedelta(days=1)
    return target.timestamp()


def footer_present(text: str) -> bool:
    """True if the bottom of the pane shows the waiting-for-reset footer."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return bool(FOOTER_RE.search("\n".join(lines[-8:])))


def decide(limits: dict, pane_text: str, now: float, max_wait: float) -> tuple[float | None, str]:
    """Return (reset_epoch, reason). reset_epoch is None when we should not act."""
    kind = pane_limit_kind(pane_text)
    if kind in ("weekly", "model"):
        return None, f"blocked by the {kind} limit, not the 5-hour window"
    five = limits.get("five_hour")
    seven = limits.get("seven_day")
    if kind != "session" and seven and seven["pct"] >= 100:
        return None, "weekly window is exhausted"
    five_live = bool(five and five["resets_at"] > now)
    at_limit = bool(five_live and five["pct"] >= FIVE_HOUR_THRESHOLD)
    if kind != "session" and not at_limit:
        return None, "no sign that the 5-hour window is exhausted"
    reset = five["resets_at"] if five_live else parse_pane_reset(pane_text, now)
    if reset is None:
        return None, "5-hour limit but the reset time is unknown"
    if reset - now > max_wait:
        return None, f"reset is {int((reset - now) / 60)} min away, over the max wait"
    return reset, "5-hour limit"


def transcript_activity(path: str | None) -> int | None:
    """Count real user/assistant entries in a transcript JSONL (None if unreadable)."""
    if not path:
        return None
    count = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") not in ("user", "assistant"):
                    continue
                if entry.get("isMeta") or entry.get("isApiErrorMessage"):
                    continue
                message = entry.get("message")
                if isinstance(message, dict) and message.get("model") == "<synthetic>":
                    continue
                count += 1
    except OSError:
        return None
    return count


# ---------------------------------------------------------------------------
# tmux
# ---------------------------------------------------------------------------

def tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def pane_exists(pane: str) -> bool:
    r = tmux("display-message", "-p", "-t", pane, "#{pane_id}")
    return r.returncode == 0 and r.stdout.strip() == pane


def capture_pane(pane: str) -> str:
    r = tmux("capture-pane", "-p", "-t", pane, "-S", "-60")
    return r.stdout if r.returncode == 0 else ""


def ppid_of(pid: int) -> int | None:
    r = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


def pane_pid(pane: str) -> int | None:
    r = tmux("display-message", "-p", "-t", pane, "#{pane_pid}")
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


def find_claude_pid(root: int, start: int, parent_of=ppid_of, max_depth: int = 12) -> int | None:
    """Walk up from `start` to the process that is `root` (the pane's process) or its direct child."""
    pid: int | None = start
    for _ in range(max_depth):
        if pid is None or pid <= 1:
            return None
        if pid == root:
            return pid
        parent = parent_of(pid)
        if parent == root:
            return pid
        pid = parent
    return None


def running_in_pane(pid: int, pane: str) -> bool:
    """True if `pid` is alive and still the pane's process or a direct child of it."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    root = pane_pid(pane)
    return root is not None and (pid == root or ppid_of(pid) == root)


def send_continue(pane: str, text: str) -> bool:
    # Text and Enter go as two calls: the TUI can swallow an Enter that arrives with the text.
    if tmux("send-keys", "-t", pane, "-l", text).returncode != 0:
        return False
    time.sleep(0.4)
    return tmux("send-keys", "-t", pane, "Enter").returncode == 0


# ---------------------------------------------------------------------------
# Waiter bookkeeping
# ---------------------------------------------------------------------------

def waiter_path(pane: str) -> Path:
    return state_dir() / "waiters" / f"{safe_name(pane)}.json"


def sent_path(pane: str) -> Path:
    return state_dir() / "sent" / f"{safe_name(pane)}.json"


def is_our_process(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    r = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return "claude-resume" in r.stdout


def sleep_until(target: float, step: float = 20.0) -> None:
    # Wall-clock loop in short steps: time.sleep does not count time the Mac spent asleep.
    while True:
        remaining = target - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, step))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_record(args: argparse.Namespace) -> int:
    try:
        data = json.load(sys.stdin)
        session_id = data.get("session_id")
        limits = parse_limits(data)
        if not session_id or not limits:
            return EXIT_OK
        d = state_dir() / "sessions"
        write_json_atomic(
            d / f"{safe_name(str(session_id))}.json",
            {"updated": time.time(), "pane": os.environ.get("TMUX_PANE"), "limits": limits},
        )
        cutoff = time.time() - STATE_MAX_AGE
        for f in d.glob("*.json"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
    except Exception as exc:  # statusline must never break
        log(f"record failed: {exc!r}")
    return EXIT_OK


def cmd_hook(args: argparse.Namespace, forward: list[str]) -> int:
    try:
        data = json.load(sys.stdin)
        payload = {
            "session_id": data.get("session_id"),
            "transcript_path": data.get("transcript_path"),
            "error": data.get("error"),
            "error_details": data.get("error_details"),
            "last_assistant_message": str(data.get("last_assistant_message") or "")[:200],
        }
        pane = os.environ.get("TMUX_PANE")
        root = pane_pid(pane) if pane else None
        payload["claude_pid"] = find_claude_pid(root, os.getppid()) if root else None
        log(f"StopFailure: {json.dumps(payload)} pane={pane}")
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "schedule", *forward,
             "--payload", json.dumps(payload)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as exc:  # a hook must never break Claude
        log(f"hook failed: {exc!r}")
    return EXIT_OK


def cmd_schedule(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(args.payload)
    except ValueError:
        log("schedule: bad payload")
        return EXIT_INVALID
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        log("schedule: not running inside tmux, nothing to do")
        return EXIT_OK

    time.sleep(args.settle)  # let the TUI draw the limit message
    pane_text = capture_pane(pane)
    if (payload.get("error") != "rate_limit" and pane_limit_kind(pane_text) is None
            and not footer_present(pane_text)):
        log(f"skip: failure {payload.get('error')!r} does not look like a usage limit")
        return EXIT_OK

    sid = payload.get("session_id")
    limits = read_json(state_dir() / "sessions" / f"{safe_name(str(sid))}.json").get("limits", {}) if sid else {}
    now = time.time()
    reset, reason = decide(limits, pane_text, now, args.max_wait)
    if reset is None:
        log(f"skip: {reason}")
        return EXIT_OK

    transcript = payload.get("transcript_path")
    baseline = transcript_activity(transcript)
    wake = reset + args.buffer
    path = waiter_path(pane)
    with waiter_lock(path):
        old = parse_waiter(read_json(path))
        if old and is_our_process(old[0]) and old[0] != os.getpid():
            if abs(old[1] - wake) < 120:
                log(f"skip: waiter {old[0]} already scheduled for {pane}")
                return EXIT_OK
            try:
                os.kill(old[0], signal.SIGTERM)
            except ProcessLookupError:
                pass
            log(f"replaced waiter {old[0]} for {pane}")
        write_json_atomic(path, {"pid": os.getpid(), "wake": wake, "session_id": sid})
    log(f"scheduled {pane}: {reason}, wake at {datetime.fromtimestamp(wake):%H:%M:%S} "
        f"(in {int(wake - now)}s), baseline={baseline}")

    if args.caffeinate:
        caf = shutil.which("caffeinate")
        if caf:
            subprocess.Popen([caf, "-i", "-w", str(os.getpid())],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            log("caffeinate unavailable on this platform; skipping")
    try:
        sleep_until(wake)
        return wake_and_send(args, pane, transcript, baseline, payload.get("claude_pid"))
    finally:
        with waiter_lock(path):
            cur = parse_waiter(read_json(path))
            if cur and cur[0] == os.getpid():
                path.unlink(missing_ok=True)


def wake_and_send(args: argparse.Namespace, pane: str, transcript: str | None,
                  baseline: int | None, claude_pid: int | None) -> int:
    if read_json(waiter_path(pane)).get("pid") != os.getpid():
        log("skip: a newer waiter owns this pane")
        return EXIT_OK
    if not pane_exists(pane):
        log(f"skip: pane {pane} no longer exists")
        return EXIT_OK
    if claude_pid is not None and not running_in_pane(claude_pid, pane):
        log(f"skip: Claude (pid {claude_pid}) is no longer running in {pane}")
        return EXIT_OK
    current = transcript_activity(transcript)
    footer = footer_present(capture_pane(pane))
    if baseline is not None and current is not None and current > baseline:
        log(f"skip: session moved on ({baseline} -> {current} entries); footer={footer}")
        return EXIT_OK
    if (claude_pid is None or baseline is None or current is None) and not footer:
        log("skip: cannot confirm the session is still the same one and the pane shows no limit footer")
        return EXIT_OK
    last_sent = read_json(sent_path(pane)).get("at", 0)
    if time.time() - last_sent < SEND_COOLDOWN:
        log("skip: already sent to this pane recently")
        return EXIT_OK
    if args.dry_run:
        log(f"dry-run: would send {args.text!r} + Enter to {pane}")
        return EXIT_OK
    if not send_continue(pane, args.text):
        log(f"send to {pane} failed")
        return EXIT_ERROR
    write_json_atomic(sent_path(pane), {"at": time.time()})
    log(f"sent {args.text!r} + Enter to {pane}")
    return EXIT_OK


def cmd_send(args: argparse.Namespace) -> int:
    # No state checks: the text is typed into whatever the pane is showing right now.
    if not pane_exists(args.pane):
        print(f"pane {args.pane} not found", file=sys.stderr)
        return EXIT_INVALID
    if not send_continue(args.pane, args.text):
        print(f"send to {args.pane} failed", file=sys.stderr)
        return EXIT_ERROR
    log(f"sent {args.text!r} + Enter to {args.pane} (manual send)")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    found = False
    for f in sorted((state_dir() / "waiters").glob("*.json")):
        w = parse_waiter(read_json(f))
        if w and is_our_process(w[0]):
            found = True
            print(f"pane {f.stem}: pid {w[0]}, wakes at {datetime.fromtimestamp(w[1]):%Y-%m-%d %H:%M:%S}")
    if not found:
        print("no waiters scheduled")
    return EXIT_OK


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="also log to stderr")
    common.add_argument("--text", default=DEFAULT_TEXT, help=f"text to send (default: {DEFAULT_TEXT})")
    common.add_argument("--buffer", type=float, default=DEFAULT_BUFFER, help="seconds to wait past the reset")
    common.add_argument("--max-wait", type=float, default=DEFAULT_MAX_WAIT,
                        help="ignore resets further away than this many seconds")
    common.add_argument("--settle", type=float, default=DEFAULT_SETTLE,
                        help="seconds to let the TUI draw before reading the pane")
    common.add_argument("--dry-run", action="store_true", help="log instead of sending keys")
    common.add_argument("--caffeinate", action="store_true", help="keep the Mac from idle-sleeping while waiting")

    parser = argparse.ArgumentParser(description="Resume Claude Code in tmux after the 5-hour limit resets.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("record", help="statusline hook: save rate-limit windows from stdin")
    sub.add_parser("hook", parents=[common], help="StopFailure hook: schedule a resume")
    p = sub.add_parser("schedule", parents=[common], help="internal: wait and send")
    p.add_argument("--payload", required=True)
    p = sub.add_parser("send", help="type a message + Enter into a tmux pane right now, whatever its state")
    p.add_argument("-v", "--verbose", action="store_true", help="also log to stderr")
    p.add_argument("--pane", required=True, help="tmux pane id (e.g. %%8; see: tmux list-panes -a -F '#{pane_id}')")
    p.add_argument("text", help="message to send")
    sub.add_parser("status", help="show scheduled waiters")
    return parser


def main(argv: list[str] | None = None) -> int:
    global VERBOSE
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    VERBOSE = getattr(args, "verbose", False)
    if args.command == "record":
        return cmd_record(args)
    if args.command == "hook":
        return cmd_hook(args, argv[1:])
    if args.command == "schedule":
        return cmd_schedule(args)
    if args.command == "send":
        return cmd_send(args)
    return cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
