"""Renders the real page in Chromium via Playwright."""

import pytest

TABS = ["overview", "agents", "lab", "network", "system/services", "system/processes", "system/ports", "system/docker"]
NAV = ["Overview", "Agents", "Agent Lab", "Network", "System"]
SYSTEM = ["docker", "services", "processes", "ports"]
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
    assert page.locator("nav a[aria-current=page]").get_attribute("data-tab") == tab.split("/")[0]
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
    open_tab(page, base_url, "system/ports")
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


def test_pihole_url_is_a_link_with_copy(make_page, base_url):
    url = "https://box.tail9.ts.net:8445/admin/"
    data = {"installed": True, "running": True, "pihole": {"url": url, "publish": ""}, "containers": [
        {"name": "pihole", "image": "pihole/pihole", "state": "running", "status": "Up", "ports": "8081->80/tcp"}]}
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, "system/docker")
    assert page.locator(".pihole-row a").get_attribute("href") == url
    assert page.locator(".pihole-row a").get_attribute("target") == "_blank"  # opens in a new tab
    page.locator(".pihole-row .copy").click()
    assert page.evaluate("navigator.clipboard.readText()") == url


def test_pihole_publish_command_when_not_published(make_page, base_url):
    cmd = "sudo tailscale serve --bg --https=8445 8081"
    data = {"installed": True, "running": True, "pihole": {"url": "", "publish": cmd}, "containers": [
        {"name": "pihole", "image": "pihole/pihole", "state": "running", "status": "Up", "ports": "8081->80/tcp"}]}
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, "system/docker")
    assert page.locator(".pihole-row code").inner_text() == cmd
    assert page.locator(".pihole-row a").count() == 0


def test_pihole_url_hidden_when_not_running(make_page, base_url):
    data = {"installed": True, "running": True, "pihole": {"url": "", "publish": ""}, "containers": [
        {"name": "web", "image": "nginx", "state": "running", "status": "Up", "ports": ""}]}
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, "system/docker")
    page.wait_for_selector("table")
    assert page.locator(".pihole-row").count() == 0


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
    page.wait_for_selector("#view .agent")
    assert page.evaluate("window.pwned") is None
    assert page.locator("#view img").count() == 0
    assert evil in page.locator("#view .agent").text_content()


def test_docker_not_installed_message(make_page, base_url):
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json={"installed": False, "containers": []}))
    open_tab(page, base_url, "system/docker")
    assert "isn't installed" in page.locator("#view").inner_text()


def test_docker_containers_table(make_page, base_url):
    data = {"installed": True, "containers": [
        {"name": "web", "image": "nginx", "state": "running", "status": "Up 2h", "ports": "80/tcp"}]}
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, "system/docker")
    page.wait_for_selector("#view table")
    assert "web" in page.locator("#view tbody").inner_text() and "nginx" in page.locator("#view tbody").inner_text()


def test_process_sort_toggle(make_page, base_url):
    procs = {"total": 3, "processes": [
        {"pid": 1, "user": "u", "cpu": 90.0, "rss": 2**20, "age_s": 1, "cmd": "cpuhog"},
        {"pid": 2, "user": "u", "cpu": 1.0, "rss": 2**30, "age_s": 1, "cmd": "memhog"}]}
    page = make_page()
    page.route("**/api/processes", lambda r: r.fulfill(json=procs))
    open_tab(page, base_url, "system/processes")
    page.wait_for_selector("#view tbody tr")
    assert "cpuhog" in page.locator("#view tbody tr").first.inner_text()
    page.click("text=Top by memory")
    page.wait_for_function("document.querySelector('#view tbody tr')?.textContent.includes('memhog')")


def test_api_failure_shows_unreachable(make_page, base_url):
    page = make_page()
    page.route("**/api/ports", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    open_tab_ports = f"{base_url}/#system/ports"
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
    page.wait_for_selector("#view .signins table")
    text = page.locator("#view").inner_text()
    for expected in ["Sign-ins", "Google Cloud", "gcloud", "Google Workspace", "gws", "gh", "me@x.com", "project demo",
                     "signed in", "expired", "signed out", "not installed"]:
        assert expected in text
    assert page.errors == []


def test_agents_tab_survives_sign_in_failure(make_page, base_url):
    page = make_page()
    page.route("**/api/auth", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .agent")
    assert "Sign-in status unavailable" in page.locator("#view").inner_text()
    assert "Claude Code" in page.locator("#view").inner_text()  # the agent list still renders


def test_sign_in_table_fits_phone(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/auth", lambda r: r.fulfill(json=AUTH))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .signins table")
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
    open_tab(page, base_url, "system/ports")
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    assert seen.count("ports") == 1 and seen.count("version") == 1


def test_refresh_button_reloads_the_current_tab(make_page, base_url):
    page = make_page()
    seen = count_api_requests(page)
    open_tab(page, base_url, "system/ports")
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


def proc(pid, cwd="~", ports=(), cmd="x", age_s=900, rss=400 * 2**20):
    return {"pid": pid, "user": "guy", "cpu": 1.5, "rss": rss, "age_s": age_s, "cwd": cwd, "ports": list(ports), "cmd": cmd}


AGENTS = [
    {"name": "Claude Code", "kind": "Coding agent", "instances": [
        proc(11, "~/dev/pi-status", cmd="claude --model=opus"), proc(12, "~/dev", cmd="claude --model=sonnet", age_s=60)]},
    {"name": "OpenHuman", "kind": "Personal assistant", "unit": "openhuman.service", "unit_state": "inactive", "instances": []},
    {"name": "Hermes", "kind": "Agent", "unit": "hermes-dashboard.service", "unit_state": "active",   # up, port not open yet
     "instances": [proc(21, cmd="hermes dashboard --no-open")]},
    {"name": "OpenClaw", "kind": "Personal assistant", "unit": "openclaw-gateway.service", "unit_state": "active",
     "instances": [proc(31, ports=["127.0.0.1:18789"], cmd="openclaw-gateway")]},
]

DASHBOARDS = [
    {"name": "Hermes", "what": "Web dashboard", "running": False, "tailnet_url": "https://box.tail9.ts.net:8443/",
     "publish": "tailscale serve --bg --https=8443 9119", "tunnel": "ssh -N -L 9119:localhost:9119 pi", "local_url": "http://localhost:9119/"},
    {"name": "OpenClaw", "what": "Control UI", "running": True, "tailnet_url": "https://box.tail9.ts.net:8444/",
     "publish": "tailscale serve --bg --https=8444 18789", "tunnel": "ssh -N -L 18789:localhost:18789 pi", "local_url": "http://localhost:18789/"},
    {"name": "OpenHuman", "what": "Desktop app and TUI only; no web dashboard yet"},
]

SIGNED_IN = {"checked_at": 0, "services": [{**s, "state": "signed_in"} for s in AUTH["services"]]}


def open_agents(page, base_url, agents=AGENTS, dash=DASHBOARDS, auth=SIGNED_IN):
    page.route("**/api/agents", lambda r: r.fulfill(json=agents))
    page.route("**/api/dashboards", lambda r: r.fulfill(json=dash))
    page.route("**/api/auth", lambda r: r.fulfill(json=auth))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .agent")
    return {c.locator(".card-head h4").inner_text(): c for c in page.locator("#view .agent").all()}


def test_each_agent_appears_once(make_page, base_url):
    page = make_page()
    cards = open_agents(page, base_url)
    names = page.locator("#view .agent .card-head h4").all_inner_texts()
    assert sorted(names) == sorted({"Claude Code", "OpenHuman", "Hermes", "OpenClaw"})
    assert names[-1] == "OpenHuman"   # running ones first, stopped last
    assert page.locator("#view .dashboard").count() == 0
    assert "Start it on the Pi" not in page.locator("#view").text_content()  # the Start button replaces it
    after = page.evaluate("[...document.querySelectorAll('#view .agent')].pop().compareDocumentPosition(document.querySelector('#view .signins'))")
    assert after & 4, "sign-ins come after the agent cards"
    assert page.errors == []


def test_agent_status_words(make_page, base_url):
    page = make_page()
    cards = open_agents(page, base_url)
    pills = {name: c.locator(".card-head .pill").all_inner_texts() for name, c in cards.items()}
    assert pills == {"Claude Code": ["running · 2"], "OpenClaw": ["running"],
                     "Hermes": ["starting"],      # its unit is active, its dashboard port isn't listening yet
                     "OpenHuman": ["stopped"]}    # one pill each: no separate unit-state pill


def test_published_dashboards_link_to_their_tailnet_url(make_page, base_url):
    page = make_page()
    cards = open_agents(page, base_url)
    link = cards["OpenClaw"].locator("a[href='https://box.tail9.ts.net:8444/']")
    assert link.inner_text() == "https://box.tail9.ts.net:8444/" and link.get_attribute("target") == "_blank"
    assert "On your tailnet" in cards["OpenClaw"].inner_text() and "once it's running" not in cards["OpenClaw"].inner_text()
    assert cards["Hermes"].locator("a[href='https://box.tail9.ts.net:8443/']").count() == 1  # published, still starting
    assert page.locator("#view a[href^='https://box.tail9.ts.net']").count() == 2           # once per agent
    cards["OpenClaw"].locator(".ssh-row:has(a[href='https://box.tail9.ts.net:8444/']) .copy").click()
    assert page.evaluate("navigator.clipboard.readText()") == "https://box.tail9.ts.net:8444/"


def test_stopped_agent_keeps_its_tailnet_link(make_page, base_url):
    stopped = [{**a, "unit_state": "inactive", "instances": []} if a["name"] == "OpenClaw" else a for a in AGENTS]
    dash = [{**d, "running": False} if d["name"] == "OpenClaw" else d for d in DASHBOARDS]
    page = make_page()
    claw = open_agents(page, base_url, stopped, dash)["OpenClaw"]
    assert claw.locator(".card-head .pill").inner_text() == "stopped"
    assert claw.locator(".service-btn").inner_text() == "Start"
    assert claw.locator("a[href='https://box.tail9.ts.net:8444/']").count() == 1
    assert "On your tailnet (once it's running)" in claw.inner_text()


def test_unpublished_dashboard_shows_the_publish_command(make_page, base_url):
    dash = [{**d, "tailnet_url": ""} if d["name"] == "Hermes" else d for d in DASHBOARDS]
    page = make_page()
    cards = open_agents(page, base_url, dash=dash)
    text = cards["Hermes"].inner_text()
    assert "not published yet" in text and "tailscale serve --bg --https=8443 9119" in text


def test_agent_reference_details_are_under_more(make_page, base_url):
    page = make_page()
    claw = open_agents(page, base_url)["OpenClaw"]
    assert "ssh -N -L 18789" not in claw.inner_text()       # collapsed by default
    assert "up 15m · 1.5% CPU · 400 MB" in claw.inner_text()  # the summary line stays visible
    claw.locator("summary", has_text="More").click()
    text = claw.inner_text()
    for expected in ["ssh -N -L 18789:localhost:18789 pi", "http://localhost:18789/", "openclaw-gateway.service", "127.0.0.1:18789"]:
        assert expected in text
    assert claw.locator("table").count() == 1               # the process table


def test_no_web_ui_agent_says_so(make_page, base_url):
    page = make_page()
    human = open_agents(page, base_url)["OpenHuman"]
    assert "no web dashboard yet" in human.inner_text() and "ssh" not in human.text_content()


def test_claude_code_has_one_row_per_session(make_page, base_url):
    page = make_page()
    claude = open_agents(page, base_url)["Claude Code"]
    rows = claude.locator(".session")
    assert rows.count() == 2
    assert "~/dev/pi-status" in rows.nth(0).inner_text() and "up 15m" in rows.nth(0).inner_text() and "400 MB" in rows.nth(0).inner_text()
    assert "claude --model=opus" not in rows.nth(0).inner_text()  # the full command is one click away
    rows.nth(0).locator("summary").click()
    assert "claude --model=opus" in rows.nth(0).inner_text()


def test_sign_ins_collapse_to_one_line_when_all_signed_in(make_page, base_url):
    page = make_page()
    open_agents(page, base_url)
    box = page.locator("#view .signins details")
    assert box.get_attribute("open") is None
    assert box.locator("summary").inner_text().startswith("4 of 4 signed in · checked ")


def test_sign_ins_open_when_one_is_expired(make_page, base_url):
    page = make_page()
    open_agents(page, base_url, auth=AUTH)
    box = page.locator("#view .signins details")
    assert box.get_attribute("open") is not None
    assert box.locator("summary").inner_text().startswith("1 of 4 signed in")
    assert "expired" in box.inner_text()


def test_agents_tab_survives_dashboard_failure(make_page, base_url):
    page = make_page()
    page.route("**/api/agents", lambda r: r.fulfill(json=AGENTS))
    page.route("**/api/dashboards", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .agent")
    assert "Dashboard status unavailable" in page.locator("#view").inner_text()
    assert page.locator("#view .agent").count() == 4
    assert page.locator("#view .agent", has_text="Hermes").locator(".card-head .pill").inner_text() == "running"  # the unit says so


def test_status_stays_next_to_its_button_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    cards = open_agents(page, base_url)
    for name in ("OpenClaw", "OpenHuman", "Hermes"):
        # both boxes in one call: the sidebar loading in between can shift the whole view
        middles = cards[name].evaluate("""c => [".card-head .pill", ".service-btn"].map(s => {
            const b = c.querySelector(s).getBoundingClientRect(); return b.top + b.height / 2; })""")
        assert abs(middles[0] - middles[1]) < 4, f"{name}: split across lines"


def test_agent_cards_fit_phone(make_page, base_url):
    page = make_page(*PHONE)
    open_agents(page, base_url, auth=AUTH)
    page.evaluate("document.querySelectorAll('#view details').forEach(d => d.open = true)")
    assert page.evaluate(OVERFLOWING) == []


SERVICE_AGENTS = [
    {"name": "Hermes", "kind": "Agent", "unit": "hermes-dashboard.service", "unit_state": "active", "instances": [
        {"pid": 7, "user": "guy", "cpu": 0.0, "rss": 2**20, "age_s": 9, "cwd": "~", "ports": [], "cmd": "hermes dashboard"}]},
    {"name": "OpenClaw", "kind": "Personal assistant", "unit": "openclaw-gateway.service", "unit_state": "inactive", "instances": []},
    {"name": "Claude Code", "kind": "Coding agent", "instances": []},
]


def test_agent_cards_offer_stop_and_start(make_page, base_url):
    posts = []

    def control(route):
        posts.append((route.request.url, route.request.headers.get("x-requested-with")))
        route.fulfill(json={"unit": "hermes-dashboard.service", "state": "inactive"})
    page = make_page()
    page.route("**/api/agents", lambda r: r.fulfill(json=SERVICE_AGENTS))
    page.route("**/api/agents/*/*", control)
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .service-btn")
    cards = page.locator("#view .agent")
    assert cards.filter(has_text="Hermes").locator(".service-btn").inner_text() == "Stop"
    assert cards.filter(has_text="OpenClaw").locator(".service-btn").inner_text() == "Start"
    assert cards.filter(has_text="Claude Code").locator(".service-btn").count() == 0  # no service to control
    cards.filter(has_text="Hermes").locator(".service-btn").click()
    page.wait_for_function("document.getElementById('conn').textContent.startsWith('updated')")
    page.wait_for_timeout(300)
    assert posts == [(f"{base_url}/api/agents/hermes-dashboard.service/stop", "pi-status")]
    assert page.errors == []


def test_failed_agent_control_shows_the_error(make_page, base_url):
    page = make_page()
    page.route("**/api/agents", lambda r: r.fulfill(json=SERVICE_AGENTS))
    page.route("**/api/agents/*/*", lambda r: r.fulfill(status=500, json={"error": "Unit not loaded."}))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .service-btn")
    page.locator("#view .agent", has_text="OpenClaw").locator(".service-btn").click()
    page.wait_for_selector("#view .alert")
    assert "Couldn't start openclaw-gateway.service: Unit not loaded." in page.locator("#view .alert").inner_text()


def test_dark_mode_uses_dark_scrollbars(make_page, base_url):
    page = make_page()
    open_tab(page, base_url, "overview")
    assert "dark" in page.evaluate("getComputedStyle(document.documentElement).colorScheme")


def line_count(page, selector):
    """How many lines the text of the first matching element wraps onto."""
    return page.evaluate("""s => { const r = document.createRange(); r.selectNodeContents(document.querySelector(s));
                                   return new Set([...r.getClientRects()].map(b => Math.round(b.top))).size; }""", selector)


def test_process_uptime_stays_on_one_line_on_phone(make_page, base_url):
    procs = {"total": 1, "processes": [
        {"pid": 4242, "user": "guy", "cpu": 1.0, "rss": 2**30, "age_s": 109800, "cmd": "node /usr/lib/node_modules/" + "x" * 200}]}
    page = make_page(*PHONE)
    page.route("**/api/processes", lambda r: r.fulfill(json=procs))
    open_tab(page, base_url, "system/processes")
    page.wait_for_selector("#view tbody td")
    assert page.locator("#view tbody td:nth-child(4)").first.inner_text() == "1d 6h 30m"
    assert line_count(page, "#view tbody td:nth-child(4)") == 1


def test_session_date_stays_on_one_line_on_phone(make_page, base_url):
    sessions = [{"user": "guy", "tty": "sshd pts/0", "since": "2026-10-20 09:01", "origin": "fd7a:115c:a1e0::1234:5678"}]
    page = make_page(*PHONE)
    page.route("**/api/network", lambda r: r.fulfill(json={**NETWORK, "sessions": sessions}))
    open_tab(page, base_url, "network")
    since = "#view > .card:last-child tbody td:nth-child(3)"  # the sessions table is the last card
    page.wait_for_selector(since)
    assert page.locator(since).inner_text() == "2026-10-20 09:01"
    assert line_count(page, since) == 1


# ---------- tables ----------

OVERFLOWING = """() => [...document.querySelectorAll('#view *')]
  .filter(e => !e.closest('.ssh-cmd') && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1)
  .map(e => `${e.tagName.toLowerCase()}.${e.className} ${e.scrollWidth}px in ${e.clientWidth}px`)"""

LONG_CMD = ("node /usr/lib/node_modules/openclaw/dist/index.js gateway --port 18789 --bind loopback --verbose "
            "--log-file /home/guy/.openclaw/logs/gateway.log --config /home/guy/.openclaw/openclaw.json --profile default")
PROCS = {"total": 1, "processes": [{"pid": 4242, "user": "guy", "cpu": 1.0, "rss": 2**30, "age_s": 109800, "cmd": LONG_CMD}]}


@pytest.mark.parametrize("tab", TABS)
def test_nothing_in_the_view_overflows_on_phone(make_page, base_url, tab):
    """Stricter than the page-width check: a table can't hide columns inside its own sideways-scrolling box."""
    page = make_page(*PHONE)
    open_tab(page, base_url, tab)
    page.wait_for_timeout(300)
    assert page.evaluate(OVERFLOWING) == []


@pytest.mark.parametrize("tab, api, data", [("network", "network", NETWORK), ("processes", "processes", PROCS)])
def test_nothing_overflows_on_phone_with_long_values(make_page, base_url, tab, api, data):
    page = make_page(*PHONE)
    page.route(f"**/api/{api}", lambda r: r.fulfill(json=data))
    open_tab(page, base_url, tab)
    page.wait_for_selector("#view tbody td")
    assert page.evaluate(OVERFLOWING) == []


def test_lab_does_not_overflow_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    open_lab(page, base_url)
    assert page.evaluate(OVERFLOWING) == []


def test_process_command_is_readable_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/processes", lambda r: r.fulfill(json=PROCS))
    open_tab(page, base_url, "system/processes")
    cmd = page.locator("#view td.cmd").first
    assert cmd.inner_text() == LONG_CMD
    box = cmd.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE[0]
    assert cmd.evaluate("e => e.scrollHeight <= e.clientHeight && e.scrollWidth <= e.clientWidth")  # wrapped, not clipped
    label = lambda td: td.evaluate("e => getComputedStyle(e, '::before').content")
    assert "Command" in label(cmd)                                     # each cell says what it is
    assert label(page.locator("#view tbody td").first) in ("none", "normal")  # the first one is the row's title


def test_cell_labels_use_the_header_text(make_page, base_url):
    page = make_page(*PHONE)
    open_lab(page, base_url)
    cells = page.locator("#view table").first.locator("tbody tr").first.locator("td")
    assert [cells.nth(i).get_attribute("data-label") for i in range(4)] == ["Use case", "OpenClaw", "Hermes", "OpenHuman"]


def test_long_command_wraps_to_two_lines_on_desktop(make_page, base_url):
    page = make_page(1100, 900)
    page.route("**/api/processes", lambda r: r.fulfill(json=PROCS))
    open_tab(page, base_url, "system/processes")
    cmd = page.locator("#view td.cmd").first
    lines = cmd.evaluate("""e => { const s = getComputedStyle(e);
        return Math.round((e.clientHeight - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom)) / parseFloat(s.lineHeight)); }""")
    assert lines == 2
    assert cmd.get_attribute("title") == LONG_CMD  # the rest is on hover


def test_columns_with_no_values_are_hidden(make_page, base_url):
    rows = [{"port": 22, "address": "0.0.0.0", "exposure": "all interfaces", "process": "", "pid": None},
            {"port": 53, "address": "127.0.0.1", "exposure": "local only", "process": "", "pid": None}]
    page = make_page()
    page.route("**/api/ports", lambda r: r.fulfill(json=rows))
    open_tab(page, base_url, "system/ports")
    assert page.locator("#view thead").inner_text().split("\n")[-1].strip().lower() != "process"
    assert "–" not in page.locator("#view tbody").inner_text()


def test_columns_with_some_values_are_kept(make_page, base_url):
    rows = [{"port": 22, "address": "0.0.0.0", "exposure": "all interfaces", "process": "", "pid": None},
            {"port": 7788, "address": "127.0.0.1", "exposure": "local only", "process": "openhuman-core", "pid": 9}]
    page = make_page()
    page.route("**/api/ports", lambda r: r.fulfill(json=rows))
    open_tab(page, base_url, "system/ports")
    assert "PROCESS" in page.locator("#view thead").inner_text().upper()
    assert "openhuman-core (9)" in page.locator("#view tbody").inner_text()


def test_lab_scoreboard_keeps_agents_without_runs(make_page, base_url):
    page = make_page()
    open_lab(page, base_url)
    head = page.locator("#view table").first.locator("thead").inner_text().upper()
    assert "OPENCLAW" in head and "OPENHUMAN" in head  # neither has a run yet; the "–" cells are the point


# ---------- navigation ----------

def test_nav_has_five_tabs(make_page, base_url):
    page = make_page()
    open_tab(page, base_url, "overview")
    assert page.locator("nav a").all_inner_texts() == NAV


def test_every_nav_link_is_on_screen_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    open_tab(page, base_url, "overview")
    for link in page.locator("nav a").all():
        box = link.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE[0], f"{link.inner_text()} is off-screen"


def status():
    """Just what the sidebar reads from /api/status on a System tab."""
    return {"hostname": "box", "model": "Raspberry Pi 5"}


def subtab(page):
    return page.locator("#view .subtabs a[aria-current=page]").inner_text()


@pytest.mark.parametrize("sub", SYSTEM)
def test_system_sub_tabs_mark_system_and_themselves(make_page, base_url, sub):
    page = make_page()
    page.route("**/api/status", lambda r: r.fulfill(json=status()))
    open_tab(page, base_url, f"system/{sub}")
    assert page.locator("nav a[aria-current=page]").get_attribute("data-tab") == "system"
    assert subtab(page) == sub.capitalize()
    assert page.locator("#view h2").inner_text() == "System"


def test_system_opens_on_docker(make_page, base_url):
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json={"installed": True, "running": False, "containers": []}))
    seen = count_api_requests(page)
    open_tab(page, base_url, "system")
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    assert subtab(page) == "Docker" and "isn't running" in page.locator("#view").inner_text()
    assert seen.count("docker") == 1


def test_sub_tab_links_switch_views(make_page, base_url):
    page = make_page()
    open_tab(page, base_url, "system/services")
    page.click("#view .subtabs a:text('Processes')")
    page.wait_for_selector("#view .seg button:text('Top by CPU')")
    assert page.url.endswith("#system/processes") and subtab(page) == "Processes"


@pytest.mark.parametrize("old", SYSTEM)
def test_old_hashes_redirect_to_system(make_page, base_url, old):
    page = make_page()
    seen = count_api_requests(page)
    page.goto(f"{base_url}/#{old}")
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    assert page.url.endswith(f"#system/{old}")
    assert page.locator("nav a[aria-current=page]").get_attribute("data-tab") == "system"
    assert seen.count(old) == 1   # the redirect doesn't load the view twice


def test_docker_sub_tab_always_listed(make_page, base_url):
    page = make_page()
    page.route("**/api/status", lambda r: r.fulfill(json=status()))
    open_tab(page, base_url, "system/services")
    assert page.locator("#view .subtabs a").all_inner_texts() == ["Docker", "Services", "Processes", "Ports"]


def test_docker_not_running_message(make_page, base_url):
    page = make_page()
    page.route("**/api/docker", lambda r: r.fulfill(json={"installed": True, "running": False, "containers": []}))
    open_tab(page, base_url, "system/docker")
    assert "isn't running" in page.locator("#view").inner_text()


# ---------- overview: needs attention and the agent strip ----------

NO_SERVICES = {"user": [], "system": []}
FAILED_UNIT = {"unit": "backup.service", "active": "failed", "sub": "failed", "description": "Nightly backup"}


def open_overview(page, base_url, status=STATUS, agents=SERVICE_AGENTS, auth=SIGNED_IN, services=NO_SERVICES,
                  version=VERSION, dash=DASHBOARDS):
    page.route("**/api/status", lambda r: r.fulfill(json=status))
    page.route("**/api/agents", lambda r: r.fulfill(json=agents))
    page.route("**/api/auth", lambda r: r.fulfill(json=auth))
    page.route("**/api/services", lambda r: r.fulfill(json=services))
    page.route("**/api/dashboards", lambda r: r.fulfill(json=dash))
    page.route("**/api/version", lambda r: r.fulfill(json=version))
    open_tab(page, base_url, "overview")
    page.wait_for_selector("#view .strip")
    page.wait_for_function("document.getElementById('version').textContent.includes('a1b2c3d')")


def attention(page):
    return page.locator("#view .attention li").all_inner_texts()


def test_overview_has_no_attention_list_when_all_is_well(make_page, base_url):
    page = make_page()
    open_overview(page, base_url)
    assert attention(page) == [] and not page.locator("#view .attention").is_visible()
    assert page.errors == []


@pytest.mark.parametrize("change, expected", [
    ({"status": {**STATUS, "throttled": ["under-voltage now"]}}, "Power/thermal: under-voltage now"),
    ({"auth": AUTH}, "Google Workspace sign-in expired"),
    ({"services": {"user": [FAILED_UNIT], "system": []}}, "backup.service failed"),
    ({"version": {**VERSION, "stale": True}}, "Newer pi-status code on disk"),
    ({"agents": [{**SERVICE_AGENTS[1], "unit_state": "failed"}]}, "OpenClaw failed"),
])
def test_overview_attention_lists_what_needs_you(make_page, base_url, change, expected):
    page = make_page()
    open_overview(page, base_url, **change)
    page.wait_for_selector("#view .attention li")
    assert any(expected in line for line in attention(page)), attention(page)


def test_attention_lists_each_problem_once(make_page, base_url):
    """A failed agent unit is also a failed user service; it's listed once, as the agent."""
    page = make_page()
    agent_unit = {**FAILED_UNIT, "unit": "openclaw-gateway.service"}
    open_overview(page, base_url, agents=[{**SERVICE_AGENTS[1], "unit_state": "failed"}],
                  services={"user": [agent_unit], "system": []}, auth=AUTH)
    lines = attention(page)
    assert sum("openclaw" in line.lower() for line in lines) == 1, lines
    assert "GitHub sign-in signed out" not in lines and any(line.startswith("GitHub") for line in lines)
    assert not any("Claude Code" in line for line in lines)   # "not installed" isn't a problem


def test_attention_links_to_where_it_is_fixed(make_page, base_url):
    page = make_page()
    open_overview(page, base_url, auth=AUTH, services={"user": [FAILED_UNIT], "system": []})
    assert page.locator("#view .attention a[href='#agents']").count() >= 1
    assert page.locator("#view .attention a[href='#system/services']").count() == 1


def test_overview_strip_shows_each_agent_with_its_status(make_page, base_url):
    page = make_page()
    open_overview(page, base_url, agents=AGENTS)
    rows = page.locator("#view .strip .strip-row")
    assert rows.count() == 4
    text = page.locator("#view .strip").inner_text()
    for word in ["Claude Code", "running · 2", "Hermes", "starting", "OpenClaw", "running", "OpenHuman", "stopped"]:
        assert word in text
    assert page.locator("#view .strip a[href='#agents']").count() == 4   # each name opens the Agents tab


def test_overview_strip_start_posts_to_the_unit(make_page, base_url):
    posts = []

    def control(route):
        posts.append(route.request.url)
        route.fulfill(json={"unit": "openclaw-gateway.service", "state": "active"})
    page = make_page()
    page.route("**/api/agents/*/*", control)
    open_overview(page, base_url)
    page.locator("#view .strip-row", has_text="OpenClaw").locator(".service-btn").click()
    page.wait_for_timeout(500)
    assert posts == [f"{base_url}/api/agents/openclaw-gateway.service/start"]


def test_overview_survives_agent_and_sign_in_failures(make_page, base_url):
    page = make_page()
    for api in ["agents", "auth", "services", "dashboards"]:
        page.route(f"**/api/{api}", lambda r: r.fulfill(status=500, json={"error": "boom"}))
    page.route("**/api/status", lambda r: r.fulfill(json=STATUS))
    open_tab(page, base_url, "overview")
    page.wait_for_selector("#view .grid")
    assert "Agent status unavailable" in page.locator("#view").inner_text()
    assert "Raspberry Pi 5 Model B Rev 1.0" in page.locator("#view dl").inner_text()


def test_overview_visit_fetches_each_api_once(make_page, base_url):
    page = make_page()
    seen = count_api_requests(page)
    open_overview(page, base_url)
    page.wait_for_function("document.getElementById('conn').textContent.includes('updated')")
    for api in ["status", "agents", "auth", "services", "dashboards", "version"]:
        assert seen.count(api) == 1, (api, seen)


# ---------- polish: labels, headings, touch targets, times, phone header ----------

def test_copy_buttons_say_what_they_copy(make_page, base_url):
    page = make_page()
    open_agents(page, base_url)
    page.evaluate("document.querySelectorAll('#view details').forEach(d => d.open = true)")
    labels = page.locator("#view button.copy:not(.service-btn)").evaluate_all("bs => bs.map(b => b.getAttribute('aria-label'))")
    assert labels and all(labels), labels
    assert len(set(labels)) == len(labels), "two Copy buttons read the same"
    assert "Copy OpenClaw tailnet address" in labels and "Copy OpenClaw SSH tunnel command" in labels


def test_network_copy_buttons_say_what_they_copy(make_page, base_url):
    page = make_page()
    page.route("**/api/network", lambda r: r.fulfill(json=NETWORK))
    open_tab(page, base_url, "network")
    page.wait_for_selector(".ssh-row")
    labels = page.locator("#view button.copy").evaluate_all("bs => bs.map(b => b.getAttribute('aria-label'))")
    assert all(labels) and len(set(labels)) == len(labels), labels
    assert "Copy SSH command: Over Tailscale (from anywhere)" in labels


def test_start_and_stop_buttons_name_their_agent(make_page, base_url):
    page = make_page()
    page.route("**/api/agents", lambda r: r.fulfill(json=SERVICE_AGENTS))
    open_tab(page, base_url, "agents")
    page.wait_for_selector("#view .service-btn")
    labels = page.locator("#view .service-btn").evaluate_all("bs => bs.map(b => b.getAttribute('aria-label'))")
    assert sorted(labels) == ["Start OpenClaw", "Stop Hermes"]


def test_card_titles_are_headings(make_page, base_url):
    page = make_page()
    open_agents(page, base_url)
    assert page.locator("#view .agent h4").all_inner_texts().count("OpenClaw") == 1
    assert page.locator("#view .agent .card-head strong").count() == 0


def test_buttons_are_bigger_on_touch_screens(browser, base_url):
    ctx = browser.new_context(viewport={"width": PHONE[0], "height": PHONE[1]}, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    try:
        page.route("**/api/agents", lambda r: r.fulfill(json=SERVICE_AGENTS))
        open_tab(page, base_url, "agents")
        page.wait_for_selector("#view .service-btn")
        assert page.evaluate("matchMedia('(pointer: coarse)').matches")
        for sel in ["#refresh", "#view .service-btn"]:
            assert page.locator(sel).first.bounding_box()["height"] >= 36, sel
    finally:
        ctx.close()


def test_buttons_stay_compact_with_a_mouse(make_page, base_url):
    page = make_page()
    open_tab(page, base_url, "overview")
    assert page.locator("#refresh").bounding_box()["height"] < 36


def test_sign_in_check_time_has_the_clock_time_on_hover(make_page, base_url):
    page = make_page()
    open_agents(page, base_url, auth={**SIGNED_IN, "checked_at": 1_800_000_000})
    title = page.locator("#view .signins summary").get_attribute("title")
    assert title and title.startswith("checked at ")


def test_version_shares_the_status_line_on_phone(make_page, base_url):
    page = make_page(*PHONE)
    page.route("**/api/version", lambda r: r.fulfill(json=VERSION))
    open_tab(page, base_url, "overview")
    page.wait_for_function("document.getElementById('version').textContent.includes('a1b2c3d')")
    conn, version, nav = (page.locator(s).bounding_box() for s in ["#conn", "#version", "nav"])
    assert abs(version["y"] - conn["y"]) < 12, (conn, version)   # same line as "updated ..."
    assert version["y"] < nav["y"]
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1]
