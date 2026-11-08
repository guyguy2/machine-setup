"""Tests for pi-checkup's pure helper functions, run against fixtures (no live system state).

pi-checkup is bash: each test sources it (sourcing defines the functions and skips main) and calls one helper.
Run: uvx pytest ~/dev/machine-setup/raspberry-pi/checkup/tests
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "pi-checkup"


def sh(code: str, *args: str, stdin: str = "") -> str:
    """Source pi-checkup in bash, run `code` with positional args, return stdout."""
    out = subprocess.run(
        ["bash", "-c", f'source "$0"; {code}', str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True, check=True,
    )
    return out.stdout


def test_sourcing_runs_no_checks():
    assert sh("echo sourced") == "sourced\n"


# ---------- R-084: unpinned compose images ----------

def test_unpinned_images(tmp_path: Path):
    f = tmp_path / "docker-compose.yml"
    f.write_text(
        "services:\n"
        "  a:\n    image: pihole/pihole:latest\n"
        "  b:\n    image: \"nginx\"\n"
        "  c:\n    image: pihole/pihole:2026.10.1  # pinned\n"
        "  d:\n    image: localhost:5000/tool\n"
        "  e:\n    image: alpine@sha256:0123abcd\n"
        "  f:\n    image: 'caddy:2.10'\n"
    )
    assert sh('unpinned_images "$1"', str(f)).split() == ["pihole/pihole:latest", "nginx", "localhost:5000/tool"]


def test_repo_compose_files_are_pinned():
    for f in (SCRIPT.parent.parent / "services").glob("*/docker-compose.y*ml"):
        assert sh('unpinned_images "$1"', str(f)) == "", f


# ---------- R-041: links restore.sh would make ----------

def test_links_drift():
    home = sh('printf %s "$HOME"')
    dry_run = (
        "Role: main (default)\n"
        f"  {home}/dev/scripts already linked\n"
        f"  [dry-run] ln -s /x/backup/pi-backup {home}/.local/bin/pi-backup\n"
        f"  linked {home}/.local/bin/pi-backup -> /x/backup/pi-backup\n"
        f"  {home}/dev/pihole exists and is not this repo's services/pihole/; leaving it\n"
    )
    assert sh("links_drift", stdin=dry_run).splitlines() == [
        "~/.local/bin/pi-backup is missing",
        "~/dev/pihole exists but isn't the repo's link",
    ]


def test_links_drift_clean():
    assert sh("links_drift", stdin="  /home/x/dev/scripts already linked\n") == ""
