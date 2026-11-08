"""Tests for pi-alert's helpers and its alert logic, with nothing sent (PI_ALERT_DRY=1, state in a temp dir).

pi-alert is bash: each test sources it (sourcing defines the functions and skips main) and runs a snippet.
Run: uvx pytest ~/dev/machine-setup/raspberry-pi/alert/tests
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "pi-alert"


@pytest.fixture
def sh(tmp_path):
    env = {**os.environ, "PI_ALERT_DRY": "1", "PI_ALERT_STATE": str(tmp_path / "state"),
           "PI_ALERT_ENV": str(tmp_path / "no.env"), "PI_ALERT_CONFIRM_SECS": "0"}

    def run(code: str, *args: str, stdin: str = "") -> str:
        out = subprocess.run(["bash", "-c", f'source "$0"; {code}', str(SCRIPT), *args],
                             input=stdin, capture_output=True, text=True, env=env)
        return out.stdout

    return run


def test_sourcing_sends_nothing(sh):
    assert sh("echo sourced") == "sourced\n"


def test_backoff_then_reset(sh):
    # first alert, held within the hour, again after 1 h, then 4 h, then 24 h; 48 h of quiet starts over
    steps = [0, 100, 3600, 3700, 3600 + 14400, 3600 + 14400 + 86399, 3600 + 14400 + 86400,
             3600 + 14400 + 86400 + 172801]
    code = "; ".join(f"rate_check k {1_000_000 + t}" for t in steps)
    assert sh(code).split("\n")[:-1] == ["send 0", "hold", "send 1", "hold", "send 1", "hold", "send 1", "send 0"]


def test_keyname_is_file_safe(sh):
    assert sh('keyname "unit-user-a b/c@x.service"').strip() == "unit-user-a_b_c@x.service"


def test_chat_id_from_home_channel_or_single_allowed_user(sh, tmp_path):
    env = tmp_path / "no.env"
    env.write_text("TELEGRAM_ALLOWED_USERS=111\n")
    assert sh("chat_id") == "111\n"
    env.write_text("TELEGRAM_ALLOWED_USERS=111,222\n")
    assert sh("chat_id") == ""  # whose would it be?
    env.write_text("TELEGRAM_ALLOWED_USERS=111,222\nTELEGRAM_HOME_CHANNEL='333'\n")
    assert sh("chat_id") == "333\n"


def test_warn_lines_and_new_warnings(sh, tmp_path):
    out = ("== health\n  \x1b[33mWARN\x1b[0m  disk 91% full [health.disk]\n  OK    fine\n"
           "  WARN  rei.service failed 4 times in 24h [services.flapping]\n\nWARNINGS health=2\n")
    lines = sh("warn_lines", stdin=out)
    assert lines == "disk 91% full [health.disk]\nrei.service failed 4 times in 24h [services.flapping]\n"
    prev = tmp_path / "prev"
    prev.write_text(sh("normalize", stdin="disk 85% full [health.disk]\n"))
    # the same warning with other numbers isn't new; the other one is
    assert sh('new_warnings "$1"', str(prev), stdin=lines) == "rei.service failed 4 times in 24h [services.flapping]\n"
    assert sh('new_warnings "$1"', str(tmp_path / "missing"), stdin=lines) == lines


def test_ignored_units(sh):
    assert sh("ignored xdg-desktop-portal-gtk.service && echo y || echo n") == "y\n"
    assert sh("ignored pi-alert@rei.service.service && echo y || echo n") == "y\n"
    assert sh("ignored rei.service && echo y || echo n") == "n\n"


def test_send_keyed_counts_what_was_held_back(sh):
    out = sh('send_keyed k one; send_keyed k two; echo "$(date +%s) 1 0" > /dev/null')
    assert "one" in out and "two" not in out
    # pretend the hour has passed: the next one says how many were held back
    out = sh('read -r l n h < "$PI_ALERT_STATE/keys/k"; echo "$((l - 3600)) $n $h" > "$PI_ALERT_STATE/keys/k"; send_keyed k three')
    assert "three" in out and "(and 1 more since the last alert)" in out


def test_watch_alerts_once_then_says_ok_again(sh):
    bad = 'watch_checks() { echo "pihole-dns|Pi-hole doesn\'t answer DNS"; }; cmd_watch'
    good = "watch_checks() { :; }; cmd_watch"
    first = sh(bad)
    assert "Pi-hole doesn't answer DNS" in first
    assert sh(bad) == ""  # still broken: no repeat
    assert "OK again: Pi-hole doesn't answer DNS" in sh(good)
    assert sh(good) == ""


def test_watch_ignores_a_blip(sh):
    # broken on the first look, fine a minute later (upd recreating Pi-hole): nothing sent, nothing remembered
    # (watch_checks runs in a subshell, so it counts its calls in a file)
    code = ('c="$PI_ALERT_STATE/calls"; mkdir -p "$PI_ALERT_STATE"; '
            'watch_checks() { echo x >> "$c"; [[ $(wc -l < "$c") == 1 ]] && echo "docker|docker.service is inactive"; }; '
            'cmd_watch; ls "$PI_ALERT_STATE/watch"')
    assert sh(code) == ""


def test_unit_message(sh):
    out = sh("systemctl() { echo exit-code; }; journalctl() { printf 'line one\\nline two\\n'; }; cmd_unit rei.service")
    assert "rei.service failed (user unit, exit-code)" in out
    assert "line two" in out and "journalctl --user -u rei.service" in out
    out = sh("systemctl() { echo timeout; }; journalctl() { :; }; cmd_unit --system docker.service")
    assert "docker.service failed (system unit, timeout)" in out and "journalctl -u docker.service" in out
    assert sh("cmd_unit xdg-desktop-portal-gtk.service") == ""


def test_long_messages_are_cut_to_telegrams_limit(sh):
    out = sh('deliver "$(printf "x%.0s" $(seq 5000))"')
    assert out.count("x") == 4000


def test_no_token_means_not_sent_and_not_queued(tmp_path):
    env = {**os.environ, "PI_ALERT_STATE": str(tmp_path / "s"), "PI_ALERT_ENV": str(tmp_path / "none.env")}
    r = subprocess.run([str(SCRIPT), "hello"], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "no Telegram bot token" in r.stderr
    assert not list((tmp_path / "s" / "unsent").glob("*.txt"))
