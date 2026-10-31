# Kill-A-Watt J1 driver: PIO UART on GP17 (TX, to meter RX) / GP18 (RX, from meter TX).
#
# The meter's UART runs at ~20174 baud (its "19200" with a ~5 % fast clock).
#
#   import kaw
#   kaw.open()
#   kaw.query(kaw.VOLTS)   -> b'1!" $'  (reply line without the LF)
#   kaw.press(kaw.AMP)     -> True if the meter acked the button press
import time

import rp2
from machine import Pin

TX_PIN = 17
RX_PIN = 18
BAUD = 20174

# Queries: reply is a header byte + 4 digits (each 0x20 + digit).
# Q15 is the "0.2 Watt" setting in the calibration menu; what it does isn't known.
VOLTS, AMPS, WATTS, HZ, Q15, KWH, CLOCK = 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17
# Front-panel buttons: the meter beeps and acts as if the key was pressed;
# reply is the same byte echoed back.
VOLT, AMP, WATT_VA, HZ_PF, KWH_HOUR = 0x01, 0x02, 0x03, 0x04, 0x05
# Calibration mode, starting at "oPEn". The buttons change meaning in there: see README.md.
OPEN = 0x09


@rp2.asm_pio(sideset_init=rp2.PIO.OUT_HIGH, out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _uart_tx():
    pull()
    set(x, 7).side(0)[7]
    label("bitloop")
    out(pins, 1)[6]
    jmp(x_dec, "bitloop")
    nop().side(1)[6]


@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT, fifo_join=rp2.PIO.JOIN_RX)
def _uart_rx():
    label("start")
    wait(0, pin, 0)
    set(x, 7)[10]  # to the middle of bit 0
    label("bitloop")
    in_(pins, 1)
    jmp(x_dec, "bitloop")[6]
    jmp(pin, "good_stop")
    wait(1, pin, 0)  # framing error: drop it, wait for idle
    jmp("start")
    label("good_stop")
    push(block)


_tx = None
_rx = None


def open(baud=BAUD):
    global _tx, _rx
    close()
    _tx = rp2.StateMachine(4, _uart_tx, freq=8 * baud, sideset_base=Pin(TX_PIN), out_base=Pin(TX_PIN))
    _rx = rp2.StateMachine(5, _uart_rx, freq=8 * baud, in_base=Pin(RX_PIN, Pin.IN), jmp_pin=Pin(RX_PIN))
    _tx.active(1)
    _rx.active(1)
    flush()


def close():
    global _tx, _rx
    for sm in (_tx, _rx):
        if sm is not None:
            sm.active(0)
    _tx = _rx = None
    Pin(TX_PIN, Pin.IN)


def flush():
    while _rx.rx_fifo():
        _rx.get()


def write(data):
    for b in data:
        _tx.put(b)


def read_line(timeout_ms=100):
    """Bytes up to (not including) LF, or None on timeout."""
    buf = bytearray()
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if _rx.rx_fifo():
            b = _rx.get() >> 24
            if b == 0x0A:
                return bytes(buf)
            buf.append(b)
    return bytes(buf) if buf else None


def query(cmd, timeout_ms=100):
    flush()
    write(bytes([cmd]))
    return read_line(timeout_ms)


def press(button, timeout_ms=100):
    return query(button, timeout_ms) == bytes([button])


def value(cmd, timeout_ms=100):
    """A query decoded to a number using the header's decimal places, or None.

    CLOCK comes back as minutes (the display shows hh:mm, then whole hours past 99:59)."""
    rep = query(cmd, timeout_ms)
    if not rep or len(rep) != 5 or not all(0x20 <= b <= 0x29 for b in rep[1:]):
        return None
    digits = [b - 0x20 for b in rep[1:]]
    places = {0x1: 0, 0x3: 1, 0x5: 2}.get(rep[0] >> 4)
    if places is None:
        return None
    n = 0
    for d in digits:
        n = n * 10 + d
    if cmd == CLOCK:
        if places == 2:
            return (digits[0] * 10 + digits[1]) * 60 + digits[2] * 10 + digits[3]
        return n * 60 if places == 0 else None
    return n / 10 ** places
