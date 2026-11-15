"""Tests for claude-resume.py. Run: uv run --with pytest pytest tests/ -q

The tmux tests start their own server on a private socket and never touch a live session.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "claude-resume.py"
spec = importlib.util.spec_from_file_location("claude_resume", SCRIPT)
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

LIMIT_MSG = "You've hit your session limit · resets 3:45pm"


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------

def local_epoch(hour, minute=0, day=15):
    return datetime(2026, 11, day, hour, minute).timestamp()


def test_parse_pane_reset_same_day():
    now = local_epoch(10, 0)
    assert cr.parse_pane_reset(LIMIT_MSG, now) == local_epoch(15, 45)


def test_parse_pane_reset_rolls_to_tomorrow():
    now = local_epoch(16, 0)
    assert cr.parse_pane_reset("resets 3:45pm", now) == local_epoch(15, 45, day=16)


def test_parse_pane_reset_hour_only_and_midnight():
    now = local_epoch(10, 0)
    assert cr.parse_pane_reset("resets 5pm", now) == local_epoch(17, 0)
    assert cr.parse_pane_reset("resets 12am", now) == local_epoch(0, 0, day=16)


def test_parse_pane_reset_weekday_is_ignored():
    assert cr.parse_pane_reset("resets Mon 12:00am", local_epoch(10)) is None


def test_pane_limit_kind_uses_latest_message():
    assert cr.pane_limit_kind(LIMIT_MSG) == "session"
    assert cr.pane_limit_kind("You've hit your weekly limit · resets Mon 12:00am") == "weekly"
    assert cr.pane_limit_kind("You've hit your Opus limit") == "model"
    assert cr.pane_limit_kind("hit your weekly limit ... later ... hit your session limit") == "session"
    assert cr.pane_limit_kind("just a prompt") is None


def test_footer_present_only_checks_bottom_lines():
    bottom = "chat\n" * 20 + "Usage limit reached · limit resets 3:45pm\n"
    assert cr.footer_present(bottom)
    assert not cr.footer_present("Usage limit reached\n" + "chat\n" * 20)


NOW = 1_000_000.0


def limits(five_pct, five_reset, seven_pct=10.0):
    return {"five_hour": {"pct": five_pct, "resets_at": five_reset},
            "seven_day": {"pct": seven_pct, "resets_at": NOW + 86400}}


def test_decide_acts_on_five_hour_limit():
    reset, _ = cr.decide(limits(100, NOW + 3600), "", NOW, 5.5 * 3600)
    assert reset == NOW + 3600


def test_decide_accepts_stale_percentage_when_pane_says_session():
    reset, _ = cr.decide(limits(80, NOW + 3600), LIMIT_MSG, NOW, 5.5 * 3600)
    assert reset == NOW + 3600


def test_decide_skips_low_usage_without_message():
    reset, _ = cr.decide(limits(40, NOW + 3600), "", NOW, 5.5 * 3600)
    assert reset is None


def test_decide_skips_weekly_and_model_limits():
    assert cr.decide(limits(100, NOW + 3600), "hit your weekly limit", NOW, 5.5 * 3600)[0] is None
    assert cr.decide(limits(100, NOW + 3600), "hit your Opus limit", NOW, 5.5 * 3600)[0] is None
    assert cr.decide(limits(100, NOW + 3600, seven_pct=100), "", NOW, 5.5 * 3600)[0] is None


def test_decide_falls_back_to_pane_time_when_no_statusline_data():
    now = local_epoch(10, 0)
    reset, _ = cr.decide({}, LIMIT_MSG, now, 24 * 3600)
    assert reset == local_epoch(15, 45)


def test_decide_skips_when_reset_too_far():
    assert cr.decide(limits(100, NOW + 10 * 3600), "", NOW, 5.5 * 3600)[0] is None


def test_decide_ignores_past_reset_window():
    assert cr.decide(limits(100, NOW - 10), "", NOW, 5.5 * 3600)[0] is None


def test_transcript_activity_ignores_synthetic_and_meta(tmp_path):
    t = tmp_path / "t.jsonl"
    entries = [
        {"type": "user", "message": {"content": "hi"}},
        {"type": "assistant", "message": {"model": "claude"}},
        {"type": "assistant", "message": {"model": "<synthetic>"}},
        {"type": "assistant", "isApiErrorMessage": True},
        {"type": "user", "isMeta": True},
        {"type": "attachment"},
    ]
    t.write_text("\n".join(json.dumps(e) for e in entries) + "\nnot json\n")
    assert cr.transcript_activity(str(t)) == 2
    assert cr.transcript_activity(str(tmp_path / "missing")) is None
    assert cr.transcript_activity(None) is None


def test_find_claude_pid_walks_up_to_child_of_pane():
    parents = {50: 40, 40: 30, 30: 20, 20: 1}  # hook sh -> claude -> pane shell(20)
    assert cr.find_claude_pid(20, 50, parent_of=parents.get) == 30
    assert cr.find_claude_pid(20, 20, parent_of=parents.get) == 20
    assert cr.find_claude_pid(99, 50, parent_of=parents.get) is None


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

def run(args, stdin="", env=None, **kw):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, text=True,
                          capture_output=True, env=env, **kw)


@pytest.fixture
def env(tmp_path):
    # Whitelist instead of copying os.environ: keeps secrets out of pytest failure output.
    e = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TERM") if k in os.environ}
    e["CLAUDE_RESUME_STATE"] = str(tmp_path / "state")
    return e


def test_record_saves_limits_and_prints_nothing(env, tmp_path):
    payload = {"session_id": "abc", "rate_limits": {
        "five_hour": {"used_percentage": 42.5, "resets_at": 1234},
        "seven_day": {"used_percentage": 3, "resets_at": 5678}}}
    r = run(["record"], json.dumps(payload), env)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    saved = json.loads((tmp_path / "state" / "sessions" / "abc.json").read_text())
    assert saved["limits"]["five_hour"] == {"pct": 42.5, "resets_at": 1234.0}


def test_record_ignores_payload_without_limits_and_bad_json(env, tmp_path):
    assert run(["record"], json.dumps({"session_id": "abc"}), env).returncode == 0
    assert run(["record"], "not json", env).returncode == 0
    assert not (tmp_path / "state" / "sessions").exists()


# ---------------------------------------------------------------------------
# End to end against a real tmux server
# ---------------------------------------------------------------------------

pytestmark_tmux = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")


class Tmux:
    def __init__(self, sock):
        self.sock = str(sock)

    def run(self, *args):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("TMUX")}
        return subprocess.run(["tmux", "-S", self.sock, "-f", "/dev/null", *args],
                              capture_output=True, text=True, env=clean)

    def start(self, message):
        """Start a pane that prints `message`, then echoes the next line typed as GOT:<line>."""
        script = Path(self.sock).parent / "pane.sh"
        script.write_text(f'cat <<"EOF"\n{message}\nEOF\nread line\necho "GOT:$line"\nsleep 60\n')
        self.run("new-session", "-d", "-x", "120", "-y", "30", "-s", "t", f"bash --norc {script}")
        pane = self.run("list-panes", "-a", "-F", "#{pane_id}").stdout.split()[0]
        pid = self.run("display-message", "-p", "#{pid}").stdout.strip()
        return pane, pid

    def screen(self, pane):
        return self.run("capture-pane", "-p", "-t", pane).stdout


@pytest.fixture
def tmux():
    # macOS limits unix socket paths to about 100 chars, so pytest's tmp_path is too long.
    sock_dir = tempfile.mkdtemp(prefix="crt", dir="/tmp")
    t = Tmux(Path(sock_dir) / "s")
    yield t
    t.run("kill-server")
    shutil.rmtree(sock_dir, ignore_errors=True)


FOOTER = "Usage limit reached \u00b7 limit resets 3:45pm"
PANE_CMD = LIMIT_MSG + "\n" + FOOTER


def write_session_state(env, resets_at, pct=100):
    d = Path(env["CLAUDE_RESUME_STATE"]) / "sessions"
    d.mkdir(parents=True)
    (d / "sess1.json").write_text(json.dumps({"limits": {
        "five_hour": {"pct": pct, "resets_at": resets_at},
        "seven_day": {"pct": 1, "resets_at": resets_at + 86400}}}))


def tmux_env(env, tmux, pane, pid):
    e = dict(env)
    e["TMUX"] = f"{tmux.sock},{pid},0"
    e["TMUX_PANE"] = pane
    return e


def wait_for(predicate, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def write_transcript(path, n):
    path.write_text("".join(json.dumps({"type": "user", "message": {"content": str(i)}}) + "\n"
                            for i in range(n)))


@pytestmark_tmux
def test_hook_returns_fast_and_waiter_types_continue(env, tmux, tmp_path):
    pane, pid = tmux.start(PANE_CMD)
    assert wait_for(lambda: "session limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 3)
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 3)
    hook_payload = {"session_id": "sess1", "transcript_path": str(transcript), "error": "rate_limit"}

    start = time.time()
    r = run(["hook", "--settle", "0.5", "--buffer", "0"], json.dumps(hook_payload),
            tmux_env(env, tmux, pane, pid))
    elapsed = time.time() - start
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert elapsed < 1.0, f"hook took {elapsed:.2f}s"

    assert wait_for(lambda: "GOT:continue" in tmux.screen(pane)), tmux.screen(pane)
    log = (Path(env["CLAUDE_RESUME_STATE"]) / "log").read_text()
    assert "sent 'continue' + Enter" in log


@pytestmark_tmux
def test_waiter_skips_when_session_moved_on(env, tmux, tmp_path):
    pane, pid = tmux.start(PANE_CMD)
    assert wait_for(lambda: "session limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 4)
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 3)
    payload = json.dumps({"session_id": "sess1", "transcript_path": str(transcript), "error": "rate_limit"})

    proc = subprocess.Popen([sys.executable, str(SCRIPT), "schedule", "--settle", "0.5",
                             "--buffer", "0", "--payload", payload],
                            env=tmux_env(env, tmux, pane, pid))
    time.sleep(1.5)  # baseline is taken by now
    write_transcript(transcript, 5)  # the session did something while we waited
    assert proc.wait(timeout=20) == 0
    assert "GOT:" not in tmux.screen(pane)
    assert "session moved on" in (Path(env["CLAUDE_RESUME_STATE"]) / "log").read_text()


@pytestmark_tmux
def test_waiter_skips_weekly_limit(env, tmux, tmp_path):
    pane, pid = tmux.start("You've hit your weekly limit \u00b7 resets Mon 12:00am")
    assert wait_for(lambda: "weekly limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 3)
    payload = json.dumps({"session_id": "sess1", "error": "rate_limit"})
    r = run(["schedule", "--settle", "0.5", "--buffer", "0", "--payload", payload],
            env=tmux_env(env, tmux, pane, pid), timeout=20)
    assert r.returncode == 0
    assert "GOT:" not in tmux.screen(pane)
    assert "weekly limit" in (Path(env["CLAUDE_RESUME_STATE"]) / "log").read_text()


@pytestmark_tmux
def test_dry_run_does_not_send(env, tmux, tmp_path):
    pane, pid = tmux.start(PANE_CMD)
    assert wait_for(lambda: "session limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 2)
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 1)
    payload = json.dumps({"session_id": "sess1", "transcript_path": str(transcript), "error": "rate_limit"})
    r = run(["schedule", "--settle", "0.2", "--buffer", "0", "--dry-run", "--payload", payload],
            env=tmux_env(env, tmux, pane, pid), timeout=20)
    assert r.returncode == 0
    assert "GOT:" not in tmux.screen(pane)
    assert "dry-run: would send" in (Path(env["CLAUDE_RESUME_STATE"]) / "log").read_text()


def test_hook_outside_tmux_does_nothing(env):
    r = run(["schedule", "--settle", "0", "--payload", json.dumps({"error": "rate_limit"})], env=env)
    assert r.returncode == 0


def pane_process(tmux, pane):
    return int(tmux.run("display-message", "-p", "-t", pane, "#{pane_pid}").stdout.strip())


@pytestmark_tmux
def test_waiter_sends_with_live_claude_pid_even_without_footer(env, tmux, tmp_path):
    pane, pid = tmux.start(LIMIT_MSG)  # no footer line on screen
    assert wait_for(lambda: "session limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 2)
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 2)
    payload = json.dumps({"session_id": "sess1", "transcript_path": str(transcript),
                          "error": "rate_limit", "claude_pid": pane_process(tmux, pane)})
    r = run(["schedule", "--settle", "0.2", "--buffer", "0", "--payload", payload],
            env=tmux_env(env, tmux, pane, pid), timeout=20)
    assert r.returncode == 0
    assert wait_for(lambda: "GOT:continue" in tmux.screen(pane)), tmux.screen(pane)


@pytestmark_tmux
def test_waiter_skips_when_claude_is_gone_from_pane(env, tmux, tmp_path):
    pane, pid = tmux.start(PANE_CMD)  # footer is on screen, but the recorded Claude pid is dead
    assert wait_for(lambda: "session limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 2)
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 2)
    payload = json.dumps({"session_id": "sess1", "transcript_path": str(transcript),
                          "error": "rate_limit", "claude_pid": 999999})
    r = run(["schedule", "--settle", "0.2", "--buffer", "0", "--payload", payload],
            env=tmux_env(env, tmux, pane, pid), timeout=20)
    assert r.returncode == 0
    assert "GOT:" not in tmux.screen(pane)
    assert "no longer running" in (Path(env["CLAUDE_RESUME_STATE"]) / "log").read_text()


@pytestmark_tmux
def test_waiter_skips_when_superseded_by_newer_waiter(env, tmux, tmp_path):
    pane, pid = tmux.start(PANE_CMD)
    assert wait_for(lambda: "session limit" in tmux.screen(pane))
    write_session_state(env, time.time() + 3)
    payload = json.dumps({"session_id": "sess1", "error": "rate_limit", "claude_pid": pane_process(tmux, pane)})
    proc = subprocess.Popen([sys.executable, str(SCRIPT), "schedule", "--settle", "0.2", "--buffer", "0",
                             "--payload", payload], env=tmux_env(env, tmux, pane, pid))
    time.sleep(1.0)
    waiter = Path(env["CLAUDE_RESUME_STATE"]) / "waiters" / f"{pane.replace('%', '_')}.json"
    waiter.write_text(json.dumps({"pid": 1, "wake": 0}))  # another waiter took over
    assert proc.wait(timeout=20) == 0
    assert "GOT:" not in tmux.screen(pane)
    assert "newer waiter" in (Path(env["CLAUDE_RESUME_STATE"]) / "log").read_text()


@pytestmark_tmux
def test_send_types_text_into_pane_regardless_of_state(env, tmux):
    pane, pid = tmux.start("just a normal screen, no usage limit")
    assert wait_for(lambda: "normal screen" in tmux.screen(pane))
    r = run(["send", "--pane", pane, "hello there"], env=tmux_env(env, tmux, pane, pid))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert wait_for(lambda: "GOT:hello there" in tmux.screen(pane)), tmux.screen(pane)


@pytestmark_tmux
def test_send_to_missing_pane_exits_2(env, tmux):
    pane, pid = tmux.start("x")
    r = run(["send", "--pane", "%999", "hi"], env=tmux_env(env, tmux, pane, pid))
    assert r.returncode == 2
    assert "not found" in r.stderr
