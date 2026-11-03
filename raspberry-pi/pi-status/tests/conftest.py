import os
import shutil
import threading
from http.server import ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright

from mail_fixture import write_fresh
from pi_status import Handler, collect


@pytest.fixture(scope="session", autouse=True)
def fake_mail_state(tmp_path_factory):
    """Point /api/emails at the FAKE fixture for the whole run, so no test ever reads real mail."""
    path = write_fresh(tmp_path_factory.mktemp("mail") / "state.json")
    old = os.environ.get(collect.MAIL_STATE_ENV)
    os.environ[collect.MAIL_STATE_ENV] = str(path)
    yield path
    if old is None:
        os.environ.pop(collect.MAIL_STATE_ENV, None)
    else:
        os.environ[collect.MAIL_STATE_ENV] = old


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
