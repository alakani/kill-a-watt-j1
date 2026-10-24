#!/usr/bin/env python3
"""Decode 'B <cmd> <edge,times>' lines from probe scripts."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import decode

BIT = float(sys.argv[2]) if len(sys.argv) > 2 else 49.56
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) < 2 or p[0] != "B":
        continue
    if len(p) < 3:
        print(p[1], "(no reply)")
        continue
    t = [int(x) for x in p[2].split(",") if x]
    ch = [(0, 1)] + [(x, 0 if i % 2 == 0 else 1) for i, x in enumerate(t)]
    fr = decode.uart(ch, BIT)
    data = bytes(v for _, v, _ in fr)
    print(p[1], "lat=%5dus" % t[0], " ".join("%02x%s" % (v, "" if ok else "!") for _, v, ok in fr), "|", repr(data))
