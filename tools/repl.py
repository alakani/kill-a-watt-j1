#!/usr/bin/env python3
"""Minimal MicroPython raw-REPL client (pyserial only).

    repl.py exec 'print(1+1)'         run code, print output
    repl.py run script.py [secs]      run a local file on the board, stream output
    repl.py put local.py [remote.py]  copy a file to the board
    repl.py ls

The port is $PICO_PORT, or the first Raspberry Pi USB serial device found.
"""
import os
import sys
import time

import serial
from serial.tools import list_ports


def find_port():
    """$PICO_PORT, else the first Raspberry Pi (vendor 0x2E8A) USB serial port."""
    if os.environ.get("PICO_PORT"):
        return os.environ["PICO_PORT"]
    for p in list_ports.comports():
        if p.vid == 0x2E8A:
            return p.device
    sys.exit("no Pico found on USB (set PICO_PORT)")


def open_port():
    s = serial.Serial(find_port(), 115200, timeout=0.2, write_timeout=3)
    for attempt in range(3):
        s.write(b"\x02\r\x03\x03")
        time.sleep(0.2)
        s.reset_input_buffer()
        s.write(b"\x01")  # raw REPL
        try:
            _read_until(s, b"raw REPL; CTRL-B to exit\r\n>", 2)
            break
        except TimeoutError:
            if attempt == 2:
                raise
    if os.environ.get("PICO_NORESET") != "1":
        s.write(b"\x04")  # soft reset for a clean heap
        buf = _read_until(s, b"soft reboot", 3)
        if b"raw REPL; CTRL-B to exit\r\n>" not in buf.split(b"soft reboot", 1)[1]:
            _read_until(s, b"raw REPL; CTRL-B to exit\r\n>", 3)
    return s


def _read_until(s, marker, timeout):
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        buf += s.read(256)
        if marker in buf:
            return buf
    raise TimeoutError("waiting for %r, got %r" % (marker, buf[-200:]))


def exec_code(s, code, timeout=10, stream=None):
    """Run code in raw REPL. Returns (stdout, stderr)."""
    if isinstance(code, str):
        code = code.encode()
    for i in range(0, len(code), 256):
        s.write(code[i:i + 256])
        time.sleep(0.01)
    s.write(b"\x04")
    out = _read_until(s, b"OK", 3).split(b"OK", 1)[1]
    if stream and out:
        stream.write(out.decode(errors="replace"))
    end = time.time() + timeout
    while time.time() < end:
        if out.count(b"\x04") >= 2 and out.endswith(b">"):
            break
        chunk = s.read(512)
        if chunk:
            out += chunk
            if stream:
                stream.write(chunk.decode(errors="replace"))
                stream.flush()
    else:
        s.write(b"\x03")  # interrupt a script that outlived its time
        time.sleep(0.3)
        out += s.read(4096)
    parts = out.split(b"\x04")
    stdout = parts[0].decode(errors="replace")
    stderr = parts[1].decode(errors="replace") if len(parts) > 1 else ""
    return stdout, stderr


def put(s, local, remote):
    data = open(local, "rb").read()
    exec_code(s, "f=open(%r,'wb')" % remote)
    for i in range(0, len(data), 512):
        exec_code(s, "f.write(%r)" % data[i:i + 512])
    exec_code(s, "f.close()")


def main():
    cmd = sys.argv[1]
    s = open_port()
    try:
        if cmd == "exec":
            out, err = exec_code(s, sys.argv[2], timeout=float(sys.argv[3]) if len(sys.argv) > 3 else 10)
            print(out, end="")
            if err:
                print(err, end="", file=sys.stderr)
        elif cmd == "run":
            code = open(sys.argv[2]).read()
            timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 30
            exec_code(s, code, timeout=timeout, stream=sys.stdout)
        elif cmd == "put":
            remote = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(sys.argv[2])
            put(s, sys.argv[2], remote)
            print("wrote", remote)
        elif cmd == "ls":
            out, err = exec_code(s, "import os;print(os.listdir())")
            print(out, err)
    finally:
        s.write(b"\x02")
        s.close()


if __name__ == "__main__":
    main()
