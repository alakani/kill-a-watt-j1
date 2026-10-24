# Passive: count edges and record timestamps on GP17/GP18 for a few seconds.
from machine import Pin
import time, array
pins = {17: Pin(17, Pin.IN), 18: Pin(18, Pin.IN)}
print("idle levels:", {k: p.value() for k, p in pins.items()})
N = 2000
ts = {k: array.array('I', [0]*N) for k in pins}
cnt = {k: 0 for k in pins}
def mk(k):
    buf = ts[k]
    def h(p):
        c = cnt[k]
        if c < N:
            buf[c] = time.ticks_us()
        cnt[k] = c + 1
    return h
for k, p in pins.items():
    p.irq(mk(k), Pin.IRQ_RISING | Pin.IRQ_FALLING, hard=True)
time.sleep(30)
for p in pins.values():
    p.irq(None)
for k in pins:
    c = min(cnt[k], N)
    d = [time.ticks_diff(ts[k][i+1], ts[k][i]) for i in range(c-1)]
    print("GP%d edges=%d" % (k, cnt[k]))
    if d:
        print("  min dt us:", min(d), " first 60 dts:", d[:60])
