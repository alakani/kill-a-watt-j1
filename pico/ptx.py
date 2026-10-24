# PIO UART transmitter on GP17 (to the meter's RX), 8N1, any baud.
import time

import rp2
from machine import Pin

TX_PIN = 17


@rp2.asm_pio(sideset_init=rp2.PIO.OUT_HIGH, out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _uart_tx():
    pull()
    set(x, 7).side(0)[7]
    label("bitloop")
    out(pins, 1)[6]
    jmp(x_dec, "bitloop")
    nop().side(1)[6]


_sm = None
_baud = 0


def open(baud):
    global _sm, _baud
    close()
    _baud = baud
    _sm = rp2.StateMachine(1, _uart_tx, freq=8 * baud, sideset_base=Pin(TX_PIN), out_base=Pin(TX_PIN))
    _sm.active(1)


def write(data):
    for b in data:
        _sm.put(b)
    # wait for the last byte to clock out (FIFO drain + one frame)
    while _sm.tx_fifo():
        pass
    time.sleep_us(int(11_000_000 / _baud))


def close():
    global _sm
    if _sm is not None:
        _sm.active(0)
        _sm = None
    Pin(TX_PIN, Pin.IN)
