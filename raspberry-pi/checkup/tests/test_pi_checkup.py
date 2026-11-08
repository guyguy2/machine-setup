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


# ---------- R-036: tailnet routes map to agents by the ports their units serve ----------

SERVE_STATUS = """{"TCP": {}, "Web": {
  "pi.example.ts.net:443":  {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8080"}}},
  "pi.example.ts.net:8443": {"Handlers": {"/hermes": {"Proxy": "http://127.0.0.1:9120/hermes"}}},
  "pi.example.ts.net:8444": {"Handlers": {"/openclaw": {"Proxy": "http://127.0.0.1:18789/openclaw"}}},
  "pi.example.ts.net:8445": {"Handlers": {"/pihole": {"Proxy": "http://127.0.0.1:8081"}}}
}}"""

UNITS = {
    "hermes-dashboard.service": (
        "[Unit]\nDescription=Hermes web dashboard on 127.0.0.1:9119 (HTTPS via hermes-proxy.service)\n"
        "[Service]\nExecStart=%h/.local/bin/hermes dashboard --no-open\n"
    ),
    "hermes-proxy.service": (
        "[Unit]\nDescription=Caddy: serves the Hermes dashboard under /hermes; HTTPS via "
        "`tailscale serve --bg --https=8443 --set-path /hermes`\n"
        "[Service]\nExecStart=/usr/bin/caddy run --config %h/Caddyfile --adapter caddyfile\n"
    ),
    "openclaw-gateway.service": (
        "[Unit]\nDescription=OpenClaw Gateway + Control UI on 127.0.0.1:18789\n"
        "[Service]\nExecStart=%h/openclaw gateway run\n"
    ),
}
CADDYFILE = "{\n\tadmin off\n}\nhttp://:9120 {\n\tbind 127.0.0.1\n\treverse_proxy 127.0.0.1:9119\n}\n"


def fake_units(tmp_path: Path) -> str:
    """bash that makes `systemctl --user cat <unit>` read fixtures and %h point at tmp_path."""
    for name, text in UNITS.items():
        (tmp_path / name).write_text(text)
    (tmp_path / "Caddyfile").write_text(CADDYFILE)
    return f'HOME={tmp_path}; systemctl() {{ cat "$HOME/$3" 2>/dev/null; }}; '


def test_agent_ports_from_units(tmp_path: Path):
    out = sh(fake_units(tmp_path) + 'agent_ports; for a in Hermes OpenClaw; do echo "$a=${AGENT_PORTS[$a]}"; done')
    # the dashboard's own port first (agents check), then the Caddy proxy's 9120 that tailscale serve points at
    assert out.splitlines() == ["Hermes=9119 9120", "OpenClaw=18789"]


def test_route_block_maps_hermes_route_to_hermes(tmp_path: Path):
    """Regression: the /hermes route goes to 9120 (hermes-proxy), not the dashboard's 9119, and was a false WARN."""
    code = fake_units(tmp_path) + (
        'agent_ports; serve_routes | while read -r host path proxy; do echo "${host##*:}$path=$(route_agent "$proxy")"; done'
    )
    assert sh(code, stdin=SERVE_STATUS).splitlines() == [
        "443/=", "8443/hermes=Hermes", "8444/openclaw=OpenClaw", "8445/pihole=",
    ]


def test_unit_ports_ignores_tailnet_ports():
    assert sh("unit_ports", stdin="tailscale serve --https=8443 http://127.0.0.1:9120/hermes --port 7000\n").split() == [
        "9120", "7000",
    ]


def test_main_only():
    assert sh('for u in rei.service mail-sync.timer hermes-gateway.service pi-status.service; do '
              'main_only "$u" && echo "$u"; done; true') == "rei.service\nmail-sync.timer\nhermes-gateway.service\n"


# ---------- R-036: health.unclean-shutdown ----------

def test_shutdown_was_clean():
    clean = "Stopped target\nSyncing filesystems and block devices.\nJournal stopped\n"
    cut = "Finished vault-index.service\nmagicsock: disco: node now using 192.0.2.1\n"
    assert sh('shutdown_was_clean && echo clean || echo unclean', stdin=clean) == "clean\n"
    assert sh('shutdown_was_clean && echo clean || echo unclean', stdin=cut) == "unclean\n"
