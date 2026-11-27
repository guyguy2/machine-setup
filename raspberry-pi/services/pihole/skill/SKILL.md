---
name: pihole
description: "Manage Pi-hole (Docker): stats, blocking, allow/deny, DNS."
---

# Pi-hole (v6, Docker)

Pi-hole runs as the Docker container `pihole`, not on the host, so there is no `pihole` binary on PATH. Use `docker exec pihole ...` or the REST API.

- Project dir: `~/dev/pihole` (symlink to `~/dev/machine-setup/raspberry-pi/services/pihole`, containing `docker-compose.yml` and gitignored `.env`).
- Persistent state (`/etc/pihole`): `~/.local/share/pihole`.
- Web UI/API: `127.0.0.1:8081` (`/admin`, `/api`, docs at `/api/docs`), also published on the tailnet at `:8445/pihole/admin/`.
- DNS: port 53 tcp/udp on all interfaces. One admin password, no username.

## Admin password

The password lives in `~/dev/pihole/.env` as `FTLCONF_webserver_api_password` and overrides container state on restart (`pihole setpassword` inside the container will not stick). To change it, edit `.env` and run `cd ~/dev/pihole && docker compose up -d`. Never print the password in chat; tell the user to run `grep FTLCONF_webserver_api_password ~/dev/pihole/.env`.

## CLI inside the container

```sh
docker exec pihole pihole status
docker exec pihole pihole enable | disable
docker exec pihole pihole allow example.com        # exact domain; --help for regex/wildcard
docker exec pihole pihole deny example.com
docker exec pihole pihole -g                       # update gravity (blocklists)
docker exec pihole pihole-FTL --config             # list all settings
docker exec pihole pihole-FTL --config dns.upstreams
docker exec pihole pihole-FTL --config dns.upstreams '["1.1.1.1","1.0.0.1"]'
```

## REST API

Authenticate using `FTLCONF_webserver_api_password` from `~/dev/pihole/.env` (pass `sid` header, and `DELETE /api/auth` to log out when done):

```sh
PW=$(grep '^FTLCONF_webserver_api_password=' ~/dev/pihole/.env | cut -d= -f2-)
SID=$(curl -s -X POST localhost:8081/api/auth -H 'Content-Type: application/json'   -d "$(jq -n --arg p "$PW" '{password:$p}')" | jq -r .session.sid)

curl -s -H "sid: $SID" localhost:8081/api/stats/summary | jq '.queries'
curl -s -H "sid: $SID" localhost:8081/api/dns/blocking
curl -s -X POST -H "sid: $SID" -H 'Content-Type: application/json'   -d '{"blocking":false,"timer":300}' localhost:8081/api/dns/blocking
curl -s -H "sid: $SID" localhost:8081/api/config/dns/upstreams
curl -s -X DELETE -H "sid: $SID" localhost:8081/api/auth
```

Check `/api/docs` rather than guessing other endpoint payloads.

## Settings pinned by env vars

Any `FTLCONF_<section>_<key>` env var (`webserver_api_password`, `dns_listeningMode`) is read-only via UI/API/CLI and re-applied on restart; change those in `docker-compose.yml` or `.env` + `docker compose up -d`. Other changes (upstreams, blocklists, allow/deny, groups, clients) persist in `~/.local/share/pihole`.

## Safety

- Reads are free. Before changing blocking, blocklists, DNS settings, or the password, state the change and get confirmation (blocking changes affect every device using this Pi-hole for DNS).
- `docker compose up -d` causes ~15s of DNS downtime until healthy; warn first.
- Never run `docker compose down -v`, delete `~/.local/share/pihole`, or remove the container without explicit approval.
