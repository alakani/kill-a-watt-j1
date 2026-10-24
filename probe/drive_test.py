# Gentle test: drive each pin low at the weakest drive strength (2 mA) for a
# few tens of us and read the pad back. A push-pull high on the far side shows
# up as the pad not going (cleanly) low.
from machine import Pin, mem32
import time
PADS = 0x4001c000
def weak(n):
    a = PADS + 4 + 4*n
    mem32[a] = (mem32[a] & ~0x30)  # DRIVE = 2 mA
    return mem32[a]
for n in (17, 18):
    other = 18 if n == 17 else 17
    po = Pin(other, Pin.IN)
    p = Pin(n, Pin.IN)
    p.init(Pin.OUT, value=1)
    pad = weak(n)
    reads = []; oreads = []
    t0 = time.ticks_us()
    p.value(0)
    for i in range(20):
        reads.append(p.value()); oreads.append(po.value())
    p.value(1)
    dt = time.ticks_diff(time.ticks_us(), t0)
    p.init(Pin.IN)
    print("GP%d pad=0x%x driven low %dus, pad reads: %s other: %s" % (n, pad, dt, reads, oreads))
    time.sleep_ms(50)
