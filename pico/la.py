# Tiny PIO + DMA logic analyzer for two adjacent pins (GP17 = bit0, GP18 = bit1).
#
#   import la
#   la.start(freq=1_000_000, words=16000)   # begins sampling into RAM
#   ... stimulate ...
#   la.wait(); la.dump()                    # prints "t_us value" transitions
import array
import time

import micropython
import rp2
from machine import Pin

BASE = 17
PIO0_RXF0 = 0x50200020
DREQ_PIO0_RX0 = 4

_buf = None
_dma = None
_sm = None
_freq = 1


@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT, autopush=True, push_thresh=32, fifo_join=rp2.PIO.JOIN_RX)
def _sampler():
    in_(pins, 2)


def start(freq=1_000_000, words=16000):
    global _buf, _dma, _sm, _freq
    stop()
    if _buf is None or len(_buf) != 4 * words:
        _buf = None
        _buf = bytearray(4 * words)
    _freq = freq
    _sm = rp2.StateMachine(0, _sampler, freq=freq, in_base=Pin(BASE))
    _dma = rp2.DMA()
    ctrl = _dma.pack_ctrl(size=2, inc_read=False, inc_write=True, treq_sel=DREQ_PIO0_RX0)
    _dma.config(read=PIO0_RXF0, write=_buf, count=words, ctrl=ctrl, trigger=True)
    _sm.active(1)


def busy():
    return _dma is not None and _dma.active()


def wait(timeout_ms=5000):
    t = time.ticks_ms()
    while busy() and time.ticks_diff(time.ticks_ms(), t) < timeout_ms:
        time.sleep_ms(5)
    stop()


def stop():
    global _dma, _sm
    if _sm is not None:
        _sm.active(0)
    if _dma is not None:
        _dma.close()
    _dma = None
    _sm = None


@micropython.viper
def _edges(buf, n: int, out, maxout: int) -> int:
    """Transitions as (sample_index << 2 | value) into out; returns count."""
    b = ptr32(buf)
    o = ptr32(out)
    k = 0
    prev = (b[0] >> 30) & 3
    o[0] = prev
    k = 1
    for w in range(n):
        word = b[w]
        # fast path: word holds 16 copies of prev
        rep = prev | (prev << 2)
        rep = rep | (rep << 4)
        rep = rep | (rep << 8)
        rep = rep | (rep << 16)
        if word == rep:
            continue
        for i in range(16):
            v = (word >> (30 - 2 * i)) & 3
            if v != prev:
                if k < maxout:
                    o[k] = ((w * 16 + i) << 2) | v
                    k += 1
                prev = v
    return k


def edges(maxout=8000):
    out = bytearray(4 * maxout)
    k = _edges(_buf, len(_buf) // 4, out, maxout)
    return out, k


def dump(maxout=8000):
    """Print transitions: time_us then value (bit0 = GP17, bit1 = GP18)."""
    out, k = edges(maxout)

    scale = 1_000_000 / _freq
    print("LA freq=%d samples=%d edges=%d" % (_freq, len(_buf) * 4, k))
    for j in range(k):
        e = int.from_bytes(out[4 * j:4 * j + 4], "little")
        print("%d %d" % (int((e >> 2) * scale), e & 3))
    print("LA end")
