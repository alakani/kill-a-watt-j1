# How the J1 protocol was worked out

A log of the reverse engineering, with pointers to the raw captures in `probe/`.
The result is in `README.md`.

## 1. Listening

- Both J1 lines idle high. A 30 s listen with pin interrupts saw **no edges** on either
  (`probe/edges.py`): the meter doesn't stream.
- Driving each line low at the Pico's weakest drive (2 mA) and reading the pad back
  (`probe/drive_test.py`): both went cleanly to 0, so neither is a strong push-pull
  output — safe to drive. (8051-style quasi-bidirectional pins or plain pull-ups.)

## 2. A lucky I2C scan

Two pulled-up lines suggested I2C. `probe/i2c_scan.py` scanned both orientations at
100 kHz and 10 kHz. With SDA = GP18, SCL = GP17 at 100 kHz it got "ACKs" at a few
scattered addresses, different each run; at 10 kHz, none. A real I2C device doesn't do
that.

Capturing both lines during the scan (`pico/la.py`, a PIO + DMA logic analyzer,
`probe/scan_capture.*`) showed GP18 still toggling for ~3 ms after the scan ended, in
multiples of ~49.6 µs: **a UART reply**. The 100 kHz clock on GP17 looked like bytes to
the meter's UART RX, and its answer on GP18 landed in the ACK slots.

So: GP17 = meter RX, GP18 = meter TX, ~20 kbaud.

## 3. Single bytes

A PIO UART TX on GP17 (`pico/ptx.py`) sent 0x00, 0x55, 0xFF, 0x01, 0xAA at 19200
(`probe/poke.*`): only **0x01** answered, with `01 0a`.

Then every byte 0x00–0xFF (`probe/sweep1.*`):

- `0x01`–`0x05`, `0x09`: echo + LF.
- `0x11`–`0x17`: five characters + LF.
- Nothing else.

During this sweep the meter **beeped several times and its display changed to
"OPEN"**. Power-cycling restored it; readings were unchanged afterwards.

## 4. Baud rate

From the LF terminator (start-bit fall to stop-bit rise = 9 bits) over 34 replies:
**49.57 µs per bit, sd 0.05 µs → 20174 baud**. A "19200" meter with a ~5 % fast clock.
Decoding the reply at 19200 still works, but a PIO receiver at 19200 samples the stop bit
right at its edge, so `pico/kaw.py` uses 20174 for both directions.

## 5. Decoding the readings

In the normal state (`probe/query*`, `probe/poll1.txt`), the replies to `0x11`–`0x17`
are a header plus four characters in `0x20`–`0x29`, i.e. `0x20` + a decimal digit.
`0x11` read `1204` and `0x14` read `0600` / `0599`, alternating: 120.4 V and
60.0 / 59.9 Hz.

With a small load plugged in (display: 120.4 V, 0.11 A, 6.3 W, 13.1–13.3 VA,
59.9–60 Hz, PF 0.47–0.48, 0.0 kWh):

| cmd | digits | matches |
| --- | --- | --- |
| `0x11` | 1204 | 120.4 V |
| `0x12` | 0010–0011 | 0.10–0.11 A |
| `0x13` | 0061–0066 | 6.1–6.6 W |
| `0x14` | 0599–0600 | 59.9–60.0 Hz |
| `0x15` | 0002 | nothing on the display (also 0002 with no load) |
| `0x16` | 0000 | 0.00 kWh |
| `0x17` | counts up once a minute from power-up | the display's clock (read `0015` when it showed 0:15) |

VA and PF aren't sent; V × A and W / VA reproduce the display.

The header's high nibble lines up with the decimal places: `0x3_` on V, W, Hz, `0x15`
(one decimal), `0x5_` on A, kWh, clock (two decimals / hh:mm).

## 6. Button commands, one at a time

With someone watching the display (`probe/cmd.py`, `probe/cmd*.txt`):

| sent | display before | effect |
| --- | --- | --- |
| `0x01` | volts | beep, stays on volts |
| `0x02` | volts | beep → amps |
| `0x03` | amps | beep → watts |
| `0x03` | watts | beep → VA |
| `0x04` | VA | beep → Hz |
| `0x05` | Hz | beep → kWh |
| `0x09` | kWh | beep → **OPEN** |
| `0x01` | OPEN (load unplugged) | beep → volts |

In the OPEN state every reading stayed live and correct, and nothing arrived unprompted
in 5 s (`probe/open_read.txt`). Before pressing a button there, the load was unplugged in
case OPEN was an "open-circuit" calibration step waiting to record a zero; with the load
plugged back in afterwards, readings were the same as before (0.11 A, 6.0 W). Most likely
OPEN is a link test for a factory fixture.
