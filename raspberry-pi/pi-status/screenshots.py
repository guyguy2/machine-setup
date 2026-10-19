"""Render every tab on desktop and phone and save PNGs to ./screenshots.

    uv run python screenshots.py                  # starts its own server, real data from this machine
    uv run python screenshots.py --url https://<this-pi>.<your-tailnet>.ts.net
"""

import argparse
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from pi_status import Handler

TABS = ["overview", "network", "agents", "docker", "services", "processes", "ports"]
VIEWPORTS = {"desktop": (1280, 900), "phone": (390, 844)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="existing server to capture (default: start a temporary one)")
    parser.add_argument("--out", default="screenshots")
    args = parser.parse_args()

    url = args.url
    if not url:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}"

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    exe = shutil.which("chromium") or shutil.which("chromium-browser")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        for name, (w, h) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2 if name == "phone" else 1)
            for tab in TABS:
                page.goto(f"{url}/#{tab}")
                page.wait_for_selector("#view h2")
                page.wait_for_timeout(500)
                path = out / f"{tab}-{name}.png"
                page.screenshot(path=path, full_page=True)
                print(path)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
