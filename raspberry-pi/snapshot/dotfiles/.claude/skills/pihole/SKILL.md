---
name: pihole
description: Manage the user's Pi-hole (v6, runs in Docker on this Pi) from the shell: read stats, pause/enable blocking, allow/deny domains, manage blocklists/groups/clients, change DNS upstreams and other settings, reset the admin password. Use whenever the user mentions Pi-hole, DNS blocking, blocklists, or the pihole admin login.
---

# Pi-hole (v6, Docker)

Pi-hole runs as the Docker container `pihole`, not on the host, so there is no `pihole` command on PATH. Use
`docker exec pihole ...` or the REST API.

- Project dir: `~/dev/pihole`, a symlink to `~/dev/machine-setup/raspberry-pi/services/pihole` (`docker-compose.yml`,
  `.env`, `.env.example`). `.env` is gitignored and holds the password and `PIHOLE_DATA`; the persistent volume
  (`/etc/pihole`) is `~/.local/share/pihole`, outside the public repo.
- Web UI/API: bound to `127.0.0.1:8081` (`/admin`, `/api`, API reference at `/api/docs`). The user reaches it from
  the Mac over Tailscale (`https://raspberrypi.<tailnet>.ts.net:8445/pihole/admin/`; get the name with `tailscale status --json | jq -r .Self.DNSName`) or an SSH tunnel.
- DNS: port 53 tcp/udp on all interfaces.
- There is one admin account and no username, only a password.

## Admin password

The password lives in `~/dev/pihole/.env` as `FTLCONF_webserver_api_password`, which the compose file passes into
the container. Because it is set via an `FTLCONF_` variable it overrides everything on restart, so
`pihole setpassword` inside the container will not stick. To change it, edit `.env`, then:

```sh
cd ~/dev/pihole && docker compose up -d
```

Don't print the password into the conversation. Tell the user to run `grep FTLCONF_webserver_api_password ~/dev/pihole/.env`
if they need to see it.

## REST API

Authenticate with the password from `.env` (build the JSON with jq so special characters survive), pass the session
id in a `sid` header, and log out when done:

```sh
PW=$(grep '^FTLCONF_webserver_api_password=' ~/dev/pihole/.env | cut -d= -f2-)
SID=$(curl -s -X POST localhost:8081/api/auth -H 'Content-Type: application/json' \
  -d "$(jq -n --arg p "$PW" '{password:$p}')" | jq -r .session.sid)

curl -s -H "sid: $SID" localhost:8081/api/stats/summary | jq '.queries'
curl -s -H "sid: $SID" localhost:8081/api/dns/blocking                     # status
curl -s -X POST -H "sid: $SID" -H 'Content-Type: application/json' \
  -d '{"blocking":false,"timer":300}' localhost:8081/api/dns/blocking      # pause 5 min
curl -s -H "sid: $SID" localhost:8081/api/config/dns/upstreams             # read one setting
curl -s -H "sid: $SID" localhost:8081/api/config | jq                      # all settings

curl -s -X DELETE -H "sid: $SID" localhost:8081/api/auth                   # log out
```

Other endpoints (domains, lists, groups, clients, queries, history) are documented at `/api/docs`, which redirects
to the browsable reference. Check it rather than guessing request bodies.

## CLI inside the container

```sh
docker exec pihole pihole status
docker exec pihole pihole enable | disable
docker exec pihole pihole allow example.com        # exact domain; --help for regex/wildcard options
docker exec pihole pihole deny example.com
docker exec pihole pihole -g                       # update gravity (blocklists)
docker exec pihole pihole-FTL --config             # list all settings
docker exec pihole pihole-FTL --config dns.upstreams                       # read one
docker exec pihole pihole-FTL --config dns.upstreams '["1.1.1.1","1.0.0.1"]'   # set one
```

## Settings pinned by environment variables

Any setting defined as an `FTLCONF_<section>_<key>` variable in `docker-compose.yml` or `.env` (currently
`webserver_api_password` and `dns_listeningMode`) is read-only through the UI, API and CLI and is re-applied on every
restart. Change those in the compose file/`.env` and run `docker compose up -d`. Everything else (upstreams,
blocklists, allow/deny entries, groups, clients) can be changed live and is persisted in `~/.local/share/pihole`.

If the user wants a live-changed setting to survive a container rebuild from scratch, `~/.local/share/pihole` is the state
that matters. The nightly pi-backup keeps a Teleporter export of it; check that it's recent before recreating or deleting the volume.

## Temporarily allow a blocked site (auto-expires)

Pi-hole can't expire an allow rule itself, so use `pihole-allow-temp` (script in `~/dev/pihole/pihole-allow-temp`,
linked into `~/.local/bin`). When the user asks to allow a site for a while, run it, don't hand-roll allow + reminder:

```sh
pihole-allow-temp example.com 1h      # duration optional, default 1h (30m, 2h, 1d ...)
pihole-allow-temp list                # active temporary allows and expiry times
pihole-allow-temp remove example.com  # end one early
```

Run it once per domain (`www.` and the bare domain are separate entries). The expiry is stored in the rule's comment
and `pihole-allow-temp.timer` (user unit, every minute) runs `pihole-allow-temp sweep` to delete expired ones, so it
survives reboots. Only rules with the `temp-allow until` comment are ever removed. Allows apply to every device using
this Pi-hole. Devices may cache the old answer for a few minutes either way. Verify with
`docker exec pihole dig +short @127.0.0.1 <domain>`. From the Mac: `ssh <pi> pihole-allow-temp example.com 1h`.

## Safety

- Reads are free. Before changing settings, blocklists or the password, say what you're changing. Blocking
  changes affect every device on the network that uses this Pi-hole for DNS.
- `docker compose up -d` recreates the container and DNS is briefly down (about 15 s until healthy). Warn first
  if the user may be mid-call or streaming.
- Don't run `docker compose down -v`, delete `~/.local/share/pihole`, or remove the container without asking.
