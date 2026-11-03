import json
import os
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright

from mail_fixture import write_fresh
from pi_status import Handler, collect


@pytest.fixture(scope="session", autouse=True)
def fake_mail_state(tmp_path_factory):
    """Point /api/emails at the FAKE fixture for the whole run, so no test ever reads real mail, and the choice
    buttons at a `mail` command that doesn't exist, so none can touch it (tests that click use `fake_mail`)."""
    folder = tmp_path_factory.mktemp("mail")
    path = write_fresh(folder / "state.json")
    env = {collect.MAIL_STATE_ENV: str(path), collect.MAIL_BIN_ENV: str(folder / "no-mail-command-here")}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    yield path
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class FakeMail:
    """tests/fake_mail.py as the `mail` command, on a fresh copy of the fixture that it rewrites."""

    def __init__(self, folder):
        self.folder = folder
        self.state = write_fresh(folder / "state.json")
        self.exe = folder / "mail"
        self.exe.write_text(f"#!/bin/sh\nexec {sys.executable} {os.path.dirname(__file__)}/fake_mail.py \"$@\"\n")
        self.exe.chmod(0o755)

    def calls(self) -> list[list[str]]:
        log = self.folder / "calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def reply(self, code: int, out: dict | str) -> None:
        """Answer every call with this exit code and output instead of acting on the state file."""
        (self.folder / "reply.json").write_text(json.dumps({"exit": code, "stdout": out if isinstance(out, str) else json.dumps(out)}))


@pytest.fixture
def fake_mail(tmp_path, monkeypatch):
    fake = FakeMail(tmp_path)
    monkeypatch.setenv(collect.MAIL_STATE_ENV, str(fake.state))
    monkeypatch.setenv(collect.MAIL_BIN_ENV, str(fake.exe))
    monkeypatch.setenv("FAKE_MAIL_DIR", str(tmp_path))
    return fake


@pytest.fixture(scope="session")
def base_url():
    """The real server on a free localhost port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    # Prefer the system Chromium (apt); falls back to Playwright's own (`playwright install chromium`).
    exe = shutil.which("chromium") or shutil.which("chromium-browser")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture
def make_page(browser):
    """Open a page at a given viewport; collects console errors in page.errors."""
    contexts = []

    def make(width=1100, height=900):
        ctx = browser.new_context(viewport={"width": width, "height": height})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        contexts.append(ctx)
        page = ctx.new_page()
        page.errors = []
        page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        return page

    yield make
    for ctx in contexts:
        ctx.close()
