# Kill-A-Watt logger firmware: polls the meter over J1 and prints one line per sample
# on USB serial. Decoding happens on the host (kaw_log.py), so this stays dumb:
#
#   K <ms> 31:1204 52:0011 33:0063 34:0600 35:0002 56:0000 57:0006
#
# each field is <header hex>:<digits> for queries 0x11..0x17, or "--" if the meter
# didn't answer. Digits outside 0..9 are sent as <hex>.
import time

from machine import Pin

import kaw

INTERVAL_MS = 1000
QUERIES = (kaw.VOLTS, kaw.AMPS, kaw.WATTS, kaw.HZ, kaw.Q15, kaw.KWH, kaw.CLOCK)

led = Pin("LED", Pin.OUT)


def field(rep):
    if not rep:
        return "--"
    digits = "".join("%d" % (b - 0x20) if 0x20 <= b <= 0x29 else "<%02x>" % b for b in rep[1:])
    return "%02x:%s" % (rep[0], digits)


def run():
    kaw.open()
    print("KAW start")
    next_t = time.ticks_ms()
    while True:
        t = time.ticks_ms()
        led.on()
        line = " ".join(field(kaw.query(q, 60)) for q in QUERIES)
        led.off()
        print("K %d %s" % (t, line))
        next_t = time.ticks_add(next_t, INTERVAL_MS)
        wait = time.ticks_diff(next_t, time.ticks_ms())
        if wait > 0:
            time.sleep_ms(wait)
        else:
            next_t = time.ticks_ms()


run()
