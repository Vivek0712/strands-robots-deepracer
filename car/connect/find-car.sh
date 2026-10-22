#!/usr/bin/env bash
# Print the car's IP on this network. Reads DEEPRACER_MDNS (e.g. amss-abcd.local) and
# DEEPRACER_MAC (the car's Wi-Fi MAC, never changes). Order: ARP table by MAC, mDNS, ping sweep
# of the laptop's /24 then ARP again. Exit 1 when not found. Shell twin of deepracer_agent/discover.py.
set -uo pipefail
MDNS=${DEEPRACER_MDNS:-}
MAC=${DEEPRACER_MAC:-}

norm_mac() { local IFS=:; local out=(); for o in $1; do out+=("$(printf '%02x' "0x$o")"); done; IFS=:; echo "${out[*]}"; }
answers() { nc -z -w 1 "$1" 22 2>/dev/null || nc -z -w 1 "$1" 9090 2>/dev/null; }
arp_lookup() {
  local want; want=$(norm_mac "$1")
  arp -a -n 2>/dev/null | while read -r line; do
    ip=$(sed -n 's/.*(\([0-9.]*\)) at \([0-9a-fA-F:]*\) .*/\1/p' <<<"$line")
    mac=$(sed -n 's/.*(\([0-9.]*\)) at \([0-9a-fA-F:]*\) .*/\2/p' <<<"$line")
    [ -n "$mac" ] && [ "$mac" != "(incomplete)" ] || continue
    [ "$(norm_mac "$mac")" = "$want" ] && { echo "$ip"; break; }
  done
}

if [ -n "$MAC" ]; then
  ip=$(arp_lookup "$MAC")
  if [ -n "$ip" ] && answers "$ip"; then echo "$ip"; echo "via arp" >&2; exit 0; fi
fi
if [ -n "$MDNS" ]; then
  ip=$(ping -c 1 -W 1500 "$MDNS" 2>/dev/null | sed -n '1s/.*(\([0-9.]*\)).*/\1/p')
  if [ -n "$ip" ] && answers "$ip"; then echo "$ip"; echo "via mdns" >&2; exit 0; fi
fi
[ -n "$MAC" ] || { echo "find-car: set DEEPRACER_MAC (and DEEPRACER_MDNS) in ~/.config/deepracer/env" >&2; exit 1; }
# IPv6-only network (a phone hotspot): the car's MAC in the neighbour table after an all-nodes ping.
if command -v ndp >/dev/null; then
  for ifc in $(ifconfig -l 2>/dev/null); do case "$ifc" in en*) ping6 -c 1 -I "$ifc" "ff02::1%$ifc" >/dev/null 2>&1 & esac; done; wait
  want=$(norm_mac "$MAC")
  ip6=$(ndp -an 2>/dev/null | awk 'NR>1 && $2 ~ /:/ {print $1, $2}' | while read -r a m; do
    [ "$(norm_mac "$m")" = "$want" ] && echo "$a"; done | grep -v '^fe80' | head -1)
  [ -n "$ip6" ] || ip6=$(ndp -an 2>/dev/null | awk 'NR>1 && $2 ~ /:/ {print $1, $2}' | while read -r a m; do
    [ "$(norm_mac "$m")" = "$want" ] && echo "$a"; done | head -1)
  if [ -n "$ip6" ] && answers "$ip6"; then echo "$ip6"; echo "via ndp" >&2; exit 0; fi
fi
me=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$me" ] || { echo "find-car: no local IPv4" >&2; exit 1; }
prefix=${me%.*}
for i in $(seq 1 254); do ping -c 1 -W 300 "$prefix.$i" >/dev/null 2>&1 & done; wait
ip=$(arp_lookup "$MAC")
if [ -n "$ip" ] && answers "$ip"; then echo "$ip"; echo "via sweep" >&2; exit 0; fi
echo "find-car: car not found on $prefix.0/24 (MAC $MAC)" >&2
exit 1
