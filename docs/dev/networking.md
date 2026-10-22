# Networking: finding the car when the network changes

The DeepRacer takes a DHCP address on every network. On 2026-10-14 at home it came back from a
reboot as 192.168.0.2 while a phone took its old 192.168.0.7, and every script that carried the
address went to the phone. On the road (hotel, venue, a friend's office) this happens every day.
Rules: no IP in the repo, no IP in the config file unless you want one, and the car is found by
what does not change.

## What does not change

| Thing | Value | How to read it |
|---|---|---|
| Wi-Fi MAC of the car | `02:00:00:ab:cd:ef` (placeholder; use your car's) | on the car: `ip link show mlan0`; or the router's client list |
| Hostname | `amss-abcd` (placeholder; `amss-` plus four characters on the stock image) | on the car: `hostname`; the console shows it too |
| mDNS name | `amss-abcd.local` | hostname + `.local` (avahi runs on the stock image) |
| SSH host key | ED25519 `SHA256:<fingerprint>` (this car's value is in the operator's notes, not in the repo) | `ssh-keygen -l -F <host>` after the first login |

## Config: `~/.config/deepracer/env`

```
DEEPRACER_HOST=auto
DEEPRACER_MAC=02:00:00:ab:cd:ef
DEEPRACER_MDNS=amss-abcd.local
```

`auto`, an empty host, or an address that no longer answers on 22/9090 is resolved by
`car/connect/find-car.sh` (shell) and `deepracer_agent.discover` (Python), in this order:

1. **ARP by MAC**: the laptop's ARP table already has the car's MAC (it does after any traffic,
   including the car's own DHCP chatter). Under a second, on any shared subnet.
2. **mDNS**: `DEEPRACER_MDNS` resolves and answers. Needs a network that passes multicast and
   the car's firewall to admit it (see below). A dead lookup costs two seconds, so it is second.
3. **Sweep**: one ping to every address of the laptop's /24 (about a second, in parallel), then
   the ARP table again. Works on any network where laptop and car share a subnet.

The result is exported as `DEEPRACER_HOST` for the rest of that process, so rosbridge, the
console URL (`https://<host>`), `car.sh`, `install.sh`, `make wheels-off` and `make pen` all agree.
`make find-car` prints the address and how it was found. Nothing in discovery moves the car.

Limits: step 3 assumes a /24 (set `DEEPRACER_HOST` by hand on anything else) and needs laptop and
car on the same L2 segment. A venue network with client isolation defeats every step and also
defeats rosbridge itself, which is why the show runs on its own network (next section).

## mDNS on the stock car

Avahi runs, but on 2026-10-14 the car could not resolve its own `.local` name and the laptop saw
no IPv4 record. Two things to do once, on the car, with the operator's password (sudo):

```
sudo ufw allow 5353/udp comment 'mDNS'                 # avahi answers
sudo ufw allow in on mlan0 to 239.255.0.1 comment 'DDS' # rosbridge/rosapi discovery after a restart
sudo systemctl restart avahi-daemon
```

Then `ping amss-abcd.local` from the laptop should answer and discovery has a second route
when the ARP table is cold. Until then discovery takes step 1 or 3, which is fine.

## For travel and the show

- **Bring the network**: a pocket travel router (any GL.iNet, or a phone hotspot) with the car
  and the laptop as its only clients. Give the car a DHCP reservation so it is always the same
  address on that router; put the router's SSID on the car once (the stock image reads
  `wifi-creds.txt` from a USB stick, or use the console's Wi-Fi page). Venue Wi-Fi with client
  isolation would block laptop-to-car traffic entirely, so this is the show setup, not a
  convenience.
- **Wired bench**: a USB-Ethernet adapter on the car and one on the laptop, direct cable, both
  on link-local. `DEEPRACER_HOST=auto` still finds it (step 3 sweeps the laptop's own subnet).
  Deterministic latency, no Wi-Fi, for wheels-off measurements.
- **Remote work** (optional): Tailscale on the car and the laptop gives a stable `100.x` address
  from anywhere with internet; set `DEEPRACER_HOST` to it when not on the same LAN. On the same
  LAN it finds a direct path; through a relay the extra latency makes it unfit for driving.

## SSH host keys

When the car moves to an address another machine once had, ssh refuses with "REMOTE HOST
IDENTIFICATION HAS CHANGED". Check the fingerprint against the table above before trusting it:

```
ssh-keyscan -t ed25519 <new-ip> | ssh-keygen -lf -     # must print the SHA256 fingerprint recorded at first login
ssh-keygen -R <new-ip>                                  # drop the other machine's stale key
```

`car.sh` uses `StrictHostKeyChecking=accept-new`, which records a new address but never accepts
a changed key for a known one.
