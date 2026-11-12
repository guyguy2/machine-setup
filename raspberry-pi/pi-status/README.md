# pi-status (Home Base)

**Home Base** is the single-page site this project serves: the Raspberry Pi's status (the Pi tabs) plus home admin (the
Home tabs). The page shows that name; the code, folder, service and commands keep the name `pi-status`. Standard
library only, no runtime dependencies, reachable only over Tailscale. It is part of this repo because it is part of
setting up a new Pi: `restore.sh` in the parent folder installs and starts it.

    uv run pi-status                    # 127.0.0.1:8080 (what the service runs); Tailscale Serve adds HTTPS in front

## Tabs

The sidebar groups the tabs in two labelled sections (Settings has its own link at the bottom): **Pi** (this machine: Overview through System) and **Home**
(Emails and REI). Click a section's label to fold it (the chevron turns; all its tabs hide, the open one too) or open
it again; the browser remembers which are folded (localStorage, so each browser on its own). While Home is folded the
Emails badge shows on the HOME label instead. Each tab has a line icon (Lucide shapes, drawn as CSS masks in the link's color, so the links stay
plain text) and the Home Base name a house. On phones the sidebar becomes a strip along the top with one row per group,
its label on the left, and the tab icons are left out to save room. A tab without an `api` in `TABS` (in `index.html`) would render straight away without fetching
anything, with "no live data" in the status line instead of an update time (no tab uses that at the moment).

| Tab | Shows |
|---|---|
| Overview | The home page. **Needs attention** lists what needs you, each problem once, and is hidden when all is well: power/thermal throttling, a failed agent, a sign-in that is signed out, expired or failing, a failed systemd service, a red health check, a broken email sorter (its file unreadable or older than 3 hours, or its last run failed, with the error; nothing when it isn't set up yet), and newer pi-status code on disk (with **Restart now**). Then CPU, temperature, memory and disk; **Health check**: the red/green checks `upd` ends with (`pi-up --json`, run on each load; folded to "All 16 green" and opened by itself when one is red; each red check is also in Needs attention, except "No failed systemd units", whose units are already listed by name); one line per agent (Hermes, OpenClaw) with its status and **Start/Stop**, then **Coding sessions** (Claude Code, agy: "2 open" or "none", nothing to start or stop), and uptime, model and revision, OS, kernel, Wi-Fi/ethernet, local IP and Tailscale IP |
| Agents | Two groups, running ones first in each. **Agents** are the always-on assistants, Hermes and OpenClaw: status is running, starting, stopping, stopped or failed, taken from the agent's systemd unit (Hermes: `hermes-gateway.service`, the Telegram bot; OpenClaw: `openclaw-gateway.service`, "starting" while it's up but its Control UI port isn't listening yet). Hermes's web dashboard runs as its own unit, off at boot on purpose, so its card has a **Web dashboard** line with that unit's state ("starting" until port 9119 listens) and its own **Start/Stop**. **Coding sessions** are the interactive tools, Claude Code and agy (the Antigravity CLI): "2 open" or "none", from their processes. The card links to the Hermes dashboard or OpenClaw Control UI on the tailnet (opens in a new tab, with Copy); if it isn't published yet, it shows the `tailscale serve` command instead. **Start/Stop** control the services of Hermes and OpenClaw to free up resources: a stop is systemd's graceful one (SIGTERM, then the unit's stop timeout to clean up), and a stopped service starts again at boot. The card shows uptime, CPU and memory; Claude Code and agy list one row per session (directory, uptime, memory, command one click away); **More** has the `ssh -L` tunnel and localhost URL, the unit and the process table. **Sign-ins** (`gcloud`, `gws`, `gh`, `claude`, Tailscale: signed in, expired, signed out or not installed, with account and project) fold to one line, "5 of 5 signed in", and open themselves when one isn't signed in |
| Agent Lab | Read-only view of `~/dev/agent-lab` (the OpenClaw / Hermes comparison; agents that were removed later stay in `results.md` and the run notes as history but are not shown here): scoreboard per use case, average scores per agent as a bar chart, time and memory per run, my notes per agent, every run note (`#lab/<file>` links to one), and each use case's prompt with a Copy button. The markdown files stay the source of truth; nothing is written back |
| Websites | Sites for the home Wi-Fi (devices without Tailscale) and the tailnet: each one's HTTPS address under the Pi's tailnet name (Tailscale's Let's Encrypt certificate; Pi-hole resolves the name to the LAN IP for the Wi-Fi) as a link with Copy, the old plain-HTTP addresses that redirect there (if it has a `redirect_port`), its status (running, starting, stopped or failed, from the app's and its Caddy proxy's user units and whether the HTTPS port listens beyond localhost), units and folder. A site with `tailnet_only` (the REI dashboard, published by `tailscale serve`) is marked **tailnet only**: it isn't on the Wi-Fi/LAN and has no redirect port. Add one to `WEBSITES` in `src/pi_status/collect.py`, or one whose name or path is private (family names: this repo is public) to `~/dev/websites/sites.json` in the private websites repo, same keys |
| Network | Ready-to-paste SSH commands (Tailscale name and IP, `.local`, LAN IP, plus an `ssh pi` config snippet), Wi-Fi details, gateway, DNS, interfaces, Tailscale peers, logged-in sessions |
| System | Sub-tabs, each with its own address: **Docker** (`#system/docker`, the default: containers, with an HTTPS link to the Pi-hole admin UI (`https://<pi>.<tailnet>.ts.net:8445/pihole/admin/`) while its container runs, or the `tailscale serve` command to publish it, or that Docker isn't installed or isn't running), **Services** (`#system/services`: running and failed systemd system and user services), **Processes** (`#system/processes`: top processes by CPU or memory) and **Ports** (`#system/ports`: listening TCP ports and who can reach them: local only, tailnet, all interfaces). The old `#services`, `#processes`, `#ports` and `#docker` links redirect there |
| Emails | Email triage with the private mail sorter (`~/dev/mail`): its suggestions from `/api/emails`, which reads only `~/.local/share/mail/state.json` (written every hour by `mail-sync.timer`; the format is `docs/state-json.md` there). **All inboxes** (`#emails/all`) and the queues Inbox, Action, Respond, Review, Drafts, Waiting, Later, Delete and Agent Notes, each with its count: Inbox a highlighted pill (the goal is zero), a colored dot for Action (red), Respond (orange), Review (blue), Drafts (teal), Waiting (grey, amber when one is overdue) and Agent Notes (amber), Delete and Later plain counts, and a quiet "3✓" for the ones you confirmed; an empty queue shows nothing. Each queue has its own address (`#emails/<queue>`; `#emails` opens Inbox, the old `#emails/spam` redirects to `#emails/delete`) and switching queues redraws without fetching. The main pane has one card per thread: sender (address on hover), subject, snippet, date, unread dot, message count, "Suggested: Action — why" with who suggested it (`rule` or `Claude`) and the confidence, the to-do, the sender's history ("opened 12 of 14, replied 3" or "new sender"), days waiting (amber when overdue), **Open in Gmail** and the choice buttons: the suggestion first (outlined, with a small "suggested"), then the alternatives, then the rest of Action, Respond, Review and Delete, then **No action** (no action needed: the email is marked read and stays in the Gmail inbox with no label, and its card leaves the page; never deleted), and last **Later** (not sure yet: the email stays in the Gmail inbox, unread and unlabelled, and the card moves to the Later queue). A click locks the card with a spinner, POSTs to `/api/emails/decide` and redraws from the state that comes back; an error (e.g. sign-in expired) shows on the card. A card that moves to another queue leaves a line in its place with **Undo** (where you clicked, and the page doesn't scroll: it keeps its height until the next refresh, so working up from the oldest at the bottom never jumps to the top). A decided card (and the line a choice leaves) has **Add a reason**: a one-line box (Enter saves, Escape cancels) that POSTs `/api/emails/reason` (`mail reason ID TEXT`), kept with the choice for learning and shown as "Your reason: …" with **Edit**. Respond cards (and any card with a draft) have **✎ Draft a reply**: an optional note on what to say ("yes to Friday"), then Claude writes a reply in about half a minute (`/api/emails/draft`, `mail draft`; it doesn't wait behind other clicks). The draft shows in an editable box with its status (only here / in Gmail Drafts / changed here, Gmail has the older version), what you asked, **Save to Gmail drafts** (then **Update Gmail draft**; `mail draft-save`: a reply in the thread to the sender, never sent, refused if you edited it in Gmail since), **Copy**, **Redo…** and **Discard** (Home Base's copy only). Your unsaved edits survive redraws. A decided card says "✓ You chose Review" ("✓ Labelled in Gmail" when you labelled it in Gmail), shows your choice solid with a ✓ ("✓ Review") and offers **Undo**, and decided Action and Respond cards also **Done** (archive). What the buttons do in Gmail is one line above the cards: Action/Respond label and stay in the inbox, Review labels and archives, Delete only marks, Later leaves it as is, and every other choice marks the email read (Undo makes it unread again); Action, Respond, Review, Delete and All inboxes have **Accept all N suggested** above the cards: after one confirm listing what each queue's accept does, it POSTs every suggestion shown and not yet chosen to `/api/emails/accept` (`mail accept ID:QUEUE...`, which skips any that changed since the page loaded) and says how many were accepted; the Delete queue's **Trash all N marked** button asks first ("You can restore them for 30 days") and then trashes exactly the marked threads it showed. While the sorter says actions are off the buttons are disabled with "Suggestions only — nothing is changed in Gmail yet." Agent Notes lists the sorter's notes (info, warning, question). The search box filters sender, address, subject and snippet across all queues. Beside the "Emails" title, in grey: "Gmail checked 21m ago · next ~8:21 PM" (the sorter's last successful Gmail check, `sync.last_success`, not the file's `generated`, which every click rewrites; full time on hover), then **Sync now**: it POSTs `/api/emails/sync`, which starts `mail-sync.service` (the timer's own run, so the next hourly one counts from it; never a second one at once), the line shows a spinner and "Checking Gmail…" (also when the timer's run is going: `/api/emails` says `syncing`), and the page looks every 4 s until it's done and redraws once. The side shows a warning when Gmail hasn't been checked for 3 hours or the last run failed (with its error, e.g. AUTH EXPIRED). Without the file it says "not connected yet" with the command that turns the sorter on. The sidebar's Emails link has a red badge with what needs you (Action + Respond) and the browser tab title starts with "(N)"; for that every page load and **Refresh** also reads `/api/emails` (one file read, never polled). On phones the queues become wrapping chips above the pane |
| REI | Launcher card for the REI dashboard, a separate app on the Pi (private repo `~/dev/rei`), from `/api/rei`. Its status (running, starting, stopped or failed, worded as on Websites: the combined state of `rei.service` and `rei-proxy.service`, "starting" while they're up but its `/healthz` doesn't answer yet), the app's version, **Vault sync** (`rei-vault-sync.timer`: not set up, off, on, with the last successful sync), the health check's error count if any, and the tailnet-only address `https://<pi>.<tailnet>.ts.net:8446/` with Copy. **Open REI** opens it in a new tab when it's running and published; otherwise it's disabled and the card shows the command that fixes it (`systemctl --user start rei.service` when it's down, the `tailscale serve` command when it isn't published). "Next filing due" and "Open alerts" stay "—" for now (they come later) |
| Settings | The link at the bottom of the sidebar (beside Refresh on phones). Everything here is saved in this browser only (one JSON object in localStorage, `pi-status.settings`, read by a small script in `<head>` before the page paints; blocked or broken storage means the defaults). **Theme**: Classic (follows the system's light or dark), Classic light, Classic dark, **Neon** (dark, cyan and hot pink, soft glows on the open tab, dots, badges, bars and hovered buttons; text itself never glows) and **Terminal** (green phosphor, monospace, square corners), each a tile with a small drawing of the page in that theme. **Display**: text size (Small, Default, Large, Larger: the root font size), density (Compact tightens cards, padding and the sidebar), motion (Reduced turns off transitions) and the start page (what opens at the plain address; a `#tab` in the address still wins). **Keyboard shortcuts**: one switch for all, then a table with an on/off box and an editable keys box per shortcut: `g` then a letter goes to a tab (`g o` Overview, `g a` Agents, `g l` Agent Lab, `g w` Websites, `g n` Network, `g s` System, `g e` Emails, `g r` REI, `g ,` Settings), `[` `]` previous/next tab, `j` `k` next/previous email queue, `/` the email search, `f p` / `f h` fold the Pi / Home group, `r` Refresh, `t` next theme, `?` a dialog listing what's on. **Open a website**: named shortcuts that open an address in a new tab (Gmail `o m`, REI `o r`, Hermes `o h`, Pi-hole `o p`, GitHub `o g`, Todoist `o t`; `{host}` in an address is the Pi's name the page was opened on), with **Add website** and **Remove**. Keys are 1–3 single characters with spaces between; a keys box refuses anything else and keys another shortcut already uses (equal, or the start of a longer one). Shortcuts never fire while typing in a box or with Ctrl/Cmd/Alt held. **Reset shortcuts** and **Reset all settings** (asks first; also opens every folded sidebar group) |

To track another agent, add an entry to `AGENTS` in `src/pi_status/collect.py` (and to `DASHBOARDS` if it has a
web UI, with its local port and the HTTPS port `tailscale serve` publishes it on); for another sign-in check, add a
function and an entry to `AUTH_CHECKS` there. Sign-in checks only call each CLI's local status command. Tokens, client
IDs and org IDs never reach the page, and command lines have key-like values masked.

## Refreshing and resource use

Nothing runs in the background. The server only reads `/proc` or runs a command when a request arrives, and the page
fetches once when you open a tab (and again when you press **Refresh** in the sidebar); it never polls. With no page
open the service uses no CPU. The sign-in checks (slow CLIs such as `gcloud`) are cached for 60 seconds.

## Version stamp and restart button

The bottom of the sidebar shows `v<date time> · <commit>`. The commit is the last one that touched this folder, so the
constant snapshot commits elsewhere in the repo don't change it. A trailing `+` means uncommitted changes and
`uncommitted` means no commit yet.

If the code on disk is newer than what the running server loaded (after editing or `git pull`), the stamp shows an
amber "newer code on disk" notice with a **Restart now** button. The button POSTs to `/api/restart` (the request must
carry an `X-Requested-With` header, so other websites can't trigger it, and come from this Pi's owner through
`tailscale serve`, see below), the service restarts itself through systemd,
and the page reloads when the new server is up. A server started by hand can't restart itself, so there the notice just
asks you to restart it: `systemctl --user restart pi-status`.

## How it runs on the Pi

- `~/.config/systemd/user/pi-status.service` starts it on `127.0.0.1:8080` and restarts it if it dies.
- `sudo tailscale serve --bg 8080` publishes it as `https://<pi>.<tailnet>.ts.net` with a real certificate
  (enable HTTPS certificates and Serve once in the Tailscale admin console).
- The dashboards it links to run as their own user units (`hermes-dashboard.service` on 9119,
  `openclaw-gateway.service` on 18789), published on the tailnet at `:8443/hermes/` and `:8444/openclaw/` (its `gateway.controlUi.basePath` is `/openclaw`). The Pi-hole UI (Docker, host port 8081) is published at `:8445/pihole/admin/`. Hermes has no prefix setting of its own but honours `X-Forwarded-Prefix`, so `hermes-proxy.service` (Caddy on 127.0.0.1:9120, config in `services/hermes-proxy/`, started and stopped with `hermes-dashboard.service`) adds that header and Tailscale publishes the proxy.
- The REI dashboard runs from its own repo: `rei.service` (uvicorn, 127.0.0.1:8420) behind `rei-proxy.service` (Caddy,
  127.0.0.1:8421), published tailnet-only at `:8446/`. `/api/rei` reads only its units, whether 8446 listens beyond
  localhost, the sync timer and `GET 127.0.0.1:8420/healthz` (2 s timeout, skipped while the app is stopped), of which
  it passes on only `ok`, `version` and the number of errors. A failed `rei.service` shows in Overview's **Needs
  attention** like any failed user service.
- **Who can change things** (agent-lab/reviews R-033): the server listens on 127.0.0.1 only, so the tailnet HTTPS
  address is the way in. `tailscale serve` deletes any `Tailscale-User-*` headers a client sends and adds
  `Tailscale-User-Login` with the login of the device's owner (not for tagged devices). Every POST (restart, agent
  start/stop, email choices) must carry the login of this Pi's own owner, read from `tailscale status --json` when the
  first POST arrives (`src/pi_status/guard.py`); anything else gets 403 (503 while Tailscale can't say who the owner
  is). GETs stay open to anyone on the tailnet, as before.
- **Audit log**: every POST, allowed or refused, is one JSON line in `~/.local/state/pi-status/audit.log` (0600; moved
  to `audit.log.1` past 1 MB): time, login, client tailnet address, path, status, error, and for email choices the
  thread id, queue and how many ids, never the text of a draft or reason. Read it with
  `tail ~/.local/state/pi-status/audit.log | jq -c`.
- `restore.sh` in the parent folder sets all of this up on a fresh image (steps `tailscale`, `pi-status` and `rei`).
- `~/dev/pi-status` is a symlink to this folder, so there is only one copy.
- `upd` runs `uv sync` and restarts the service after pulling repos.

## Develop

    uv run pytest                       # unit, server and browser tests (Playwright drives the system Chromium)
    uv run python screenshots.py        # PNGs of every tab (desktop + phone) in ./screenshots (not committed)
    pyright                             # type-check the Python (kept at 0 errors; install with sudo npm install -g pyright)

The page is served with `Content-Security-Policy: require-trusted-types-for 'script'`, so the browser refuses
`innerHTML`, `insertAdjacentHTML`, `eval` and the like: build DOM with `h()` (text only). In Playwright tests, give
`wait_for_function` an arrow function (`"() => ..."`); a plain expression is run through `eval` and refused. Tests that
fold groups or open `<details>` call `settle(page)` first, since those animate (Chrome). The colors are checked for
contrast in every theme (`test_status_text_and_text_boxes_are_readable_in_every_theme`). Target browser: Chrome
(Mac and Android); newer CSS that other browsers lack must degrade to a working page.

JSON endpoints (all GET except restart): `/api/status`, `/api/network`, `/api/agents`, `/api/dashboards`, `/api/auth`, `/api/docker`,
`/api/services`, `/api/processes`, `/api/ports`, `/api/lab`, `/api/websites`, `/api/rei`, `/api/emails`, `/api/version`; `POST /api/restart`, `POST /api/agents/<unit>/start` and `/stop` (only the
units in `AGENTS`), and `POST /api/emails/decide` `{"thread", "queue"}` (queue action, respond, review, delete or done),
`/api/emails/undo` `{"thread"}` and `/api/emails/trash` `{"ids": [...]}` (at most 500). Every POST needs the
`X-Requested-With: pi-status` header and the `Tailscale-User-Login` of this Pi's owner (next section). The email ones accept a JSON body of at most 32 KB, check every thread id
(`[0-9a-f]{10,24}`) and then run the sorter's own command, one at a time, as an argument list with no shell:
`~/dev/mail/.venv/bin/mail decide|undo|trash --yes ... --via web --json` (60 s timeout; `PI_STATUS_MAIL_BIN` overrides
the path). They answer with its JSON plus the new `/api/emails` payload under `state`; its exit code becomes the status:
0 → 200, 1 (Gmail error) → 502, 2 (sign-in expired) → 401, 3 (usage) → 400, 5 (refused) → 409; a missing command → 503,
a timeout → 504.

Emails in tests and screenshots are always fake: `tests/fixtures/mail-state.json` (invented senders on `.example`
domains), moved to the current time by `tests/mail_fixture.py`. The tests and `screenshots.py` point
`PI_STATUS_MAIL_STATE` at it (and screenshots also answer the page's `/api/emails` with it when using `--url`), so
real mail never ends up in this public repo. The tests point `PI_STATUS_MAIL_BIN` at a command that doesn't exist, and
the ones that click a button use `tests/fake_mail.py`, which records its arguments and edits a copy of the fixture the
way the real command would, so no test can reach Gmail.
