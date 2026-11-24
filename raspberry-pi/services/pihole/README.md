# Pi-hole

Docker setup for Pi-hole v6 (see `docker-compose.yml`, `.env.example`).

## Temporarily allow a blocked site

```sh
pihole-allow-temp example.com 1h   # allow for an hour (30m, 2h, 1d ...), removed automatically afterwards
pihole-allow-temp list             # show temporary allows and when they expire
pihole-allow-temp remove example.com
```

Run once per domain (`www.example.com` and `example.com` are separate). Expiry is stored in the allow rule's comment;
`user/pihole-allow-temp.timer` sweeps expired rules every minute. Applies to every device using this Pi-hole.
