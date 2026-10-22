"""Car-side PWM sampler: runs ON the car (Python 3.8) under ``python3 -u -c``; the laptop reads its lines.

Every 10 ms it reads the duty_cycle files it was given and prints ``S <car_monotonic> <v0> <v1>``
when a value changes (and every 0.5 s regardless, as a heartbeat). Any line the laptop writes on
stdin is echoed back as ``M <car_monotonic> <line>`` the moment it is read, so a laptop-side event
(a stop call, a heartbeat cut) gets a timestamp on the SAME clock as the PWM samples; ``Q`` ends
the run. No ROS, no root, no writes: it only reads sysfs. Physics stops the car; this is how we
see, to the centisecond, when it did.
"""

import select
import sys
import time


def main(argv):
    rate = 100.0
    duration = 30.0
    files = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--rate":
            rate = float(args.pop(0))
        elif a == "--duration":
            duration = float(args.pop(0))
        else:
            files.append(a)
    if not files:
        files = ["/sys/class/pwm/pwmchip0/pwm0/duty_cycle", "/sys/class/pwm/pwmchip0/pwm1/duty_cycle"]
    handles = [open(f, "rb", buffering=0) for f in files]
    out = sys.stdout
    period = 1.0 / rate
    t_end = time.monotonic() + duration
    out.write(f"READY {time.monotonic():.4f} {' '.join(files)}\n")
    out.flush()
    last = None
    last_print = 0.0
    next_tick = time.monotonic()
    while time.monotonic() < t_end:
        now = time.monotonic()
        vals = []
        for h in handles:
            h.seek(0)
            vals.append(h.read(64).strip().decode("ascii", "replace"))
        if vals != last or now - last_print >= 0.5:
            out.write(f"S {now:.4f} {' '.join(vals)}\n")
            last = vals
            last_print = now
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            out.write(f"M {time.monotonic():.4f} {line}\n")
            if line == "Q":
                break
        out.flush()
        next_tick += period
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_tick = time.monotonic()
    out.write(f"END {time.monotonic():.4f}\n")
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
