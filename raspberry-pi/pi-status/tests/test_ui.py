"""Renders the real page in Chromium via Playwright."""

import pytest

TABS = ["overview", "network", "agents", "lab", "docker", "services", "processes", "ports"]
PHONE = (390, 844)

NETWORK = {
    "connection": "Wi-Fi “testnet” (80%)", "local_ip": "10.0.0.5", "gateway": "10.0.0.1", "device": "wlan0",
    "dns": ["10.0.0.1"], "wifi": {"ssid": "testnet", "signal": 80, "rate": "100 Mbit/s", "channel": "36", "security": "WPA2"},
    "interfaces": [{"name": "wlan0", "state": "up", "mac": "aa:bb", "addresses": ["10.0.0.5/24"]}],
    "tailscale": {"dns_name": "box.tail9.ts.net", "ip": "100.9.9.9", "online": True, "peers": []},
    "sessions": [],
    "page_url": "https://box.tail9.ts.net/#overview",
    "ssh": {
        "commands": [
            {"label": "Over Tailscale (from anywhere)", "command": "ssh alice@box"},
            {"label": "Same Wi-Fi or LAN, by IP", "command": "ssh alice@10.0.0.5"},
        ],
        "shortcut": {"alias": "pi", "command": "ssh pi", "config": "Host pi\n    HostName box.tail9.ts.net\n    User alice"},
    },
}


def open_tab(page, base_url, tab):
    page.goto(f"{base_url}/#{tab}")
    page.wait_for_selector("#view h2")


@pytest.mark.parametrize("tab", TABS)
def test_tab_renders_without_errors(make_page, base_url, tab):
    page = make_page()
    open_tab(page, base_url, tab)
    assert page.locator("nav a[aria-current=page]").get_attribute("data-tab") == tab
    assert page.locator("#view h2").inner_text()
    assert page.locator("#conn").inner_text().startswith("updated")
    assert page.errors == []


def test_nav_click_switches_tabs(make_page, base_url):
    page = make_page()
    open_tab(page, base_url, "overview")
    page.click("nav a[data-tab=agents]")
    page.wait_for_function("document.querySelector('#view h2')?.textContent.includes('Agents')")
    assert page.url.endswith("#agents")


def test_sidebar_hostname_loads_on_any_tab(make_page, base_url):
    page = make_page()
    open_tab(page, base_url, "ports")
    page.wait_for_function("document.getElementById('host').textContent !== 'Pi Status'")


def test_sidebar_is_on_the_left_on_desktop(make_page, base_url):
    page = make_page(1100, 900)
    open_tab(page, base_url, "overview")
    nav, view = page.locator("nav").bounding_box(), page.locator("#view").bounding_box()
    assert nav["x"] < view["x"] and nav["y"] < 200


def test_nav_becomes_top_strip_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    open_tab(page, base_url, "overview")
    nav, view = page.locator("nav").bounding_box(), page.locator("#view").bounding_box()
    assert nav["y"] < view["y"] and nav["width"] <= PHONE[0]


@pytest.mark.parametrize("tab", TABS)
def test_no_horizontal_page_scroll_on_phone(make_page, base_url, tab):
    page = make_page(*PHONE)
    open_tab(page, base_url, tab)
    page.wait_for_timeout(300)
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1], f"page is {widths[0]}px wide in a {widths[1]}px viewport"


def test_no_horizontal_page_scroll_on_phone_with_ssh_data(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/network", lambda r: r.fulfill(json=NETWORK))
    open_tab(page, base_url, "network")
    page.wait_for_selector(".ssh-row")
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]


def test_ssh_commands_are_built_from_api_data(make_page, base_url):
    page = make_page()
    page.route("**/api/network", lambda r: r.fulfill(json=NETWORK))
    open_tab(page, base_url, "network")
    page.wait_for_selector(".ssh-row")
    text = page.locator("#view").inner_text()
    assert "ssh alice@box" in text and "ssh alice@10.0.0.5" in text and "ssh pi" in text
    assert "HostName box.tail9.ts.net" in text


def test_page_url_is_a_link_with_copy(make_page, base_url):
    page = make_page()
    page.route("**/api/network", lambda r: r.fulfill(json=NETWORK))
    open_tab(page, base_url, "network")
    link = page.locator(".page-row a")
    assert link.get_attribute("href") == "https://box.tail9.ts.net/#overview"
    page.locator(".page-row .copy").click()
    assert page.evaluate("navigator.clipboard.readText()") == "https://box.tail9.ts.net/#overview"


def test_page_url_hidden_when_not_served(make_page, base_url):
    page = make_page()
    page.route("**/api/network", lambda r: r.fulfill(json={**NETWORK, "page_url": ""}))
    open_tab(page, base_url, "network")
    page.wait_for_selector(".ssh-row")
    assert page.locator(".page-row").count() == 0


def test_copy_button_copies_command(make_page, base_url):
    page = make_page()
    page.route("**/api/network", lambda r: r.fulfill(json=NETWORK))
    open_tab(page, base_url, "network")
    page.wait_for_selector(".ssh-row")
    page.locator(".ssh-row .copy").first.click()
    assert page.evaluate("navigator.clipboard.readText()") == "ssh alice@box"
    assert page.locator(".ssh-row .copy").first.inner_text() == "Copied"


def test_command_lines_are_escaped_not_injected(make_page, base_url):
    evil = '<img src=x onerror="window.pwned=1"><script>window.pwned=2</script>'
    agents = [{"name": "Claude Code", "kind": "Coding agent", "instances": [
        {"pid": 1, "user": "guy", "cpu": 1.0, "rss": 2**20, "age_s": 5, "cwd": "~", "ports": [], "cmd": evil}]}]
    page = make_page()
    page.route("**/api/agents", lambda r: r.fulfill(json=agents))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view table")
    assert page.evaluate("window.pwned") is None
    assert page.locator("#view img").count() == 0
    assert evil in page.locator("#view").inner_text()


def test_docker_not_installed_message(make_page, base_url):
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json={"installed": False, "containers": []}))
    open_tab(page, base_url, "docker")
    assert "isn't installed" in page.locator("#view").inner_text()


def test_docker_containers_table(make_page, base_url):
    data = {"installed": True, "containers": [
        {"name": "web", "image": "nginx", "state": "running", "status": "Up 2h", "ports": "80/tcp"}]}
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, "docker")
    page.wait_for_selector("#view table")
    assert "web" in page.locator("#view tbody").inner_text() and "nginx" in page.locator("#view tbody").inner_text()


def test_agents_show_idle_ones_as_not_running(make_page, base_url):
    data = [
        {"name": "Hermes", "kind": "Agent", "instances": []},
        {"name": "OpenHuman", "kind": "Personal assistant", "unit": "openhuman.service", "unit_state": "active", "instances": [
            {"pid": 7, "user": "guy", "cpu": 0.0, "rss": 2**20, "age_s": 99, "cwd": "~", "ports": ["127.0.0.1:7788"], "cmd": "openhuman-core run"}]},
    ]
    page = make_page()
    page.route("**/api/agents", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view table")
    cards = page.locator("#view .agent")
    assert "OpenHuman" in cards.nth(0).inner_text()  # running ones sort first
    assert "not running" in cards.nth(1).inner_text()
    assert "127.0.0.1:7788" in cards.nth(0).inner_text()


def test_process_sort_toggle(make_page, base_url):
    procs = {"total": 3, "processes": [
        {"pid": 1, "user": "u", "cpu": 90.0, "rss": 2**20, "age_s": 1, "cmd": "cpuhog"},
        {"pid": 2, "user": "u", "cpu": 1.0, "rss": 2**30, "age_s": 1, "cmd": "memhog"}]}
    page = make_page()
    page.route("**/api/processes", lambda r: r.fulfill(json=procs))
    open_tab(page, base_url, "processes")
    page.wait_for_selector("#view tbody tr")
    assert "cpuhog" in page.locator("#view tbody tr").first.inner_text()
    page.click("text=Top by memory")
    page.wait_for_function("document.querySelector('#view tbody tr')?.textContent.includes('memhog')")


def test_api_failure_shows_unreachable(make_page, base_url):
    page = make_page()
    page.route("**/api/ports", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    open_tab_ports = f"{base_url}/#ports"
    page.goto(open_tab_ports)
    page.wait_for_function("document.getElementById('conn').textContent.includes('unreachable')")
    assert "boom" in page.locator("#view").inner_text()


AUTH = {"checked_at": 0, "services": [
    {"name": "Google Cloud", "command": "gcloud", "state": "signed_in", "account": "me@x.com", "detail": "project demo"},
    {"name": "Google Workspace", "command": "gws", "state": "expired", "account": "me@x.com", "detail": "13 scopes"},
    {"name": "GitHub", "command": "gh", "state": "signed_out", "account": "", "detail": "run: gh auth login"},
    {"name": "Claude Code", "command": "claude", "state": "not_installed", "account": "", "detail": ""},
]}


def test_agents_tab_shows_sign_in_status(make_page, base_url):
    page = make_page()
    page.route("**/api/auth", lambda r: r.fulfill(json=AUTH))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view table")
    text = page.locator("#view").inner_text()
    for expected in ["Sign-ins", "Google Cloud", "gcloud", "Google Workspace", "gws", "gh", "me@x.com", "project demo",
                     "signed in", "expired", "signed out", "not installed"]:
        assert expected in text
    assert page.errors == []


def test_agents_tab_survives_sign_in_failure(make_page, base_url):
    page = make_page()
    page.route("**/api/auth", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    open_tab(page, base_url, "agents")
    page.wait_for_function("document.querySelector('#view')?.textContent.includes('Running agents')")
    assert "Sign-in status unavailable" in page.locator("#view").inner_text()
    assert "Claude Code" in page.locator("#view").inner_text()  # the agent list still renders


def test_sign_in_table_fits_phone(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/auth", lambda r: r.fulfill(json=AUTH))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view table")
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]


VERSION = {"label": "v2026-10-19 16:43 · a1b2c3d", "commit": "a1b2c3d", "dirty": False, "time": 0, "stale": False,
           "started": 0, "running_label": "v2026-10-19 16:43 · a1b2c3d"}


def test_version_is_bottom_left_of_the_sidebar(make_page, base_url):
    page = make_page(1100, 900)
    page.route("**/api/version", lambda r: r.fulfill(json=VERSION))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('a1b2c3d')")
    box, side = page.locator("#version").bounding_box(), page.locator(".side").bounding_box()
    assert box["x"] < 60 and box["x"] + box["width"] <= side["x"] + side["width"]
    assert box["y"] > 900 - 120, f"version is at y={box['y']}, not at the bottom of a 900px window"
    assert page.locator("#version").inner_text().startswith("v2026-10-19 16:43")


def test_version_warns_when_server_is_stale(make_page, base_url):
    page = make_page()
    page.route("**/api/version", lambda r: r.fulfill(json={**VERSION, "stale": True, "label": "v2026-10-19 17:00 · f00ba42"}))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('newer code on disk')")
    assert "restart" in page.locator("#version").inner_text()
    assert "false" not in page.locator("#version").inner_text()


def test_version_has_no_stale_warning_when_current(make_page, base_url):
    page = make_page()
    page.route("**/api/version", lambda r: r.fulfill(json=VERSION))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('a1b2c3d')")
    assert "restart" not in page.locator("#version").inner_text()
    assert "false" not in page.locator("#version").inner_text()


def test_version_visible_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/version", lambda r: r.fulfill(json=VERSION))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('a1b2c3d')")
    assert page.locator("#version").is_visible()
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]


STATUS = {"hostname": "box", "model": "Raspberry Pi 5 Model B Rev 1.0", "os": "Debian", "kernel": "6.x", "uptime_s": 90,
          "load": [0.1, 0.2, 0.3], "cpus": 4, "cpu_percent": 5.0, "temp_c": 50.0, "mem_total": 2**33, "mem_used": 2**30,
          "disk_total": 2**37, "disk_used": 2**34, "throttled": [], "tailscale_ip": "100.64.0.1", "local_ip": "10.0.0.5",
          "gateway": "10.0.0.1", "connection": "Wi-Fi “x” (80%)", "time": 0}


def test_overview_details_include_model_and_revision(make_page, base_url):
    page = make_page()
    page.route("**/api/status", lambda r: r.fulfill(json=STATUS))
    open_tab(page, base_url, "overview")
    page.wait_for_selector("#view dl")
    details = page.locator("#view dl").inner_text()
    assert "Model" in details and "Raspberry Pi 5 Model B Rev 1.0" in details
    # still shown in the sidebar too
    assert "Raspberry Pi 5 Model B Rev 1.0" in page.locator("#model").inner_text()


def test_restart_button_restarts_then_reloads(make_page, base_url):
    state = {"stale": True, "posts": []}

    def version(route):
        route.fulfill(json={**VERSION, "stale": state["stale"], "can_restart": True, "label": "v2026-10-19 17:00 · f00ba42"})

    def restart(route):
        state["posts"].append(route.request.headers.get("x-requested-with"))
        state["stale"] = False          # the "new server" is up and current
        route.fulfill(status=202, json={"restarting": True})

    page = make_page()
    page.route("**/api/version", version)
    page.route("**/api/restart", restart)
    open_tab(page, base_url, "overview")
    page.wait_for_selector("#version button")
    assert "restart to update" in page.locator("#version").inner_text()
    with page.expect_event("load", timeout=15000):   # the page reloads itself once the server is current
        page.click("#version button")
        assert page.locator("#version button").inner_text() == "Restarting…"
    assert state["posts"] == ["pi-status"]            # sent the anti-CSRF header


def test_no_restart_button_when_server_cannot_restart_itself(make_page, base_url):
    page = make_page()
    page.route("**/api/version", lambda r: r.fulfill(json={**VERSION, "stale": True, "can_restart": False}))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('restart')")
    assert page.locator("#version button").count() == 0
    assert "restart the server to update" in page.locator("#version").inner_text()


def test_no_restart_button_when_up_to_date(make_page, base_url):
    page = make_page()
    page.route("**/api/version", lambda r: r.fulfill(json={**VERSION, "can_restart": True}))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('a1b2c3d')")
    assert page.locator("#version button").count() == 0


def count_api_requests(page):
    seen = []
    page.on("request", lambda r: seen.append(r.url.split("/api/")[1]) if "/api/" in r.url else None)
    return seen


@pytest.mark.parametrize("tab", TABS)
def test_nothing_polls_in_the_background(make_page, base_url, tab):
    page = make_page()
    page.clock.install()
    seen = count_api_requests(page)
    open_tab(page, base_url, tab)
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    before = list(seen)
    page.clock.run_for(10 * 60 * 1000)   # ten minutes pass in the page's own timers
    page.wait_for_timeout(300)
    assert seen == before, f"requests made while idle: {seen[len(before):]}"


def test_each_tab_visit_fetches_once(make_page, base_url):
    page = make_page()
    seen = count_api_requests(page)
    open_tab(page, base_url, "ports")
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    assert seen.count("ports") == 1 and seen.count("version") == 1


def test_refresh_button_reloads_the_current_tab(make_page, base_url):
    page = make_page()
    seen = count_api_requests(page)
    open_tab(page, base_url, "ports")
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    seen.clear()
    page.click("#refresh")
    page.wait_for_function("document.getElementById('refresh').textContent === 'Refresh'")
    assert seen.count("ports") == 1 and seen.count("version") == 1
    assert not page.locator("#refresh").is_disabled()


def test_refresh_button_is_reachable_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    open_tab(page, base_url, "overview")
    assert page.locator("#refresh").is_visible()
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]


# ---------- agent lab ----------

LAB = {
    "found": True, "path": "~/dev/agent-lab",
    "agents": [{"id": "openclaw", "name": "OpenClaw", "running": False}, {"id": "hermes", "name": "Hermes", "running": True},
               {"id": "openhuman", "name": "OpenHuman", "running": False}],
    "use_cases": [{"id": "UC-001", "title": "Fetch email", "file": "UC-001-fetch-email.md", "category": "email",
                   "risk": "read-only", "prompt": "Check my inbox."},
                  {"id": "UC-002", "title": "Pay bills", "file": "UC-002-pay-bills.md", "category": "finance",
                   "risk": "money", "prompt": "Find bills."}],
    "runs": [
        {"file": "2026-10-19_UC-001_hermes.md", "use_case": "UC-001", "agent": "hermes", "date": "2026-10-19 18:00",
         "outcome": "fail", "overall": 1, "score_quality": 2, "duration_min": 9, "note": "old"},
        {"file": "2026-10-20_UC-001_hermes.md", "use_case": "UC-001", "agent": "hermes", "date": "2026-10-20 09:00",
         "version": "hermes-agent 0.22.2", "model": "claude-opus-5-5", "outcome": "pass", "overall": 4, "score_quality": 4,
         "duration_min": 3, "peak_rss_mb": 800,
         "note": "## What happened\nRead the inbox `fast`.\n- [x] Fetched the real inbox\n- [ ] Changed nothing\n\n<img src=x onerror=\"window.pwned=1\">"},
    ],
    "impressions": {"hermes": "- Quick and chatty."},
}


def open_lab(page, base_url, data=LAB, hash="lab"):
    page.route("**/api/lab", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, hash)


def test_lab_scoreboard_shows_latest_run_per_cell(make_page, base_url):
    page = make_page()
    open_lab(page, base_url)
    rows = page.locator("#view table").first.locator("tbody tr")
    first = rows.nth(0).inner_text()
    assert "pass" in first and "4/5" in first and "2 runs" in first and "fail" not in first
    assert rows.nth(1).inner_text().count("–") == 3  # UC-002: nobody ran it yet
    assert "Hermes · running" in page.locator("#view").inner_text()
    assert page.errors == []


def test_lab_chart_averages_scores(make_page, base_url):
    page = make_page()
    open_lab(page, base_url)
    quality = page.locator(".lab-row").nth(1)
    assert quality.locator(".lab-label").inner_text() == "Quality"
    hermes = quality.locator(".lab-bar").nth(1)
    assert hermes.get_attribute("data-tip") == "Hermes · Quality: 3 / 5"  # (2 + 4) / 2
    assert hermes.locator(".lab-val").inner_text() == "3"
    assert quality.locator(".lab-bar").nth(0).locator(".lab-val").inner_text() == "–"


def test_lab_chart_hidden_until_something_is_scored(make_page, base_url):
    page = make_page()
    open_lab(page, base_url, {**LAB, "runs": [{**r, "overall": None, "score_quality": None} for r in LAB["runs"]]})
    assert page.locator(".lab-row").count() == 0
    assert "No scores yet" in page.locator("#view").inner_text()


def test_lab_run_note_opens_and_goes_back(make_page, base_url):
    page = make_page()
    open_lab(page, base_url)
    page.locator("#view table").first.locator("a.cell").first.click()
    page.wait_for_function("document.querySelector('#view h2')?.textContent.includes('on Hermes')")
    assert page.url.endswith("#lab/2026-10-20_UC-001_hermes.md")
    view = page.locator("#view")
    assert view.locator(".note h4").inner_text() == "What happened"
    assert view.locator(".note code").inner_text() == "fast"
    assert "☑ Fetched the real inbox" in view.inner_text() and "☐ Changed nothing" in view.inner_text()
    assert "claude-opus-5-5" in view.inner_text()
    fields = view.locator("dl").inner_text()
    assert "Quality\n4 / 5" in fields and "Peak memory (MB)\n800" in fields and "Safety" not in fields  # unscored ones hidden
    assert page.evaluate("window.pwned") is None and view.locator("img").count() == 0  # notes render as text
    page.click("text=← Back")
    page.wait_for_selector("text=Scoreboard")
    assert page.url.endswith("#lab")
    assert page.locator("nav a[aria-current=page]").get_attribute("data-tab") == "lab"


def test_lab_deep_link_to_unknown_note(make_page, base_url):
    page = make_page()
    open_lab(page, base_url, hash="lab/nope.md")
    assert "No run note called nope.md" in page.locator("#view").inner_text()


def test_lab_use_case_prompt_can_be_copied(make_page, base_url):
    page = make_page()
    open_lab(page, base_url)
    card = page.locator("#view .card:has(details)", has_text="UC-002 Pay bills")
    assert "money" in card.inner_text()
    card.locator("summary").click()
    card.locator(".copy").click()
    assert page.evaluate("navigator.clipboard.readText()") == "Find bills."


def test_lab_missing_shows_a_note(make_page, base_url):
    page = make_page()
    open_lab(page, base_url, {"found": False, "path": "~/dev/agent-lab"})
    assert "No agent lab at ~/dev/agent-lab" in page.locator("#view").inner_text()


@pytest.mark.parametrize("hash", ["lab", "lab/2026-10-20_UC-001_hermes.md"])
def test_lab_fits_phone(make_page, base_url, hash):
    page = make_page(*PHONE)
    open_lab(page, base_url, hash=hash)
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]


DASHBOARDS = [
    {"name": "Hermes", "what": "Web dashboard", "running": False, "start": "hermes dashboard --no-open", "tailnet_url": "",
     "publish": "tailscale serve --bg --https=8443 9119", "tunnel": "ssh -N -L 9119:localhost:9119 pi", "local_url": "http://localhost:9119/"},
    {"name": "OpenClaw", "what": "Control UI", "running": True, "start": "openclaw gateway run",
     "tailnet_url": "https://box.tail9.ts.net:8444/", "publish": "tailscale serve --bg --https=8444 18789",
     "tunnel": "ssh -N -L 18789:localhost:18789 pi", "local_url": "http://localhost:18789/"},
    {"name": "OpenHuman", "what": "Desktop app and TUI only"},
]


def test_agents_tab_links_dashboards(make_page, base_url):
    page = make_page()
    page.route("**/api/dashboards", lambda r: r.fulfill(json=DASHBOARDS))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .dashboard")
    cards = page.locator("#view .dashboard")
    hermes, openclaw, openhuman = (cards.nth(i).inner_text() for i in range(3))
    assert "not running" in hermes and "hermes dashboard --no-open" in hermes and "not published yet" in hermes
    assert page.locator("#view a[href='https://box.tail9.ts.net:8444/']").count() == 1
    assert "ssh -N -L 18789:localhost:18789 pi" in openclaw and "Start it" not in openclaw
    assert "no web UI" in openhuman and "ssh" not in openhuman
    assert page.errors == []


def test_agents_tab_survives_dashboard_failure(make_page, base_url):
    page = make_page()
    page.route("**/api/dashboards", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    open_tab(page, base_url, "agents")
    page.wait_for_function("document.querySelector('#view')?.textContent.includes('Running agents')")
    assert "Dashboard status unavailable" in page.locator("#view").inner_text()


def test_dashboards_fit_phone(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/dashboards", lambda r: r.fulfill(json=DASHBOARDS))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .dashboard")
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]
