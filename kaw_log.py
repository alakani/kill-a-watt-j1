#!/usr/bin/env python3
"""Log a P3 Kill-A-Watt through the Pico on its J1 port.

    python3 kaw_log.py                 # print readings, append to kaw_log.csv
    python3 kaw_log.py -o other.csv    # a different CSV
    python3 kaw_log.py --raw           # also print the Pico's raw lines

The Pico runs pico/main.py, which prints a line per sample; this decodes it.
See NOTES.md for the protocol.
"""
import argparse
import csv
import datetime
import os
import sys
import time

import serial
from serial.tools import list_ports

PICO_VID = 0x2E8A

# Query -> (name, decoder). Header high nibble gives the decimal places shown on the
# display: 0x1_ = none, 0x3_ = one, 0x5_ = two (others not seen yet, kept raw).
DECIMALS = {0x1: 0, 0x3: 1, 0x5: 2}
QUERIES = [(0x11, "volts"), (0x12, "amps"), (0x13, "watts"), (0x14, "hz"),
           (0x15, "q15"), (0x16, "kwh"), (0x17, "elapsed")]
COLUMNS = ["time", "volts", "amps", "watts", "va", "pf", "hz", "kwh", "elapsed_min", "q15", "raw"]


def find_port(serial_number=None):
    """The Pico's USB serial port: by USB serial number if given, else the first Pico."""
    for p in list_ports.comports():
        if p.vid == PICO_VID and (not serial_number or (p.serial_number or "").lower() == serial_number.lower()):
            return p.device
    return None


def decode_field(name, text):
    """'31:1204' -> number (or minutes for elapsed); None if unknown/missing."""
    if text == "--" or ":" not in text:
        return None
    hdr, digits = text.split(":", 1)
    if not digits.isdigit():
        return None
    places = DECIMALS.get(int(hdr, 16) >> 4)
    if places is None:
        return None
    if name == "elapsed":
        # hh:mm in the two-decimal position; past 99:59, whole hours with no decimals
        if places == 2:
            return int(digits[:2]) * 60 + int(digits[2:])
        return int(digits) * 60 if places == 0 else None
    return int(digits) / 10 ** places


def decode_line(line):
    """'K <ms> f11 f12 ... f17' -> dict, or None."""
    parts = line.split()
    if len(parts) != 2 + len(QUERIES) or parts[0] != "K":
        return None
    fields = parts[2:]
    row = {name: decode_field(name, f) for (_, name), f in zip(QUERIES, fields)}
    row["elapsed_min"] = row.pop("elapsed")
    v, a, w = row["volts"], row["amps"], row["watts"]
    row["va"] = round(v * a, 2) if v is not None and a is not None else None
    row["pf"] = round(w / row["va"], 3) if w is not None and row["va"] else None
    row["q15"] = fields[4]
    row["raw"] = " ".join(fields)
    return row


def start_logger(port):
    """Make sure main.py is running: interrupt whatever is there, then soft-reset."""
    port.write(b"\x02\x03\x03")  # leave raw REPL, stop anything running
    time.sleep(0.3)
    port.reset_input_buffer()
    port.write(b"\x04")  # soft reset at the friendly REPL runs main.py
    deadline = time.time() + 5
    while time.time() < deadline:
        line = port.readline().decode(errors="replace").strip()
        if line.startswith("KAW start") or line.startswith("K "):
            return
    raise RuntimeError("Pico didn't start the logger (is main.py + kaw.py on it?)")


def fmt(x, nd):
    return "-" if x is None else "%.*f" % (nd, x)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--port", help="Pico serial port (default: find it)")
    ap.add_argument("-s", "--serial", help="pick the Pico with this USB serial number")
    ap.add_argument("-o", "--output", default="kaw_log.csv")
    ap.add_argument("--raw", action="store_true")
    args = ap.parse_args()

    path = args.port or find_port(args.serial)
    if not path:
        sys.exit("no Pico found on USB")
    try:
        port = serial.Serial(path, 115200, timeout=2)
    except serial.SerialException as e:
        sys.exit("%s\n(is another program holding the port?)" % e)

    start_logger(port)
    new = not os.path.exists(args.output) or os.path.getsize(args.output) == 0
    with open(args.output, "a", newline="") as f:
        out = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            out.writeheader()
        print("logging %s -> %s" % (path, args.output), file=sys.stderr)
        while True:
            line = port.readline().decode(errors="replace").strip()
            if not line:
                continue
            if args.raw:
                print(line, file=sys.stderr)
            row = decode_line(line)
            if row is None:
                continue
            row["time"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            out.writerow(row)
            f.flush()
            el = row["elapsed_min"]
            print("%s  %s V  %s A  %s W  %s VA  PF %s  %s Hz  %s kWh  %s" % (
                row["time"][11:19], fmt(row["volts"], 1), fmt(row["amps"], 2), fmt(row["watts"], 1),
                fmt(row["va"], 1), fmt(row["pf"], 2), fmt(row["hz"], 1), fmt(row["kwh"], 2),
                "-" if el is None else "%d:%02d" % divmod(el, 60)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
