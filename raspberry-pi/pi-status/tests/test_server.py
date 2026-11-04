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


def test_rei_endpoint_shape(base_url, monkeypatch):
    monkeypatch.setattr(pi_status.collect, "rei_health",
                        lambda: {"reachable": True, "ok": True, "version": "v1", "errors": 0})
    status, ctype, body = get(base_url + "/api/rei")
    data = json.loads(body)
    assert status == 200 and ctype == "application/json"
    assert set(data) == {"units", "unit_state", "published", "health", "vault_sync", "url", "publish", "start", "folder"}
    assert set(data["vault_sync"]) == {"state", "last_sync", "last_failed"}


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


# ---------- agent start/stop endpoint ----------

@pytest.fixture
def controls(monkeypatch):
    """Record start/stop requests instead of touching real services."""
    calls = []
    monkeypatch.setattr(pi_status.collect, "control_agent",
                        lambda unit, action: (calls.append((unit, action)), (200, {"unit": unit, "state": "inactive"}))[1])
    return calls


def test_agent_control_requires_the_custom_header(base_url, controls):
    status, body = post(base_url + "/api/agents/hermes-dashboard.service/stop")
    assert status == 403 and "X-Requested-With" in body["error"]
    assert controls == []


def test_agent_control_passes_unit_and_action(base_url, controls):
    status, body = post(base_url + "/api/agents/openclaw-gateway.service/stop", {"X-Requested-With": "pi-status"})
    assert status == 200 and body["state"] == "inactive"
    assert controls == [("openclaw-gateway.service", "stop")]


def test_agent_control_only_start_and_stop(base_url, controls):
    assert post(base_url + "/api/agents/ssh.service/restart", {"X-Requested-With": "pi-status"})[0] == 404
    assert get(base_url + "/api/agents/ssh.service/stop")[0] == 404
    assert controls == []


def test_emails_endpoint_reads_the_fake_fixture_not_real_mail(base_url, fake_mail_state):
    assert pi_status.collect.mail_state_path() == fake_mail_state != pi_status.collect.MAIL_STATE
    status, ctype, body = get(base_url + "/api/emails")
    data = json.loads(body)
    assert status == 200 and ctype == "application/json"
    assert data["connected"] is True and data["needs_you"] == 3
    assert all(t["from_addr"].endswith(".example") for t in data["threads"])


def test_emails_endpoint_bad_json_is_200_with_an_error(base_url, tmp_path, monkeypatch):
    bad = tmp_path / "state.json"
    bad.write_text("{oops")
    monkeypatch.setenv(pi_status.collect.MAIL_STATE_ENV, str(bad))
    status, _, body = get(base_url + "/api/emails")
    assert status == 200 and "not valid JSON" in json.loads(body)["error"]


# ---------- email choices: POST /api/emails/<action> runs the (fake) mail command ----------

ACTION_ID, DELETE_ID = "000000000000a001", "000000000000de01"
WEB = ["--via", "web", "--json"]


def post_json(url, body, headers=None):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


HB = {"X-Requested-With": "pi-status"}


def test_mail_choices_require_the_custom_header(base_url, fake_mail):
    status, body = post_json(base_url + "/api/emails/decide", {"thread": ACTION_ID, "queue": "review"})
    assert status == 403 and "X-Requested-With" in body["error"]
    assert fake_mail.calls() == []


def test_mail_choices_are_not_gets(base_url, fake_mail):
    assert get(base_url + "/api/emails/decide")[0] == 404
    assert post_json(base_url + "/api/emails/archive", {"thread": ACTION_ID}, HB)[0] == 404
    assert fake_mail.calls() == []


@pytest.mark.parametrize("action, body, words", [
    ("decide", {"thread": "../etc", "queue": "review"}, "thread id"),
    ("decide", {"thread": "000000000000A001", "queue": "review"}, "thread id"),        # hex is lowercase
    ("decide", {"thread": "0123456789", "queue": "inbox"}, "queue must be"),            # not a choice
    ("decide", {"thread": "0123456789", "queue": "review --via cli"}, "queue must be"),
    ("decide", {"thread": "abc", "queue": "review"}, "thread id"),                       # too short
    ("undo", {"thread": "f" * 25}, "thread id"),                                         # too long
    ("undo", {"thread": 12345678901}, "thread id"),
    ("trash", {"ids": []}, "non-empty list"),
    ("trash", {"ids": "000000000000de01"}, "non-empty list"),
    ("trash", {"ids": ["000000000000de01", "-rf"]}, "thread ids"),
    ("trash", {"ids": ["%014x" % i for i in range(501)]}, "at most 500"),
    ("decide", ["000000000000a001", "review"], "JSON object"),
])
def test_mail_choices_validate_input_and_run_nothing(base_url, fake_mail, action, body, words):
    status, out = post_json(f"{base_url}/api/emails/{action}", body, HB)
    assert status == 400 and out["ok"] is False and words in out["error"], out
    assert fake_mail.calls() == []


def test_mail_choices_refuse_bad_and_oversized_bodies(base_url, fake_mail):
    assert post_json(base_url + "/api/emails/undo", b"{not json", HB)[0] == 400
    assert post_json(base_url + "/api/emails/undo", b"", HB)[0] == 400
    big = json.dumps({"ids": ["0" * 24] * 2600}).encode()   # > 64 KB
    assert post_json(base_url + "/api/emails/trash", big, HB)[0] == 413
    assert fake_mail.calls() == []


def test_mail_decide_runs_the_command_and_returns_the_new_state(base_url, fake_mail):
    status, out = post_json(base_url + "/api/emails/decide", {"thread": ACTION_ID, "queue": "review"}, HB)
    assert status == 200 and out["ok"] is True
    assert fake_mail.calls() == [["decide", ACTION_ID, "review", *WEB]]
    thread = next(t for t in out["state"]["threads"] if t["id"] == ACTION_ID)
    assert thread["queue"] == "review" and thread["decided"]["via"] == "web"
    assert out["state"]["needs_you"] == 2 and out["state"]["connected"] is True


def test_mail_undo_and_trash_arguments(base_url, fake_mail):
    assert post_json(base_url + "/api/emails/undo", {"thread": DELETE_ID}, HB)[0] == 200
    fake_mail.reply(0, {"ok": True, "trashed": 1})
    assert post_json(base_url + "/api/emails/trash", {"ids": [DELETE_ID, DELETE_ID]}, HB)[0] == 200
    assert fake_mail.calls() == [["undo", DELETE_ID, *WEB], ["trash", "--yes", DELETE_ID, *WEB]]   # duplicates dropped


def test_mail_reason_arguments_and_checks(base_url, fake_mail):
    fake_mail.reply(0, {"ok": True})
    assert post_json(base_url + "/api/emails/reason", {"thread": ACTION_ID, "text": "--yes  two\nlines"}, HB)[0] == 200
    assert fake_mail.calls() == [["reason", ACTION_ID, "--yes two lines", *WEB]]     # one line, passed as one argument
    for bad in ({"thread": ACTION_ID}, {"thread": ACTION_ID, "text": "x" * 501}, {"thread": "nope", "text": "x"}):
        assert post_json(base_url + "/api/emails/reason", bad, HB)[0] == 400
    assert len(fake_mail.calls()) == 1


def test_mail_accept_arguments_and_checks(base_url, fake_mail):
    items = [{"thread": ACTION_ID, "queue": "action"}, {"thread": DELETE_ID, "queue": "delete"},
             {"thread": ACTION_ID, "queue": "action"}]
    assert post_json(base_url + "/api/emails/accept", {"items": items}, HB)[0] == 200
    assert fake_mail.calls() == [["accept", f"{ACTION_ID}:action", f"{DELETE_ID}:delete", *WEB]]   # duplicates dropped
    for bad in ([], [{"thread": ACTION_ID, "queue": "later"}], [{"thread": "x; rm -rf", "queue": "action"}], ["a001"]):
        status, out = post_json(base_url + "/api/emails/accept", {"items": bad}, HB)
        assert status == 400 and out["ok"] is False
    assert len(fake_mail.calls()) == 1                                                  # refused ones never ran


def test_mail_draft_arguments_and_checks(base_url, fake_mail):
    fake_mail.reply(0, {"ok": True})
    url = base_url + "/api/emails/"
    assert post_json(url + "draft", {"thread": ACTION_ID}, HB)[0] == 200
    assert post_json(url + "draft", {"thread": ACTION_ID, "note": " --json  yes\n"}, HB)[0] == 200
    text = "--yes\nHi,\n\nFine.\n"
    assert post_json(url + "draft-save", {"thread": ACTION_ID, "text": text}, HB)[0] == 200
    assert post_json(url + "draft-drop", {"thread": ACTION_ID}, HB)[0] == 200
    assert fake_mail.calls() == [["draft", ACTION_ID, *WEB], ["draft", ACTION_ID, "--note", "--json yes", *WEB],
                                 ["draft-save", ACTION_ID, text, *WEB], ["draft-drop", ACTION_ID, *WEB]]  # line breaks kept
    for action, bad in [("draft", {"thread": "x"}), ("draft", {"thread": ACTION_ID, "note": "x" * 501}),
                        ("draft", {"thread": ACTION_ID, "note": 3}), ("draft-save", {"thread": ACTION_ID}),
                        ("draft-save", {"thread": ACTION_ID, "text": " \n "}),
                        ("draft-save", {"thread": ACTION_ID, "text": "x" * 8001}), ("draft-drop", {})]:
        assert post_json(url + action, bad, HB)[0] == 400, (action, bad)
    assert len(fake_mail.calls()) == 4


def test_mail_draft_does_not_wait_for_other_choices(base_url, fake_mail):
    with pi_status.collect.mail_lock:              # a long choice is running; Claude writing a draft doesn't queue behind it
        assert post_json(base_url + "/api/emails/draft", {"thread": ACTION_ID}, HB)[0] == 200


@pytest.mark.parametrize("code, status", [(5, 409), (2, 401), (1, 502), (3, 400), (7, 500)])
def test_mail_failures_map_to_http_status_with_the_error_and_state(base_url, fake_mail, code, status):
    fake_mail.reply(code, {"ok": False, "error": f"failed with {code}"})
    got, out = post_json(base_url + "/api/emails/decide", {"thread": ACTION_ID, "queue": "delete"}, HB)
    assert got == status and out["ok"] is False and out["error"] == f"failed with {code}"
    assert out["state"]["connected"] is True


def test_mail_unreadable_output_is_an_error(base_url, fake_mail):
    fake_mail.reply(1, "Traceback (most recent call last): boom")
    status, out = post_json(base_url + "/api/emails/undo", {"thread": ACTION_ID}, HB)
    assert status == 502 and out["ok"] is False and "mail undo failed" in out["error"]


def test_mail_missing_command_is_503(base_url):
    # the session default: a mail command that doesn't exist, so nothing real can run in tests
    status, out = post_json(base_url + "/api/emails/undo", {"thread": ACTION_ID}, HB)
    assert status == 503 and "isn't installed" in out["error"]


def test_mail_sync_now_starts_once_and_reports_running(base_url, monkeypatch):
    running = {"now": False, "started": 0}

    def start():
        running["started"] += 1
        running["now"] = True
    monkeypatch.setattr(pi_status.collect, "mail_syncing", lambda: running["now"])
    monkeypatch.setattr(pi_status.collect, "mail_sync_start", start)
    status, out = post_json(base_url + "/api/emails/sync", {}, HB)
    assert status == 202 and out["ok"] is True and out["state"]["syncing"] is True
    assert post_json(base_url + "/api/emails/sync", {}, HB)[0] == 202
    assert running["started"] == 1                                   # already running: not started twice
    assert post_json(base_url + "/api/emails/sync", {})[0] == 403    # the custom header, as for every POST


def test_mail_sync_now_start_failure_is_500(base_url, monkeypatch):
    monkeypatch.setattr(pi_status.collect, "mail_syncing", lambda: False)
    monkeypatch.setattr(pi_status.collect, "mail_sync_start", lambda: "Failed to connect to bus")
    status, out = post_json(base_url + "/api/emails/sync", {}, HB)
    assert status == 500 and out["error"] == "couldn't start the mail sorter: Failed to connect to bus"


def test_mail_tests_never_point_at_the_real_sorter_unit():
    assert pi_status.collect.mail_unit() == "pi-status-test-no-such-unit.service"
    assert pi_status.collect.mail_syncing() is False
