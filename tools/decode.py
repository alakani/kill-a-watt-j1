#!/usr/bin/env python3
"""Decode la.py dumps (lines "t_us value") as UART on GP17 (bit0) / GP18 (bit1)."""
import sys


def load(path_or_lines):
    lines = open(path_or_lines) if isinstance(path_or_lines, str) else path_or_lines
    ev = []
    for line in lines:
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit():
            ev.append((int(parts[0]), int(parts[1])))
    return ev


def channel(ev, bit):
    """Edges of one channel: list of (t, level) with the initial level first."""
    out = []
    for t, v in ev:
        lvl = (v >> bit) & 1
        if not out or out[-1][1] != lvl:
            out.append((t, lvl))
    return out


def level_at(ch, t):
    lvl = ch[0][1]
    for et, el in ch:
        if et > t:
            break
        lvl = el
    return lvl


def uart(ch, bit_us, bits=8, parity=None):
    """Decode 8N1 (or 8E1/8O1) frames. Returns [(t_start, byte, ok)]."""
    frames = []
    i = 1
    n = len(ch)
    while i < n:
        t, lvl = ch[i]
        if lvl != 0:
            i += 1
            continue
        # start bit falling edge at t
        val = 0
        for b in range(bits):
            if level_at(ch, t + bit_us * (1.5 + b)):
                val |= 1 << b
        nb = bits
        ok = True
        if parity:
            p = level_at(ch, t + bit_us * (1.5 + bits))
            ones = bin(val).count("1") + p
            ok = (ones % 2 == 0) if parity == "E" else (ones % 2 == 1)
            nb += 1
        stop = level_at(ch, t + bit_us * (1.5 + nb))
        ok = ok and stop == 1
        frames.append((t, val, ok))
        end = t + bit_us * (nb + 1)
        while i < n and ch[i][0] < end:
            i += 1
        while i < n and ch[i][1] != 0:
            i += 1
    return frames


def widths(ch):
    return [ch[i + 1][0] - ch[i][0] for i in range(1, len(ch) - 1)]


if __name__ == "__main__":
    ev = load(sys.argv[1])
    bit = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    bit_us = float(sys.argv[3]) if len(sys.argv) > 3 else 1e6 / 19200
    ch = channel(ev, bit)
    fr = uart(ch, bit_us)
    print(" ".join("%02x%s" % (b, "" if ok else "!") for _, b, ok in fr))
