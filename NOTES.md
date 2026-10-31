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
(one decimal), `0x5_` on A, kWh, clock (two decimals / hh:mm). A third code, `0x1_` (no
decimals), turned up later on the watts past 100 W (section 7).

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
plugged back in afterwards, readings were the same as before (0.11 A, 6.0 W). I took OPEN
for a factory link test. That was wrong: see section 9.

## 7. Watts past 100 W: header `0x13`

With a bigger load, read once a second, the watts reply changed from `33:0886` (88.6 W)
to `13:0183`–`13:0186` as the load passed 100 W, while volts (`31:1201`) and amps
(`52:0221`–`52:0223`) carried on as before. The decoder knew only `0x3_` and `0x5_`, so
it threw away every watts reply from then on.

`0x1_` is no decimal places: 186 W. The alternative, 18.6 W, would be a power factor of
0.07 at 120.1 V × 2.23 A = 268 VA; 186 W is 0.69, ordinary for electronics, and it
carries straight on from the 88 W before it. (Worked out from the other readings, not
checked against the display.) So the display shows tenths below 100 W and whole watts
from 100 W (seen up to 186), and the header says which.

Spelled out as bits, `0x1` = `001`, `0x3` = `011`, `0x5` = `101`: bit 0 always set,
bit 1 for one place, bit 2 for two. A guess from three codes.

## 8. The clock past 99:59: header `0x17`

A meter left running passed 100 hours on 30 Oct 2026. The decoder's clock stuck at 99:59,
rejecting a reply a second, and the raw reply had changed to `17:0102`: the same `0x1_`
no-decimals header as the watts, digits `0102`, whole hours. 9,868 rejected replies at
one a second is 2.74 hours past 100, so 102 is right, and the P4400 manual
says the same: "displayed as Hours:Minutes (from 00:00) and switch to Hours (to 9999)".
It also says the counters go back to zero at their maximum, and that kWh runs to 9999
with a shifting decimal, so `0x16` should step from `0x5_` to `0x3_` to `0x1_`.

## 9. `0x09` is calibration mode

Sent one byte at a time with someone reading the display, using a raw send that keeps
everything the meter says for 0.8 s and any byte that arrives outside a reply
(`probe/cal_map.txt`). The display's words are as read off the 7-segment LCD.

`0x02` steps through a loop of nine screens, and `0x03` steps back:
`oPEn`, `SAUE`, every segment flashing, `0.2` Watt, `I-20`, `I-10`, `I-01`, `U220`, `U110`.

- **`0x15` solved.** It reads `35:0002`, which with its one-decimal header is 0.2, and the
  menu shows 0.2 with the Watt icon. It was the same value on every screen, in and out of
  this mode. That's why it never followed the load. What the setting does isn't known; a
  threshold under which the meter treats the load as nothing is a guess.
- **The display test** lights icons this model has no use for ("breaker", "output on",
  "output off"), so the firmware looks shared with a model that has a relay.
- **Reported, not tested here:** that `oPEn` is an open-circuit (no load) calibration, at
  110 or 220 V, and that a voltage selected without doing `oPEn` first expects 10 A.
- The keys were expected to be menu, up, down, enter, output, in order. `0x01` left the mode
  from `oPEn`, `0x02` and `0x03` are up and down. `0x04` and `0x05` were only tried on the
  display test screen, the one place a stray enter could do no harm: `0x04` went to `SAUE`,
  after which one `0x02` didn't move it and `0x03` went to `oPEn` as usual; `0x05` beeped and
  did nothing. So `0x04` may be enter or back, and `0x05` may be either enter or an "output"
  key for a relay that isn't there.
- Every key was answered with just its echo, and readings stayed live and unchanged
  throughout, so nothing here reads calibration values out over the UART.

Selecting a real screen wasn't tried: the load couldn't be removed, and a wrong value with
no way to power-cycle the meter wasn't worth finding out about. Nothing was saved.
