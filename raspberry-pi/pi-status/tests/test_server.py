import json
import urllib.error
import urllib.request

import pytest

import pi_status


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status, r.headers["Content-Type"], r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers["Content-Type"], e.read()


@pytest.mark.parametrize("route", list(pi_status.ROUTES))
def test_api_routes_return_json(base_url, route):
    status, ctype, body = get(base_url + route)
    assert status == 200 and ctype == "application/json"
    assert json.loads(body) is not None


def test_index_page(base_url):
    status, ctype, body = get(base_url + "/")
    assert status == 200 and ctype.startswith("text/html")
    assert b"<nav" in body


def test_unknown_path_404(base_url):
    assert get(base_url + "/nope")[0] == 404


def test_query_string_ignored(base_url):
    assert get(base_url + "/api/ports?x=1")[0] == 200


def test_collector_error_returns_500_json_and_server_survives(base_url, monkeypatch):
    def boom():
        raise RuntimeError("kaput")
    monkeypatch.setitem(pi_status.ROUTES, "/api/ports", boom)
    status, _, body = get(base_url + "/api/ports")
    assert status == 500 and "kaput" in json.loads(body)["error"]
    monkeypatch.undo()
    assert get(base_url + "/api/ports")[0] == 200


def test_status_has_network_summary(base_url):
    data = json.loads(get(base_url + "/api/status")[2])
    assert data["local_ip"] and data["connection"]


# ---------- restart endpoint ----------

def post(url, headers=None):
    req = urllib.request.Request(url, method="POST", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.fixture
def restarts(monkeypatch):
    """Record restart requests instead of really restarting anything."""
    calls = []
    monkeypatch.setattr(pi_status.collect, "restart_service", lambda: calls.append(1))
    return calls


def wait_for(cond, seconds=3):
    import time
    end = time.time() + seconds
    while time.time() < end and not cond():
        time.sleep(0.02)
    return cond()


def test_restart_requires_the_custom_header(base_url, restarts, monkeypatch):
    monkeypatch.setattr(pi_status.collect, "can_restart", lambda: True)
    status, body = post(base_url + "/api/restart")                       # what a cross-site form post looks like
    assert status == 403 and "X-Requested-With" in body["error"]
    status, _ = post(base_url + "/api/restart", {"X-Requested-With": "something-else"})
    assert status == 403
    assert restarts == []


def test_restart_refused_when_not_under_systemd(base_url, restarts, monkeypatch):
    monkeypatch.setattr(pi_status.collect, "can_restart", lambda: False)
    status, body = post(base_url + "/api/restart", {"X-Requested-With": "pi-status"})
    assert status == 409 and "by hand" in body["error"]
    assert restarts == []


def test_restart_accepted_and_runs_after_the_reply(base_url, restarts, monkeypatch):
    monkeypatch.setattr(pi_status.collect, "can_restart", lambda: True)
    status, body = post(base_url + "/api/restart", {"X-Requested-With": "pi-status"})
    assert status == 202 and body == {"restarting": True}
    assert wait_for(lambda: restarts == [1])


def test_restart_is_not_available_as_a_get_or_unknown_post(base_url, restarts):
    assert get(base_url + "/api/restart")[0] == 404
    assert post(base_url + "/api/other", {"X-Requested-With": "pi-status"})[0] == 404
    assert restarts == []


def test_version_reports_can_restart(base_url, monkeypatch):
    monkeypatch.setattr(pi_status.collect, "can_restart", lambda: True)
    assert json.loads(get(base_url + "/api/version")[2])["can_restart"] is True
