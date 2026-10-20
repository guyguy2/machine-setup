"""Data collectors for the status page (stdlib only; reads /proc, shells out sparingly)."""

import json
import os
import platform
import pwd
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLK_TCK = os.sysconf("SC_CLK_TCK")
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
HOME = os.path.expanduser("~")


def read(path: str) -> str:
    with open(path) as f:
        return f.read()


def run(*cmd: str, timeout: int = 3) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------- overview ----------

def cpu_times() -> tuple[int, int]:
    fields = [int(x) for x in read("/proc/stat").splitlines()[0].split()[1:]]
    return sum(fields), fields[3] + fields[4]  # total, idle + iowait


def cpu_percent() -> float:
    t1, i1 = cpu_times()
    time.sleep(0.2)
    t2, i2 = cpu_times()
    return round(100 * (1 - (i2 - i1) / max(t2 - t1, 1)), 1)


def meminfo() -> dict[str, int]:
    info = {}
    for line in read("/proc/meminfo").splitlines():
        key, value = line.split(":")
        info[key] = int(value.split()[0]) * 1024
    return info


THROTTLE_BITS = {
    0: "under-voltage now",
    1: "frequency capped now",
    2: "throttled now",
    3: "soft temp limit now",
    16: "under-voltage occurred",
    17: "frequency cap occurred",
    18: "throttling occurred",
    19: "soft temp limit occurred",
}


def throttled() -> list[str]:
    out = run("vcgencmd", "get_throttled")  # throttled=0x0
    try:
        value = int(out.split("=")[1], 16)
    except (IndexError, ValueError):
        return []
    return [msg for bit, msg in THROTTLE_BITS.items() if value >> bit & 1]


def status() -> dict:
    mem = meminfo()
    disk = shutil.disk_usage("/")
    model = read("/proc/device-tree/model").strip("\x00\n") if os.path.exists("/proc/device-tree/model") else platform.machine()
    route = default_route()
    return {
        "hostname": platform.node(),
        "model": model,
        "os": run("sh", "-c", ". /etc/os-release && echo $PRETTY_NAME"),
        "kernel": platform.release(),
        "uptime_s": int(float(read("/proc/uptime").split()[0])),
        "load": [round(x, 2) for x in os.getloadavg()],
        "cpus": os.cpu_count(),
        "cpu_percent": cpu_percent(),
        "temp_c": round(int(read("/sys/class/thermal/thermal_zone0/temp")) / 1000, 1),
        "mem_total": mem["MemTotal"],
        "mem_used": mem["MemTotal"] - mem["MemAvailable"],
        "disk_total": disk.total,
        "disk_used": disk.used,
        "throttled": throttled(),
        "tailscale_ip": run("tailscale", "ip", "-4"),
        "local_ip": route.get("prefsrc", ""),
        "gateway": route.get("gateway", ""),
        "connection": connection_label(route.get("dev", "")),
        "time": int(time.time()),
    }


# ---------- processes ----------

SECRET_FLAG = re.compile(r"(?i)(--?[\w-]*(?:key|token|secret|passw(?:or)?d|auth)[\w-]*)([= ])(\S+)")
SECRET_ENV = re.compile(r"(?i)\b(\w*(?:key|token|secret|passw(?:or)?d)\w*)=(\S+)")
SECRET_VALUE = re.compile(r"\b(sk-[\w-]{10,}|gh[pousr]_\w{20,}|xox[abp]-[\w-]{10,}|AIza[\w-]{20,}|eyJ[\w-]{20,}\.[\w-]+)")


def redact(cmd: str) -> str:
    """Command lines can carry credentials; mask the usual shapes before they reach the page."""
    cmd = SECRET_FLAG.sub(r"\1\2•••", cmd)
    cmd = SECRET_ENV.sub(r"\1=•••", cmd)
    return SECRET_VALUE.sub("•••", cmd)


_users: dict[int, str] = {}


def username(uid: int) -> str:
    if uid not in _users:
        try:
            _users[uid] = pwd.getpwuid(uid).pw_name
        except KeyError:
            _users[uid] = str(uid)
    return _users[uid]


def sample() -> dict[int, dict]:
    """One pass over /proc. Kernel threads (empty cmdline) are skipped."""
    procs = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            # comm may contain spaces or parens, so split at the last ')'
            head, _, rest = read(f"/proc/{pid}/stat").rpartition(")")
            f = rest.split()  # f[0] is field 3 (state)
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                argv = [a.decode(errors="replace") for a in fh.read().split(b"\0") if a]
            if not argv:
                continue
            procs[pid] = {
                "pid": pid,
                "ticks": int(f[11]) + int(f[12]),  # utime + stime
                "start": int(f[19]) / CLK_TCK,
                "rss": int(f[21]) * PAGE_SIZE,
                "user": username(os.stat(f"/proc/{pid}").st_uid),
                "argv": argv,
            }
        except (OSError, ValueError, IndexError):
            continue
    return procs


def scan() -> list[dict]:
    """All processes with CPU% (of one core) measured over a short interval."""
    first = sample()
    t0 = time.monotonic()
    time.sleep(0.3)
    second = sample()
    dt = time.monotonic() - t0
    up = float(read("/proc/uptime").split()[0])
    for pid, p in second.items():
        prev = first.get(pid)
        same = prev is not None and prev["start"] == p["start"]
        p["cpu"] = round((p["ticks"] - prev["ticks"]) / CLK_TCK / dt * 100, 1) if same else 0.0
        p["age_s"] = int(up - p["start"])
    return list(second.values())


def public(p: dict) -> dict:
    return {
        "pid": p["pid"],
        "user": p["user"],
        "cpu": p["cpu"],
        "rss": p["rss"],
        "age_s": p["age_s"],
        "cmd": redact(" ".join(p["argv"]))[:300],
    }


def top_processes() -> dict:
    procs = scan()
    by_cpu = sorted(procs, key=lambda p: p["cpu"], reverse=True)[:25]
    by_mem = sorted(procs, key=lambda p: p["rss"], reverse=True)[:25]
    chosen = {p["pid"]: p for p in by_cpu + by_mem}
    return {"total": len(procs), "processes": [public(p) for p in chosen.values()]}


# ---------- agents ----------

# `match` is compared (prefix) with the executable name and, for interpreters, the script's name and folders.
AGENTS = [
    {"name": "Claude Code", "kind": "Coding agent", "match": ("claude",)},
    {"name": "OpenHuman", "kind": "Personal assistant", "match": ("openhuman", "open-human"), "unit": "openhuman.service"},
    {"name": "Hermes", "kind": "Agent", "match": ("hermes",), "unit": "hermes-dashboard.service"},
    {"name": "OpenClaw", "kind": "Personal assistant", "match": ("openclaw",), "unit": "openclaw-gateway.service"},
    # not installed here; listed only while running
    {"name": "Codex", "kind": "Coding agent", "match": ("codex",), "optional": True},
    {"name": "Gemini CLI", "kind": "Coding agent", "match": ("gemini",), "optional": True},
    {"name": "Ollama", "kind": "Local models", "match": ("ollama",), "optional": True},
]

INTERPRETER = re.compile(r"^(node|nodejs|bun|deno|python[\d.]*)$")


def exe_names(argv: list[str]) -> set[str]:
    base = os.path.basename(argv[0])
    names = {base}
    if INTERPRETER.match(base) and len(argv) > 1:
        args = argv[1:]
        target = args[args.index("-m") + 1] if "-m" in args[:-1] else next((a for a in args if not a.startswith("-")), "")
        parts = [c for c in target.split("/") if c]
        # Folder names identify a package (node_modules/openclaw/...), but scratch scripts under /tmp
        # (Claude's own is /tmp/claude-<uid>/) must not be mistaken for the agent they run beside.
        names.update(parts[-1:] if target.startswith(("/tmp/", "/var/tmp/")) else parts)
    return names


def agents() -> list[dict]:
    procs = scan()
    listening = ports()
    result = []
    for spec in AGENTS:
        found = [p for p in procs if any(n.startswith(spec["match"]) for n in exe_names(p["argv"]))]
        if spec.get("optional") and not found:
            continue
        instances = []
        for p in sorted(found, key=lambda p: p["rss"], reverse=True):
            try:
                cwd = os.readlink(f"/proc/{p['pid']}/cwd")
            except OSError:
                cwd = ""
            instances.append({
                **public(p),
                "cwd": "~" + cwd[len(HOME):] if cwd.startswith(HOME) else cwd,
                "ports": [f"{x['address']}:{x['port']}" for x in listening if x["pid"] == p["pid"]],
            })
        entry = {"name": spec["name"], "kind": spec["kind"], "instances": instances}
        if "unit" in spec:
            entry["unit"] = spec["unit"]
            entry["unit_state"] = run("systemctl", "--user", "is-active", spec["unit"]) or "unknown"
        result.append(entry)
    return result


AGENT_UNITS = {spec["unit"] for spec in AGENTS if "unit" in spec}  # the only units the page may start or stop


def control_agent(unit: str, action: str) -> tuple[int, dict]:
    """Start or stop an agent's user service from the page. A stop is systemd's graceful one: SIGTERM, then up to
    the unit's TimeoutStopSec to clean up before SIGKILL (90s by default; OpenClaw's unit allows 330s to drain
    active turns). This waits for it, however long it takes."""
    if unit not in AGENT_UNITS or action not in ("start", "stop"):
        return 404, {"error": f"not an agent service: {unit}"}
    try:
        done = subprocess.run(["systemctl", "--user", action, unit], capture_output=True, text=True, timeout=360)
    except subprocess.TimeoutExpired:
        return 504, {"error": f"{unit} is still stopping; check again in a moment"}
    state = run("systemctl", "--user", "is-active", unit) or "unknown"
    if done.returncode:
        return 500, {"error": done.stderr.strip() or f"systemctl {action} failed", "state": state}
    return 200, {"unit": unit, "state": state}


# ---------- agent lab ----------
# ~/dev/agent-lab compares agents on the same use cases (see its README). Use cases and run notes are markdown
# files with "key: value" front matter; they stay the one source of truth, so this only ever reads them.

LAB = Path(HOME) / "dev" / "agent-lab"
LAB_AGENTS = [("openclaw", "OpenClaw"), ("hermes", "Hermes"), ("openhuman", "OpenHuman")]  # (id in notes, AGENTS name)
LAB_NUMBERS = ("score_outcome", "score_quality", "score_autonomy", "score_safety", "score_ux", "score_happiness",
               "overall", "duration_min", "my_effort_min", "followups", "peak_rss_mb", "avg_cpu_pct")
NOTE_LIMIT = 50_000  # characters of a run note's body sent to the page


def front_matter(text: str) -> tuple[dict, str]:
    """Split a note into its front matter (trailing "# comments" dropped) and its body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta = {}
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:]).strip()
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = re.sub(r"(^|\s+)#.*$", "", value).strip()
    return {}, text  # no closing ---: treat it all as body


def number(value: str | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def lab_prompt(body: str) -> str:
    m = re.search(r"^## Prompt.*?\n```[^\n]*\n(.*?)\n```", body, re.S | re.M)
    return m[1] if m else ""


def lab_impressions(results: Path) -> dict[str, str]:
    """My running opinion per agent: the "### <Agent>" parts of results.md's "Overall impressions"."""
    try:
        text = results.read_text(errors="replace")
    except OSError:
        return {}
    section = re.search(r"^## Overall impressions\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    found = {}
    for name, body in re.findall(r"^### ([^\n]+)\n(.*?)(?=^### |\Z)", section[1] if section else "", re.S | re.M):
        lines = [l for l in body.strip().splitlines() if l.strip() not in ("-", "*")]  # skip the template's empty bullets
        agent = next((a for a, n in LAB_AGENTS if n.lower() == name.strip().lower()), None)
        if agent and lines:
            found[agent] = "\n".join(lines)
    return found


def lab() -> dict:
    path = "~" + str(LAB)[len(HOME):] if str(LAB).startswith(HOME) else str(LAB)
    if not LAB.is_dir():
        return {"found": False, "path": path}
    procs = list(sample().values())
    match = {a["name"]: a["match"] for a in AGENTS}
    running = {name for name in match if any(n.startswith(match[name]) for p in procs for n in exe_names(p["argv"]))}

    use_cases = []
    for f in sorted((LAB / "use-cases").glob("UC-*.md")):
        meta, body = front_matter(f.read_text(errors="replace"))
        use_cases.append({"id": meta.get("id") or f.stem[:6], "title": meta.get("title", f.stem), "file": f.name,
                          "category": meta.get("category", ""), "risk": meta.get("risk", ""), "prompt": lab_prompt(body)})

    runs = []
    for f in (LAB / "runs").glob("*.md"):
        meta, body = front_matter(f.read_text(errors="replace"))
        runs.append({
            "file": f.name,
            **{k: meta.get(k, "") for k in ("use_case", "agent", "date", "version", "model", "interface", "outcome")},
            **{k: number(meta.get(k)) for k in LAB_NUMBERS},
            "note": body[:NOTE_LIMIT],
        })
    runs.sort(key=lambda r: (r["date"], r["file"]))  # oldest first, so the last one per cell is the latest

    return {
        "found": True,
        "path": path,
        "agents": [{"id": a, "name": n, "running": n in running} for a, n in LAB_AGENTS],
        "use_cases": use_cases,
        "runs": runs,
        "impressions": lab_impressions(LAB / "results.md"),
    }


# ---------- docker ----------

def docker() -> dict:
    exe = shutil.which("docker")
    if not exe:
        return {"installed": False, "containers": []}
    try:
        r = subprocess.run([exe, "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError) as e:
        return {"installed": True, "error": str(e), "containers": []}
    if r.returncode:
        return {"installed": True, "error": r.stderr.strip()[:300], "containers": []}
    rows = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
    return {
        "installed": True,
        "containers": [
            {"name": c["Names"], "image": c["Image"], "state": c["State"], "status": c["Status"], "ports": c["Ports"]}
            for c in rows
        ],
    }


# ---------- services ----------

def services() -> dict:
    def listing(*scope: str) -> list[dict]:
        out = run("systemctl", *scope, "list-units", "--type=service", "--all", "--no-legend", "--plain", "--no-pager")
        rows = []
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit, _load, active, sub = parts[:4]
            if sub == "running" or active == "failed":
                rows.append({"unit": unit, "active": active, "sub": sub, "description": parts[4] if len(parts) > 4 else ""})
        return sorted(rows, key=lambda r: (r["active"] != "failed", r["unit"]))

    return {"system": listing(), "user": listing("--user")}


# ---------- listening ports ----------

def exposure(address: str) -> str:
    if address in ("127.0.0.1", "::1"):
        return "local only"
    if address.startswith("100.") or address.startswith("fd7a:"):
        return "tailnet"
    if address in ("0.0.0.0", "*", "::"):
        return "all interfaces"
    return "network"


def ports() -> list[dict]:
    seen = {}
    for line in run("ss", "-ltnHp").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        address, _, port = fields[3].rpartition(":")
        address = address.split("%")[0].strip("[]")  # ss writes [addr]%iface
        proc = re.search(r'\("([^"]+)",pid=(\d+)', line)
        entry = {
            "port": int(port),
            "address": address,
            "exposure": exposure(address),
            "process": proc.group(1) if proc else "",
            "pid": int(proc.group(2)) if proc else 0,
        }
        seen[(entry["port"], entry["exposure"], entry["process"])] = entry  # collapses IPv4/IPv6 twins
    return sorted(seen.values(), key=lambda e: (e["port"], e["address"]))


# ---------- agent dashboards ----------
# The agents' own web UIs. Each listens on 127.0.0.1 only: `tailscale serve --bg --https=<tailnet_port> <port>`
# publishes one to the tailnet, and an SSH tunnel reaches it from anywhere SSH does. Without a port it's a placeholder.

DASHBOARDS = [
    {"name": "Hermes", "what": "Web dashboard: settings, API keys, sessions",
     "port": 9119, "tailnet_port": 8443, "start": "hermes dashboard --no-open"},
    {"name": "OpenClaw", "what": "Control UI: chat, sessions, channels, automations",
     "port": 18789, "tailnet_port": 8444, "start": "openclaw gateway run"},
    {"name": "OpenHuman", "what": "Desktop app and TUI only; no web dashboard yet"},
]


def dashboards() -> list[dict]:
    listening = {p["port"] for p in ports()}
    dns_name = tailscale_info().get("dns_name", "")
    try:
        web = json.loads(run("tailscale", "serve", "status", "--json") or "{}").get("Web", {})
    except ValueError:
        web = {}
    result = []
    for d in DASHBOARDS:
        entry = {"name": d["name"], "what": d["what"]}
        if port := d.get("port"):
            published = dns_name and f"{dns_name}:{d['tailnet_port']}" in web
            entry |= {
                "running": port in listening,
                "start": d["start"],
                "tailnet_url": f"https://{dns_name}:{d['tailnet_port']}/" if published else "",
                "publish": f"tailscale serve --bg --https={d['tailnet_port']} {port}",
                "tunnel": f"ssh -N -L {port}:localhost:{port} pi",
                "local_url": f"http://localhost:{port}/",
            }
        result.append(entry)
    return result


# ---------- network ----------

def default_route() -> dict:
    try:
        return json.loads(run("ip", "-j", "route", "show", "default") or "[]")[0]
    except (ValueError, IndexError):
        return {}


def wifi() -> dict:
    """The access point we're associated with (cached scan list, no new scan)."""
    out = run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,RATE,CHAN,SECURITY", "dev", "wifi", "list", "--rescan", "no")
    for line in out.splitlines():
        f = [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", line)]
        if len(f) >= 6 and f[0] == "*":
            return {"ssid": f[1], "signal": int(f[2] or 0), "rate": f[3], "channel": f[4], "security": f[5]}
    return {}


def connection_label(dev: str) -> str:
    if dev.startswith("wl") and (ap := wifi()):
        return f"Wi-Fi “{ap['ssid']}” ({ap['signal']}%)"
    return {"": "offline"}.get(dev, f"{dev} (wired)" if dev.startswith(("eth", "en")) else dev)


def tailscale_info() -> dict:
    try:
        data = json.loads(run("tailscale", "status", "--json") or "{}")
    except ValueError:
        return {}
    peers = []
    for p in data.get("Peer", {}).values():
        seen = p.get("LastSeen", "")
        peers.append({
            "name": p.get("HostName", ""),
            "ip": next((a for a in p.get("TailscaleIPs", []) if "." in a), ""),
            "os": p.get("OS", ""),
            "online": bool(p.get("Online")),
            "path": "direct" if p.get("CurAddr") else f"relay {p['Relay']}" if p.get("Relay") else "",
            "last_seen": "" if seen.startswith("0001") else seen,
            "exit_node": bool(p.get("ExitNode")),
        })
    peers.sort(key=lambda p: (not p["online"], p["name"]))
    me = data.get("Self", {})
    return {
        "dns_name": me.get("DNSName", "").rstrip("."),
        "ip": next((a for a in me.get("TailscaleIPs", []) if "." in a), ""),
        "online": bool(me.get("Online")),
        "peers": peers,
    }


def sessions() -> list[dict]:
    rows = []
    for line in run("who").splitlines():
        m = re.match(r"(\S+)\s+(.+?)\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?:\s+\((.*)\))?$", line)
        if not m or m[2].startswith("seat"):
            continue
        rows.append({"user": m[1], "tty": m[2], "since": m[3], "origin": m[4] or "local"})
    return rows


def ssh_help(user: str, host: str, ts: dict, local_ip: str) -> dict:
    """Ready-to-paste commands for reaching this machine, built from whatever is currently true."""
    ts_name, ts_ip = ts.get("dns_name", ""), ts.get("ip", "")
    commands = []
    if ts_name:
        commands.append({"label": "Over Tailscale (from anywhere)", "command": f"ssh {user}@{ts_name.split('.')[0]}"})
        commands.append({"label": "Over Tailscale, full name", "command": f"ssh {user}@{ts_name}"})
    if ts_ip:
        commands.append({"label": "Over Tailscale, by IP", "command": f"ssh {user}@{ts_ip}"})
    commands.append({"label": "Same Wi-Fi or LAN", "command": f"ssh {user}@{host}.local"})
    if local_ip:
        commands.append({"label": "Same Wi-Fi or LAN, by IP", "command": f"ssh {user}@{local_ip}"})
    alias = "pi"
    target = ts_name or ts_ip or local_ip or f"{host}.local"
    return {
        "commands": commands,
        "shortcut": {
            "alias": alias,
            "command": f"ssh {alias}",
            "config": f"Host {alias}\n    HostName {target}\n    User {user}",
        },
    }


def page_url(dns_name: str) -> str:
    """This page's HTTPS address, but only while `tailscale serve` actually publishes it under that name."""
    if not dns_name:
        return ""
    try:
        web = json.loads(run("tailscale", "serve", "status", "--json") or "{}").get("Web", {})
    except ValueError:
        return ""
    return f"https://{dns_name}/#overview" if f"{dns_name}:443" in web else ""


def network() -> dict:
    interfaces = []
    for i in json.loads(run("ip", "-j", "addr") or "[]"):
        if i["ifname"] == "lo":
            continue
        interfaces.append({
            "name": i["ifname"],
            "state": i.get("operstate", "").lower(),
            "mac": i.get("address", ""),
            "addresses": [f"{a['local']}/{a['prefixlen']}" for a in i.get("addr_info", []) if a.get("scope") != "link"],
        })
    route = default_route()
    ts = tailscale_info()
    return {
        "connection": connection_label(route.get("dev", "")),
        "page_url": page_url(ts.get("dns_name", "")),
        "ssh": ssh_help(username(os.getuid()), platform.node(), ts, route.get("prefsrc", "")),
        "wifi": wifi(),
        "local_ip": route.get("prefsrc", ""),
        "gateway": route.get("gateway", ""),
        "device": route.get("dev", ""),
        "dns": [l.split()[1] for l in read("/etc/resolv.conf").splitlines() if l.startswith("nameserver")],
        "interfaces": interfaces,
        "tailscale": ts,
        "sessions": sessions(),
    }


# ---------- sign-in status ----------
# Each check uses the CLI's own local status command: nothing logs in, refreshes a token, or prints a secret.
# Only whitelisted fields leave this module (account, project, scope count), never tokens or client ids.

AUTH_TTL = 60  # seconds; gcloud alone takes ~1s on a Pi


def json_out(*cmd: str):
    try:
        return json.loads(run(*cmd, timeout=20))
    except ValueError:
        return None


def check_gcloud() -> dict:
    accounts = json_out("gcloud", "auth", "list", "--format=json")
    active = next((a["account"] for a in accounts or [] if a.get("status") == "ACTIVE"), "")
    if not active:
        return {"state": "signed_out", "account": "", "detail": "run: gcloud auth login"}
    project = run("gcloud", "config", "get-value", "project", timeout=20)
    return {"state": "signed_in", "account": active, "detail": f"project {project}" if project else "no default project"}


def check_gws() -> dict:
    d = json_out("gws", "auth", "status")
    if not d or not d.get("user"):
        return {"state": "signed_out", "account": "", "detail": "run: gws auth login"}
    detail = f"project {d.get('project_id', '?')} · {d.get('scope_count', 0)} scopes · {d.get('storage', '?')} storage"
    return {"state": "signed_in" if d.get("token_valid") else "expired", "account": d["user"], "detail": detail}


def check_gh() -> dict:
    d = json_out("gh", "auth", "status", "--json", "hosts")
    accounts = [(host, a) for host, entries in (d or {}).get("hosts", {}).items() for a in entries if a.get("active")]
    if not accounts:
        return {"state": "signed_out", "account": "", "detail": "run: gh auth login"}
    host, a = accounts[0]
    return {"state": "signed_in" if a.get("state") == "success" else "expired", "account": a.get("login", ""),
            "detail": f"{host} · git over {a.get('gitProtocol', '?')}"}


def check_claude() -> dict:
    d = json_out("claude", "auth", "status")
    if not d or not d.get("loggedIn"):
        return {"state": "signed_out", "account": "", "detail": "run: claude auth login"}
    plan = f" · {d['subscriptionType']} plan" if d.get("subscriptionType") else ""
    return {"state": "signed_in", "account": d.get("email", ""), "detail": f"{d.get('authMethod', '?')}{plan}"}


def check_tailscale() -> dict:
    d = json_out("tailscale", "status", "--json") or {}
    backend = d.get("BackendState", "")
    if backend == "Running":
        users = d.get("User", {})
        account = users.get(str(d.get("Self", {}).get("UserID", "")), {}).get("LoginName", "")
        return {"state": "signed_in", "account": account, "detail": d.get("Self", {}).get("DNSName", "").rstrip(".")}
    if backend == "NeedsLogin":
        return {"state": "signed_out", "account": "", "detail": "run: sudo tailscale up"}
    return {"state": "error", "account": "", "detail": backend or "no response"}


AUTH_CHECKS = [
    ("Google Cloud", "gcloud", check_gcloud),
    ("Google Workspace", "gws", check_gws),
    ("GitHub", "gh", check_gh),
    ("Claude Code", "claude", check_claude),
    ("Tailscale", "tailscale", check_tailscale),
]


def run_check(name: str, exe: str, check) -> dict:
    if not shutil.which(exe):
        return {"name": name, "command": exe, "state": "not_installed", "account": "", "detail": ""}
    try:
        result = check()
    except Exception as e:  # one broken CLI shouldn't hide the others
        result = {"state": "error", "account": "", "detail": f"{type(e).__name__}: {e}"}
    return {"name": name, "command": exe, **result}


_auth = {"at": 0.0, "data": None, "refreshing": False}
_auth_lock = threading.Lock()


def refresh_auth() -> dict:
    with ThreadPoolExecutor(len(AUTH_CHECKS)) as pool:
        services = list(pool.map(lambda c: run_check(*c), AUTH_CHECKS))
    data = {"checked_at": int(time.time()), "services": services}
    with _auth_lock:
        _auth.update(at=time.monotonic(), data=data, refreshing=False)
    return data


def auth_status() -> dict:
    """Cached for AUTH_TTL; once warm, stale data is served instantly while a refresh runs in the background."""
    with _auth_lock:
        data = _auth["data"]
        if data is not None:
            if time.monotonic() - _auth["at"] >= AUTH_TTL and not _auth["refreshing"]:
                _auth["refreshing"] = True
                threading.Thread(target=refresh_auth, daemon=True).start()
            return data
    return refresh_auth()  # cold start: blocks once


# ---------- version ----------

PROJECT = Path(__file__).resolve().parents[2]  # the folder holding pyproject.toml (resolved through any symlink)
_loaded: dict | None = None


def git(*args: str) -> str | None:
    """Run git inside the project folder; None if git or the repository isn't available."""
    try:
        r = subprocess.run(["git", "-C", str(PROJECT), *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def current_version() -> dict:
    """What is on disk right now. The commit is the last one touching this folder, so unrelated commits
    elsewhere in a shared repo (such as machine-setup's snapshots) don't change it."""
    commit, commit_time = "", 0
    log = git("log", "-1", "--format=%h %ct", "--", ".")
    if log:
        commit, _, ct = log.partition(" ")
        commit_time = int(ct)
    in_git = git("rev-parse", "--is-inside-work-tree") == "true"
    dirty = bool(git("status", "--porcelain", "--", ".")) if in_git else False
    edited = max((p.stat().st_mtime for p in (PROJECT / "src").rglob("*") if p.suffix in (".py", ".html")), default=0)
    # A clean checkout is dated by its commit; local edits (or no git history) by the newest file change.
    when = commit_time if commit and not dirty else int(edited)
    shown = (commit or ("uncommitted" if in_git else "nogit")) + ("+" if dirty and commit else "")
    label = f"v{time.strftime('%Y-%m-%d %H:%M', time.localtime(when))} · {shown}"
    return {"label": label, "commit": commit, "dirty": dirty or not commit, "time": when,
            "id": f"{commit}|{int(edited)}"}  # only what the server loads (src/), so editing tests doesn't flag it stale


def version() -> dict:
    """Version on disk, plus whether the running server loaded something older (needs a restart)."""
    global _loaded
    now = current_version()
    if _loaded is None:
        _loaded = now  # first call happens at server start
    return {**now, "stale": now["id"] != _loaded["id"], "started": _loaded["time"], "running_label": _loaded["label"],
            "can_restart": can_restart()}


SERVICE = "pi-status.service"


def can_restart() -> bool:
    """Only a systemd-managed server can be restarted from its page (systemd sets INVOCATION_ID for services)."""
    return "INVOCATION_ID" in os.environ


def restart_service() -> None:
    # --no-block queues the restart and returns at once, so it still happens after this process is stopped.
    subprocess.Popen(["systemctl", "--user", "--no-block", "restart", SERVICE], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
