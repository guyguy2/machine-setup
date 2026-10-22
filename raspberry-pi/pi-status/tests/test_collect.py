import json
import subprocess

import pytest

from pi_status import collect


@pytest.mark.parametrize("raw, expected", [
    ("tool --api-key sk-abcdef1234567890 --model=x", "tool --api-key ••• --model=x"),
    ("app --token abc123 run", "app --token ••• run"),
    ("env OPENAI_API_KEY=sk-live-aaaaaaaaaaaaaaaa node x.js", "env OPENAI_API_KEY=••• node x.js"),
    ("curl -H Authorization:Bearer ghp_aaaaaaaaaaaaaaaaaaaaaaaa", "curl -H Authorization:Bearer •••"),
    ("claude --dangerously-skip-permissions --model=sonnet", "claude --dangerously-skip-permissions --model=sonnet"),
])
def test_redact(raw, expected):
    assert collect.redact(raw) == expected


def test_exe_names_native_binary():
    assert collect.exe_names(["/opt/openhuman-core/openhuman-core", "run"]) == {"openhuman-core"}


def test_exe_names_node_script_includes_package_folder():
    names = collect.exe_names(["node", "/usr/lib/node_modules/openclaw/dist/index.js", "gateway"])
    assert "openclaw" in names


def test_exe_names_python_module_and_script():
    assert "hermes_cli.main" in collect.exe_names(["/usr/bin/python3", "-m", "hermes_cli.main"])
    assert "hermes" in collect.exe_names(["/opt/python3.13", "/home/x/bin/hermes", "chat"])


def test_exe_names_ignores_shell_command_strings():
    assert collect.exe_names(["zsh", "-c", "claude something"]) == {"zsh"}


@pytest.mark.parametrize("address, expected", [
    ("127.0.0.1", "local only"), ("::1", "local only"),
    ("100.64.1.2", "tailnet"), ("fd7a:115c:a1e0::1", "tailnet"),
    ("0.0.0.0", "all interfaces"), ("::", "all interfaces"),
    ("192.168.1.5", "network"),
])
def test_exposure(address, expected):
    assert collect.exposure(address) == expected


def test_ports_parses_ss_output(monkeypatch):
    ss = "\n".join([
        'LISTEN 0 128 127.0.0.1:7788 0.0.0.0:* users:(("openhuman-core",pid=54003,fd=15))',
        "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*",
        "LISTEN 0 128 [::]:22 [::]:*",
        "LISTEN 0 4096 [fd7a:115c:a1e0::1]%tailscale0:443 [::]:*",
    ])
    monkeypatch.setattr(collect, "run", lambda *cmd: ss)
    result = collect.ports()
    assert [(p["port"], p["exposure"]) for p in result] == [(22, "all interfaces"), (443, "tailnet"), (7788, "local only")]
    assert result[1]["address"] == "fd7a:115c:a1e0::1"  # no brackets or %iface
    assert result[2]["process"] == "openhuman-core" and result[2]["pid"] == 54003


def test_sessions_parse(monkeypatch):
    who = "\n".join([
        "guy      sshd pts/0   2026-10-19 15:32 (fd1b::1)",
        "guy      seat0        2026-10-19 02:31",
        "guy      tty1         2026-10-19 02:31",
    ])
    monkeypatch.setattr(collect, "run", lambda *cmd: who)
    rows = collect.sessions()
    assert [(r["tty"], r["origin"]) for r in rows] == [("sshd pts/0", "fd1b::1"), ("tty1", "local")]


def test_ssh_help_uses_live_values():
    ts = {"dns_name": "box.tail1234.ts.net", "ip": "100.1.2.3"}
    result = collect.ssh_help("alice", "box", ts, "192.168.0.9")
    commands = [c["command"] for c in result["commands"]]
    assert commands == [
        "ssh alice@box", "ssh alice@box.tail1234.ts.net", "ssh alice@100.1.2.3",
        "ssh alice@box.local", "ssh alice@192.168.0.9",
    ]
    assert result["shortcut"]["command"] == "ssh pi"
    assert result["shortcut"]["config"] == "Host pi\n    HostName box.tail1234.ts.net\n    User alice"


def test_ssh_help_without_tailscale_falls_back_to_lan():
    result = collect.ssh_help("alice", "box", {}, "192.168.0.9")
    assert [c["command"] for c in result["commands"]] == ["ssh alice@box.local", "ssh alice@192.168.0.9"]
    assert "HostName 192.168.0.9" in result["shortcut"]["config"]


SERVE_STATUS = '{"TCP": {"443": {"HTTPS": true}}, "Web": {"box.tail1234.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8080"}}}}}'


def test_page_url_when_tailscale_serve_publishes_it(monkeypatch):
    monkeypatch.setattr(collect, "run", lambda *cmd, **kw: SERVE_STATUS)
    assert collect.page_url("box.tail1234.ts.net") == "https://box.tail1234.ts.net/#overview"


@pytest.mark.parametrize("dns_name, serve_out", [
    ("box.tail1234.ts.net", ""),          # serve not configured / tailscale missing
    ("box.tail1234.ts.net", "{}"),
    ("other.tail1234.ts.net", SERVE_STATUS),  # served under a different name
    ("", SERVE_STATUS),                   # not on a tailnet
])
def test_page_url_empty_when_not_served(monkeypatch, dns_name, serve_out):
    monkeypatch.setattr(collect, "run", lambda *cmd, **kw: serve_out)
    assert collect.page_url(dns_name) == ""


PIHOLE = {"name": "pihole", "state": "running", "ports": "53/udp, 0.0.0.0:8081->80/tcp, :::8081->80/tcp"}


def serve_status(port):
    return json.dumps({"Web": {f"box.tail1234.ts.net:{port}": {"Handlers": {"/pihole": {"Proxy": "http://127.0.0.1:8081"}}}}})


def stub_tailscale(monkeypatch, serve_out):
    monkeypatch.setattr(collect, "tailscale_info", lambda: {"dns_name": "box.tail1234.ts.net"})
    monkeypatch.setattr(collect, "run", lambda *cmd, **kw: serve_out)


def test_pihole_link_is_https_when_published(monkeypatch):
    stub_tailscale(monkeypatch, serve_status(8445))
    assert collect.pihole_link([PIHOLE]) == {"url": "https://box.tail1234.ts.net:8445/pihole/admin/", "publish": ""}


def test_pihole_link_gives_the_publish_command_when_not_published(monkeypatch):
    stub_tailscale(monkeypatch, "{}")
    assert collect.pihole_link([PIHOLE]) == {"url": "", "publish": "sudo tailscale serve --bg --https=8445 --set-path /pihole http://127.0.0.1:8081"}


@pytest.mark.parametrize("containers", [
    [],                                              # no containers
    [{**PIHOLE, "state": "exited"}],                 # stopped
    [{**PIHOLE, "name": "other"}],                   # some other container
    [{**PIHOLE, "ports": "53/udp"}],                 # web port not published
])
def test_pihole_link_empty(monkeypatch, containers):
    stub_tailscale(monkeypatch, serve_status(8445))
    assert collect.pihole_link(containers) == {"url": "", "publish": ""}


def test_docker_not_installed(monkeypatch):
    monkeypatch.setattr(collect.shutil, "which", lambda name: None)
    assert collect.docker() == {"installed": False, "containers": []}


def test_docker_lists_containers(monkeypatch):
    out = '{"Names":"web","Image":"nginx","State":"running","Status":"Up 2h","Ports":"80/tcp"}\n'
    monkeypatch.setattr(collect.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(collect.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    result = collect.docker()
    assert result["containers"] == [{"name": "web", "image": "nginx", "state": "running", "status": "Up 2h", "ports": "80/tcp"}]


def test_docker_permission_error_is_reported(monkeypatch):
    monkeypatch.setattr(collect.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(collect.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "permission denied"))
    assert collect.docker()["error"] == "permission denied"


def test_docker_daemon_not_running(monkeypatch):
    err = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"
    monkeypatch.setattr(collect.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(collect.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", err))
    assert collect.docker() == {"installed": True, "running": False, "containers": []}


def fake_proc(pid, argv, rss=1000, ppid=1):
    return {"pid": pid, "ppid": ppid, "user": "guy", "cpu": 0.0, "rss": rss, "age_s": 5, "argv": argv, "ticks": 0, "start": 0}


def test_agents_matches_running_and_hides_optional(monkeypatch):
    procs = [
        fake_proc(1, ["claude", "--model=sonnet"]),
        fake_proc(2, ["node", "/lib/node_modules/openclaw/dist/index.js", "gateway"]),
        fake_proc(3, ["zsh", "-c", "claude hermes ollama"]),
    ]
    monkeypatch.setattr(collect, "scan", lambda: procs)
    monkeypatch.setattr(collect, "ports", lambda: [{"pid": 2, "address": "127.0.0.1", "port": 18789}])
    monkeypatch.setattr(collect, "run", lambda *cmd: "active")
    result = {a["name"]: a for a in collect.agents()}
    assert [i["pid"] for i in result["Claude Code"]["instances"]] == [1]
    assert result["OpenClaw"]["instances"][0]["ports"] == ["127.0.0.1:18789"]
    assert result["Hermes"]["instances"] == []       # the zsh -c string must not count
    assert "Ollama" not in result and "Codex" not in result  # optional + not running
    assert result["OpenHuman"]["unit_state"] == "active"


def test_agents_skips_the_servers_own_child_processes(monkeypatch):
    """The sign-in check runs `claude auth status` while the Agents tab scans /proc; it is not a running agent."""
    import os
    procs = [fake_proc(1, ["claude", "auth", "status"], ppid=os.getpid()), fake_proc(2, ["claude"], ppid=os.getppid())]
    monkeypatch.setattr(collect, "scan", lambda: procs)
    monkeypatch.setattr(collect, "ports", lambda: [])
    monkeypatch.setattr(collect, "run", lambda *cmd, **kw: "active")
    claude = next(a for a in collect.agents() if a["name"] == "Claude Code")
    assert [i["pid"] for i in claude["instances"]] == [2]


def test_sample_records_parent_pid():
    import os
    child = subprocess.Popen(["sleep", "5"])
    try:
        assert collect.sample()[child.pid]["ppid"] == os.getpid()
    finally:
        child.kill()
        child.wait()


def test_top_processes_shape():
    result = collect.top_processes()
    assert result["total"] > 0
    assert all({"pid", "cpu", "rss", "cmd", "user", "age_s"} <= p.keys() for p in result["processes"])
    assert len(result["processes"]) <= 50


def test_scan_includes_own_process():
    import os
    assert os.getpid() in {p["pid"] for p in collect.scan()}


# ---------- sign-in checks ----------

def fake_cli(monkeypatch, outputs: dict):
    """Make collect.run return canned output keyed by the command's first words."""
    def run(*cmd, **kw):
        for prefix, out in outputs.items():
            if " ".join(cmd).startswith(prefix):
                return out
        return ""
    monkeypatch.setattr(collect, "run", run)


def test_gcloud_signed_in_with_project(monkeypatch):
    fake_cli(monkeypatch, {"gcloud auth list": '[{"account": "a@x.com", "status": "ACTIVE"}]', "gcloud config": "my-proj"})
    assert collect.check_gcloud() == {"state": "signed_in", "account": "a@x.com", "detail": "project my-proj"}


def test_gcloud_signed_out(monkeypatch):
    fake_cli(monkeypatch, {"gcloud auth list": "[]"})
    assert collect.check_gcloud()["state"] == "signed_out"


def test_gws_valid_expired_and_signed_out(monkeypatch):
    status = '{"user": "a@x.com", "token_valid": %s, "project_id": "p", "scope_count": 13, "storage": "encrypted", "client_id": "SECRET-ID"}'
    fake_cli(monkeypatch, {"gws auth status": status % "true"})
    ok = collect.check_gws()
    assert ok["state"] == "signed_in" and ok["account"] == "a@x.com" and "13 scopes" in ok["detail"]
    assert "SECRET-ID" not in str(ok)  # only whitelisted fields leave the module
    fake_cli(monkeypatch, {"gws auth status": status % "false"})
    assert collect.check_gws()["state"] == "expired"
    fake_cli(monkeypatch, {"gws auth status": "not json"})
    assert collect.check_gws()["state"] == "signed_out"


def test_gh_states(monkeypatch):
    hosts = '{"hosts": {"github.com": [{"state": "%s", "active": true, "host": "github.com", "login": "me", "gitProtocol": "https"}]}}'
    fake_cli(monkeypatch, {"gh auth status": hosts % "success"})
    assert collect.check_gh() == {"state": "signed_in", "account": "me", "detail": "github.com · git over https"}
    fake_cli(monkeypatch, {"gh auth status": hosts % "error"})
    assert collect.check_gh()["state"] == "expired"
    fake_cli(monkeypatch, {"gh auth status": ""})
    assert collect.check_gh()["state"] == "signed_out"


def test_claude_hides_org_details(monkeypatch):
    fake_cli(monkeypatch, {"claude auth status": '{"loggedIn": true, "email": "a@x.com", "authMethod": "claude.ai", "subscriptionType": "max", "orgId": "ORG-SECRET"}'})
    result = collect.check_claude()
    assert result == {"state": "signed_in", "account": "a@x.com", "detail": "claude.ai · max plan"}
    fake_cli(monkeypatch, {"claude auth status": '{"loggedIn": false}'})
    assert collect.check_claude()["state"] == "signed_out"


def test_tailscale_states(monkeypatch):
    running = '{"BackendState": "Running", "Self": {"UserID": 7, "DNSName": "pi.ts.net."}, "User": {"7": {"LoginName": "a@x.com"}}}'
    fake_cli(monkeypatch, {"tailscale status": running})
    assert collect.check_tailscale() == {"state": "signed_in", "account": "a@x.com", "detail": "pi.ts.net"}
    fake_cli(monkeypatch, {"tailscale status": '{"BackendState": "NeedsLogin"}'})
    assert collect.check_tailscale()["state"] == "signed_out"
    fake_cli(monkeypatch, {"tailscale status": ""})
    assert collect.check_tailscale()["state"] == "error"


def test_missing_cli_is_not_installed(monkeypatch):
    monkeypatch.setattr(collect.shutil, "which", lambda name: None)
    result = collect.run_check("Thing", "thing", lambda: pytest.fail("should not run"))
    assert result["state"] == "not_installed"


def test_one_failing_check_does_not_hide_the_others(monkeypatch):
    monkeypatch.setattr(collect.shutil, "which", lambda name: "/bin/x")
    def broken():
        raise RuntimeError("kaput")
    bad = collect.run_check("Bad", "bad", broken)
    good = collect.run_check("Good", "good", lambda: {"state": "signed_in", "account": "", "detail": ""})
    assert bad["state"] == "error" and "kaput" in bad["detail"]
    assert good["state"] == "signed_in"


def test_auth_status_is_cached_and_refreshes_in_background(monkeypatch):
    calls = []
    monkeypatch.setitem(collect._auth, "data", None)
    monkeypatch.setattr(collect, "AUTH_CHECKS", [("A", "a", lambda: calls.append(1) or {"state": "signed_in", "account": "", "detail": ""})])
    monkeypatch.setattr(collect.shutil, "which", lambda name: "/bin/x")

    first = collect.auth_status()                 # cold: computes
    assert len(calls) == 1 and first["services"][0]["name"] == "A"
    assert collect.auth_status() is first         # warm: served from cache
    assert len(calls) == 1

    monkeypatch.setattr(collect, "AUTH_TTL", 0)   # now stale: returns old data immediately, refreshes behind
    assert collect.auth_status() is first
    for _ in range(50):
        if len(calls) == 2:
            break
        collect.time.sleep(0.05)
    assert len(calls) == 2


# ---------- version stamp ----------

def make_project(tmp_path, monkeypatch, git_init=True):
    """A throwaway project folder shaped like this one, optionally a git repo with one commit."""
    (tmp_path / "src" / "pi_status").mkdir(parents=True)
    (tmp_path / "src" / "pi_status" / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(collect, "PROJECT", tmp_path)
    monkeypatch.setattr(collect, "_loaded", None)
    if git_init:
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", "-C", str(tmp_path), *cmd], check=True, env={**__import__("os").environ, **env})


def test_version_clean_checkout_shows_commit(tmp_path, monkeypatch):
    make_project(tmp_path, monkeypatch)
    v = collect.version()
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert v["label"].startswith("v20") and v["label"].endswith(f" · {head}")
    assert v["commit"] == head and v["dirty"] is False and v["stale"] is False


def test_version_marks_uncommitted_changes(tmp_path, monkeypatch):
    make_project(tmp_path, monkeypatch)
    (tmp_path / "src" / "pi_status" / "a.py").write_text("x = 2\n")
    v = collect.version()
    assert v["label"].endswith("+") and v["dirty"] is True


def test_version_without_git(tmp_path, monkeypatch):
    make_project(tmp_path, monkeypatch, git_init=False)
    monkeypatch.setattr(collect, "git", lambda *a: None)
    v = collect.version()
    assert v["label"].endswith("· nogit") and v["dirty"] is True


def test_version_ignores_commits_elsewhere_in_the_repo(tmp_path, monkeypatch):
    """A shared repo (machine-setup) gets snapshot commits constantly; they must not change this project's version."""
    make_project(tmp_path, monkeypatch, git_init=False)
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    sub = tmp_path / "site"
    (sub / "src" / "pi_status").mkdir(parents=True)
    (sub / "src" / "pi_status" / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(collect, "PROJECT", sub)
    ident = ["-c", "user.name=t", "-c", "user.email=t@x"]
    git_in = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *ident, *a], check=True, capture_output=True)
    git_in("add", "site"); git_in("commit", "-q", "-m", "site")
    before = collect.current_version()["commit"]
    (tmp_path / "other.txt").write_text("unrelated\n")
    git_in("add", "other.txt"); git_in("commit", "-q", "-m", "unrelated")
    assert collect.current_version()["commit"] == before


def test_version_flags_stale_when_code_changes_after_start(tmp_path, monkeypatch):
    make_project(tmp_path, monkeypatch)
    assert collect.version()["stale"] is False          # pins what the "running" server loaded
    f = tmp_path / "src" / "pi_status" / "a.py"
    f.write_text("x = 3\n")
    import os
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 10))
    v = collect.version()
    assert v["stale"] is True and v["running_label"] != v["label"]


def test_editing_tests_does_not_flag_stale(tmp_path, monkeypatch):
    make_project(tmp_path, monkeypatch)
    collect.version()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("pass\n")
    assert collect.version()["stale"] is False


def test_scratch_scripts_in_tmp_are_not_mistaken_for_agents():
    """Claude's scratchpad is /tmp/claude-<uid>/...; a python script run from there is not Claude Code."""
    argv = ["/home/x/.venv/bin/python", "/tmp/claude-1000/proj/scratchpad/shot.py"]
    assert collect.exe_names(argv) == {"python", "shot.py"}
    assert not any(n.startswith("claude") for n in collect.exe_names(argv))


def test_agents_ignores_python_script_run_from_tmp(monkeypatch):
    procs = [fake_proc(1, ["claude", "--model=sonnet"]), fake_proc(2, ["python3", "/tmp/claude-1000/x/shot.py"])]
    monkeypatch.setattr(collect, "scan", lambda: procs)
    monkeypatch.setattr(collect, "ports", lambda: [])
    monkeypatch.setattr(collect, "run", lambda *cmd, **kw: "active")
    claude = next(a for a in collect.agents() if a["name"] == "Claude Code")
    assert [i["pid"] for i in claude["instances"]] == [1]


def test_can_restart_only_under_systemd(monkeypatch):
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    assert collect.can_restart() is False
    monkeypatch.setenv("INVOCATION_ID", "abc123")   # systemd sets this for every service it starts
    assert collect.can_restart() is True


def test_restart_service_queues_a_non_blocking_user_restart(monkeypatch):
    seen = {}
    monkeypatch.setattr(collect.subprocess, "Popen", lambda cmd, **kw: seen.update(cmd=cmd, kw=kw))
    collect.restart_service()
    assert seen["cmd"] == ["systemctl", "--user", "--no-block", "restart", "pi-status.service"]
    assert seen["kw"]["start_new_session"] is True   # survives the service being stopped


# ---------- agent lab ----------

RUN_NOTE = """---
use_case: UC-001
agent: hermes
date: 2026-10-20 09:00
model: claude-opus-5-5
outcome: partial            # pass | partial | fail
score_quality: 4            # 1-5  how good was the result itself?
score_ux:                   # 1-5  how pleasant/clear the interface and interaction were
overall: 3.5
peak_rss_mb: 812
---

# UC-001 on hermes

## My opinion
Fast, but it missed two emails.
"""

USE_CASE = """---
id: UC-001
title: Fetch and triage email
risk: read-only
---

## Prompt (paste exactly)
```
Check my inbox.
Don't change anything.
```

## Prerequisites
- Gmail
"""

RESULTS = """# Results

## Overall impressions

### OpenClaw
- 

### Hermes
- Quick and chatty.

## Verdict so far
### Not an agent
- ignored
"""


def test_front_matter_drops_comments_and_keeps_body():
    meta, body = collect.front_matter(RUN_NOTE)
    assert meta["outcome"] == "partial" and meta["score_quality"] == "4" and meta["score_ux"] == ""
    assert meta["date"] == "2026-10-20 09:00"  # colons after the first one belong to the value
    assert body.startswith("# UC-001 on hermes") and "missed two emails" in body


@pytest.mark.parametrize("text", ["no front matter", "---\nkey: value\nnever closed"])
def test_front_matter_missing_or_unterminated(text):
    assert collect.front_matter(text) == ({}, text)


@pytest.fixture
def lab_dir(tmp_path, monkeypatch):
    (tmp_path / "use-cases").mkdir()
    (tmp_path / "runs").mkdir()
    (tmp_path / "use-cases" / "UC-001-fetch-email.md").write_text(USE_CASE)
    (tmp_path / "runs" / "2026-10-20_UC-001_hermes.md").write_text(RUN_NOTE)
    (tmp_path / "runs" / "2026-10-19_UC-001_hermes.md").write_text(RUN_NOTE.replace("2026-10-20 09:00", "2026-10-19 18:00"))
    (tmp_path / "runs" / "2026-10-19_UC-001_hermes.samples").write_text("1 2 3 4\n")  # not a note
    (tmp_path / "results.md").write_text(RESULTS)
    monkeypatch.setattr(collect, "LAB", tmp_path)
    monkeypatch.setattr(collect, "sample", lambda: {1: {"argv": ["/home/x/bin/hermes", "chat"]}})
    return tmp_path


def test_lab_reads_use_cases_runs_and_impressions(lab_dir):
    d = collect.lab()
    assert d["found"] and d["path"] == str(lab_dir)
    assert d["use_cases"] == [{"id": "UC-001", "title": "Fetch and triage email", "file": "UC-001-fetch-email.md",
                               "category": "", "risk": "read-only", "prompt": "Check my inbox.\nDon't change anything."}]
    assert [r["date"] for r in d["runs"]] == ["2026-10-19 18:00", "2026-10-20 09:00"]  # oldest first
    run = d["runs"][1]
    assert run["agent"] == "hermes" and run["outcome"] == "partial" and run["model"] == "claude-opus-5-5"
    assert run["score_quality"] == 4 and run["overall"] == 3.5 and run["peak_rss_mb"] == 812
    assert run["score_ux"] is None and run["duration_min"] is None  # blank or missing fields aren't zeros
    assert "missed two emails" in run["note"]
    assert d["impressions"] == {"hermes": "- Quick and chatty."}  # empty template bullets and other sections ignored
    assert {a["id"]: a["running"] for a in d["agents"]} == {"openclaw": False, "hermes": True, "openhuman": False}


def test_lab_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "LAB", tmp_path / "nope")
    assert collect.lab() == {"found": False, "path": str(tmp_path / "nope")}


def test_dashboards_link_only_what_tailscale_publishes(monkeypatch):
    monkeypatch.setattr(collect, "ports", lambda: [{"pid": 2, "address": "127.0.0.1", "port": 18789}])
    monkeypatch.setattr(collect, "tailscale_info", lambda: {"dns_name": "box.tail9.ts.net"})
    monkeypatch.setattr(collect, "run", lambda *cmd: json.dumps({"Web": {"box.tail9.ts.net:8444": {"Handlers": {"/openclaw": {}}}}}))
    result = {d["name"]: d for d in collect.dashboards()}
    assert result["OpenClaw"]["running"] and result["OpenClaw"]["tailnet_url"] == "https://box.tail9.ts.net:8444/openclaw/"
    assert not result["Hermes"]["running"] and result["Hermes"]["tailnet_url"] == ""
    assert result["Hermes"]["publish"] == "tailscale serve --bg --https=8443 --set-path /hermes http://127.0.0.1:9120/hermes"
    assert result["OpenClaw"]["publish"] == "tailscale serve --bg --https=8444 --set-path /openclaw http://127.0.0.1:18789/openclaw"
    assert result["Hermes"]["tunnel"] == "ssh -N -L 9119:localhost:9119 pi"
    assert "local_url" not in result["OpenHuman"]  # placeholder: no web UI
    assert "start" not in result["Hermes"]  # its service has a Start button; a manual start would clash over the port


def test_dashboards_without_tailscale(monkeypatch):
    monkeypatch.setattr(collect, "ports", lambda: [])
    monkeypatch.setattr(collect, "tailscale_info", lambda: {})
    monkeypatch.setattr(collect, "run", lambda *cmd: "")
    assert all(d.get("tailnet_url", "") == "" for d in collect.dashboards())


def test_control_agent_refuses_units_that_are_not_agents(monkeypatch):
    called = []
    monkeypatch.setattr(collect.subprocess, "run", lambda *a, **k: called.append(a))
    assert collect.control_agent("ssh.service", "stop")[0] == 404
    assert collect.control_agent("pi-status.service", "stop")[0] == 404
    assert collect.control_agent("openhuman.service", "restart")[0] == 404
    assert called == []


def test_control_agent_stops_gracefully_and_reports_state(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(collect.subprocess, "run", fake_run)
    monkeypatch.setattr(collect, "run", lambda *cmd: "inactive")
    assert collect.control_agent("hermes-dashboard.service", "stop") == (200, {"unit": "hermes-dashboard.service", "state": "inactive"})
    assert calls == [["systemctl", "--user", "stop", "hermes-dashboard.service"]]  # plain stop: SIGTERM, then the stop timeout


def test_control_agent_reports_systemctl_failure(monkeypatch):
    monkeypatch.setattr(collect.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 5, "", "Unit not loaded."))
    monkeypatch.setattr(collect, "run", lambda *cmd: "inactive")
    code, body = collect.control_agent("openclaw-gateway.service", "start")
    assert code == 500 and body["error"] == "Unit not loaded."
