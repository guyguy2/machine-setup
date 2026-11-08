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


# ---------- R-029: exposure (TCP + UDP, global IPv6, the host firewall table) ----------

SS = (
    'tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1,fd=3))\n'
    'tcp LISTEN 0 128 [::]:8090 [::]:* users:(("caddy",pid=2,fd=4))\n'
    'tcp LISTEN 0 128 127.0.0.1:8080 0.0.0.0:*\n'
    'udp UNCONN 0 0 *:8091 *:* users:(("caddy",pid=2,fd=6))\n'
    'udp UNCONN 0 0 [fe80::1%eth0]:546 [::]:* users:(("NetworkManager",pid=3,fd=28))\n'
    'tcp LISTEN 0 128 [2001:db8::5]:9000 [::]:*\n'
    'tcp LISTEN 0 128 100.64.0.1:9001 0.0.0.0:*\n'
)


def test_parse_listeners_tcp_and_udp():
    assert sh("parse_listeners", stdin=SS).splitlines() == [
        "tcp 0.0.0.0 22 sshd pid 1",
        "tcp :: 8090 caddy pid 2",
        "tcp 127.0.0.1 8080 -",
        "udp * 8091 caddy pid 2",
        "udp fe80::1 546 NetworkManager pid 3",
        "tcp 2001:db8::5 9000 -",
        "tcp 100.64.0.1 9001 -",
    ]


def test_listener_scope():
    addrs = ["127.0.0.1", "::1", "100.64.0.1", "fd7a:115c::1", "0.0.0.0", "192.0.2.5", "*", "::",
             "2001:db8::5", "fe80::1", "fd00::1"]
    assert sh('for a in "$@"; do listener_scope "$a"; done', *addrs).split() == [
        "local", "local", "tailnet", "tailnet", "v4", "v4", "v6", "v6", "v6", "lan6", "lan6",
    ]


def test_host_firewall_needs_input_drop_in_its_table():
    drop = "table inet host {\n\tchain input {\n\t\ttype filter hook input priority filter + 10; policy drop;\n\t}\n}\n"
    accept = drop.replace("policy drop", "policy accept")
    fwd_only = drop.replace("hook input", "hook forward")
    for text, want in ((drop, "yes"), (accept, "no"), (fwd_only, "no"), ("", "no")):
        assert sh("host_firewall_drops && echo yes || echo no", stdin=text) == want + "\n", text


# ---------- R-008: root units running code a non-root user can change ----------

SYSTEMCTL_SHOW = (
    "ExecStart={ path=/usr/sbin/cron ; argv[]=/usr/sbin/cron -f $EXTRA_OPTS ; ignore_errors=no ; pid=0 }\n"
    "User=\nId=cron.service\n\n"
    "ExecStartPre={ path=/bin/bash ; argv[]=/bin/bash /srv/x/renew.sh --quiet ; ignore_errors=no }\n"
    "ExecStart={ path=/usr/bin/env ; argv[]=/usr/bin/env \"/opt/tool/run\" ; ignore_errors=no }\n"
    "User=root\nId=cert.service\n\n"
    "ExecStart={ path=/home/u/bin/app ; argv[]=/home/u/bin/app ; ignore_errors=no }\n"
    "User=u\nId=userish.service\n"
)


def test_root_exec_paths():
    assert sh("root_exec_paths", stdin=SYSTEMCTL_SHOW).splitlines() == [
        "cron.service /usr/sbin/cron",
        "cert.service /bin/bash", "cert.service /srv/x/renew.sh",
        "cert.service /usr/bin/env", "cert.service /opt/tool/run",
    ]


def test_nonroot_writable(tmp_path: Path):
    script = tmp_path / "renew.sh"
    script.write_text("#!/bin/sh\n")
    out = sh('nonroot_writable "$1"', str(script))
    assert out.startswith(str(script)) and "owned by" in out          # the user's own file
    assert sh("nonroot_writable /usr/bin/env") == ""                    # root's, in root's directories
    link = tmp_path / "env-link"
    link.symlink_to("/usr/bin/env")
    assert "owned by" in sh('nonroot_writable "$1"', str(link))         # a link the user can replace


def test_script_exec_paths(tmp_path: Path):
    script = tmp_path / "s.sh"
    script.write_text('#!/bin/bash\n/usr/bin/env true\ncp "$a" /etc/hostname\nx=$HOME/y\n')
    # the interpreter and the programs it runs; not data files or $HOME paths
    assert sh('script_exec_paths "$1"', str(script)).split() == ["/bin/bash", "/usr/bin/env"]
    assert sh("script_exec_paths /usr/bin/env") == ""                   # a binary isn't scanned


# ---------- R-087: venvs bound to a Homebrew Python ----------

def test_venvs_on_brew_python(tmp_path: Path):
    for proj, home in (("ok", "/usr/bin"), ("bad", "/home/linuxbrew/.linuxbrew/opt/python@3.14/bin")):
        (tmp_path / proj / ".venv").mkdir(parents=True)
        (tmp_path / proj / ".venv" / "pyvenv.cfg").write_text(f"home = {home}\nversion_info = 3.x\n")
    assert sh('venvs_on_brew_python "$1"', str(tmp_path)) == (
        f"{tmp_path}/bad/.venv (/home/linuxbrew/.linuxbrew/opt/python@3.14/bin)\n"
    )


# ---------- drift.backup: what save.sh covers ----------

def test_save_sh_lists_covers_units():
    listed = sh('save_sh_lists "$1"', str(SCRIPT.parent.parent / "save.sh"))
    assert ".config/systemd/user/hermes-gateway.service" in listed
    assert ".config/systemd/user/rei.service.d" in listed  # regenerated by the rei step, not snapshotted
    assert "say()" not in listed  # stops at the closing paren


# ---------- R-039: Pi-hole settings outside compose, local DNS record ----------

PIHOLE_TOML = """\
[dns]
  # hosts = [ "commented out" ] ### CHANGED
  upstreams = [
    "8.8.8.8",
    "8.8.4.4"
  ] ### CHANGED (env), default = []
  hosts = [
    "192.0.2.10 pi.example.ts.net",
    "192.0.2.11 other.lan"
  ] ### CHANGED, default = []
  listeningMode = "ALL" ### CHANGED (env), default = "LOCAL"
  [dns.rateLimit]
    count = 5000 ### CHANGED (env), default = 1000
[dhcp]
  hosts = [ "should not be read" ]
[webserver]
  [webserver.api]
    pwhash = "$x$y" ### CHANGED, default = ""
[files]
  macvendor = "/macvendor.db" ### CHANGED, default = "/etc/pihole/macvendor.db"
"""


def test_pihole_ui_keys():
    assert sh("pihole_ui_keys", stdin=PIHOLE_TOML).split() == ["dns.hosts", "webserver.api.pwhash", "files.macvendor"]


def test_pihole_dns_hosts():
    assert sh("pihole_dns_hosts", stdin=PIHOLE_TOML).splitlines() == ["192.0.2.10 pi.example.ts.net", "192.0.2.11 other.lan"]


def test_pihole_dns_hosts_empty():
    assert sh("pihole_dns_hosts", stdin="[dns]\n  hosts = []\n[dhcp]\n  hosts = [ \"x\" ]\n") == ""


# ---------- R-024: credential expiry ----------

NOW = "1762560000"  # 2025-11-08T00:00:00Z


def test_days_until():
    assert sh('days_until "$1" "$2"', "2025-11-18T00:00:00Z", NOW) == "10\n"
    assert sh('days_until "$1" "$2"', "2025-11-06 00:00:00 UTC", NOW) == "-2\n"
    assert subprocess.run(["bash", "-c", 'source "$0"; days_until nonsense', str(SCRIPT)]).returncode == 1


def test_expiry_check():
    def check(date: str, days: int) -> str:
        return sh(f'days_until() {{ echo {days}; }}; expiry_check k.x "Thing" "$1" 14 "fix it"', date)
    assert "WARN" in check("2027-01-01T00:00:00Z", 3) and "expires in 3 day(s), on 2027-01-01 (fix it)" in check("2027-01-01T00:00:00Z", 3)
    assert "expired 2 day(s) ago" in check("2027-01-01", -2)
    assert "OK" in check("2027-10-19 05:00:00 UTC", 300) and "valid until 2027-10-19 (300 days)" in check("2027-10-19 05:00:00 UTC", 300)


def test_env_value(tmp_path: Path):
    f = tmp_path / ".env"
    f.write_text('# A=no\nA_KEY=abc123\nexport B="quoted value"\nC=\'single\'\nA=plain\n')
    assert sh('env_value "$1" A_KEY', str(f)) == "abc123\n"
    assert sh('env_value "$1" B', str(f)) == "quoted value\n"
    assert sh('env_value "$1" C', str(f)) == "single\n"
    assert sh('env_value "$1" A', str(f)) == "plain\n"
    assert sh('env_value "$1" MISSING', str(f)) == ""
