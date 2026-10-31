# Kill A Watt J1 serial protocol

The P3 Kill A Watt **P4400.01** has a three-pin header, **J1**, with two signal pins and
ground. It's a UART, and the meter answers simple one-byte commands with its readings:
volts, amps, watts, frequency, kWh and the elapsed-time clock. It can also "press" its
own front-panel buttons.

Older Kill A Watt hacks (Tweet-a-Watt and friends) tap the LM2902 op-amp and read
analog voltages. This one talks to the meter's microcontroller directly and gets the
same numbers the display shows.

This repo has the protocol, a Raspberry Pi Pico (MicroPython) firmware that polls the
meter, and a host-side logger that writes CSV.

> [!WARNING]
> **The Kill A Watt is not isolated from the mains.** Its logic ground is tied to the
> AC line, so J1 can sit at line voltage relative to earth. Anything you wire to J1
> — and the computer that's plugged into it over USB — can end up live. Use an
> isolator (digital isolator, optocouplers, or a wireless link), or only connect while
> the meter is unplugged from the wall and powered separately from a low-voltage
> supply (5 V to its logic, or 9–12 V into its 7805 regulator as in the
> [SoundCertified mod](https://soundcertified.com/how-to-modify-kill-a-watt-meter-low-voltage/)).
> Never touch the circuit while it's plugged in.

## Hardware

- J1: two signal pins + GND, both idle high (pulled up to 5 V by the meter).
  Neither pin is a strong push-pull output, so driving them is safe. For photos of the
  board and J1, see
  [SoundCertified's teardown](https://soundcertified.com/how-to-modify-kill-a-watt-meter-low-voltage/).
- A 5 V ↔ 3.3 V level shifter (and, really, an isolator — see above).
- Raspberry Pi Pico (RP2040), MicroPython 1.29.

| J1 pin | meter side | Pico (through the level shifter) |
| --- | --- | --- |
| 1 (marked on the board) | RX — commands in | **GP17** (Pico TX) |
| 2 | TX — replies out | **GP18** (Pico RX) |
| 3 | GND | GND |

  Any two adjacent pins work; change `TX_PIN` / `RX_PIN` in `pico/kaw.py`.
  (`pico/la.py`, the logic analyzer, assumes GP17/GP18.)

## Protocol

- **UART 8N1.** The meter transmits at **~20174 baud** — a nominal 19200 with a clock
  that runs ~5 % fast (bit time 49.57 µs, very steady). It accepts commands at either
  19200 or 20174; `pico/kaw.py` uses 20174 both ways.
- The meter never talks on its own. Send **one command byte**; it replies within
  2–18 ms with a line ending in LF (0x0A).

### Reading commands

Reply: `H D D D D LF`

- `H`, header: low nibble = the command's low nibble; high nibble = decimal places as
  shown on the LCD: `0x1_` → none, `0x3_` → one, `0x5_` → two. The places follow the
  display, so one reading can change header as its value grows: **watts drop their
  decimal at 100 W** (88.6 W is `33 20 28 28 26`, 186 W is `13 20 21 28 26`). A decoder
  that only knows `0x3_` and `0x5_` loses the watts at the first 100 W load. **The clock
  does the same at 100 hours**: `57 29 29 25 29` is 99:59, then `17 20 21 20 22` is 102
  hours (the manual: hours:minutes, then hours to 9999). The manual has kWh shifting its
  decimal too (to 9999 kWh), which should arrive as `0x3_` and `0x1_`; not seen yet.
- `D`, four digits, most significant first, each **`0x20` + digit** (`' '` = 0, `'!'` = 1,
  … `')'` = 9).

| cmd | reading | header | example reply | value |
| --- | --- | --- | --- | --- |
| `0x11` | volts | `0x31` | `31 21 22 20 24 0a` | 120.4 V |
| `0x12` | amps | `0x52` | `52 20 20 21 21 0a` | 0.11 A |
| `0x13` | watts, under 100 W | `0x33` | `33 20 20 26 23 0a` | 6.3 W |
| `0x13` | watts, 100 W and up | `0x13` | `13 20 21 28 26 0a` | 186 W |
| `0x14` | frequency | `0x34` | `34 20 26 20 20 0a` | 60.0 Hz |
| `0x15` | the `0.2 Watt` setting in calibration mode; what it does is unknown | `0x35` | `35 20 20 20 22 0a` | 0.2 |
| `0x16` | energy | `0x56` | `56 20 20 20 20 0a` | 0.00 kWh |
| `0x17` | clock since power-up, to 99:59 | `0x57` | `57 20 20 21 25 0a` | 0:15 |
| `0x17` | clock, 100 hours and up | `0x17` | `17 20 21 20 22 0a` | 102 h |

VA and power factor aren't sent; compute them (VA = V × A, PF = W / VA). They match the
display, though with amps at 0.01 A resolution they're coarse at very small loads.

### Button commands

The meter beeps and behaves as if the key was pressed. Reply: the same byte echoed,
then LF.

| cmd | button | effect |
| --- | --- | --- |
| `0x01` | Volt | volts screen |
| `0x02` | Amp | amps screen |
| `0x03` | Watt/VA | watts; again → VA |
| `0x04` | Hz/PF | Hz; again → PF |
| `0x05` | kWh/Hour | kWh; again → clock |
| `0x09` | — | enters **calibration mode** (below) |

Every other single byte (0x00, 0x06–0x08, 0x0A–0x10, 0x18–0xFF) gets no reply. That sweep
sent `0x0A`–`0xFF` from inside calibration mode, on its first screen, and `0x00`–`0x08`
before entering it, so `0x06`–`0x08` haven't been tried in there.

### Calibration mode

> [!CAUTION]
> This is how the meter is calibrated. Only moving around the menu has been tried here.
> Nothing below has been selected or saved, so what selecting an item does to the
> calibration, and whether it survives a power cycle, is untested. Don't send `0x04` or
> `0x05` on `SAUE`: either might be enter.

`0x09` enters at `oPEn`. Readings keep working throughout, and the buttons change meaning.
The loop, with the display's 7-segment spelling:

| screen | what it probably is |
| --- | --- |
| `oPEn` | open-circuit (no load) calibration |
| `SAUE` | save |
| all segments flashing | display test, including icons this model doesn't use: "breaker", "output on", "output off" |
| `0.2` Watt | the value query `0x15` reads (header one decimal, digits `0002`). A low-power threshold is a guess |
| `I-20`, `I-10`, `I-01` | 20, 10 and 1 A: likely current calibration points |
| `U220`, `U110` | 220 and 110 V: voltage calibration points (a V is drawn as a U) |

| cmd | in calibration mode |
| --- | --- |
| `0x01` | left the mode from `oPEn`, back to volts (tried only there); probably "menu" |
| `0x02` | up: one step along the loop above |
| `0x03` | down: one step back |
| `0x04` | unclear. From the display test it went to `SAUE`; the next `0x02` didn't move it, then `0x03` went to `oPEn` as usual. Possibly enter, possibly back |
| `0x05` | a beep and no change on the display test. Possibly "output", for the relay that model has and this one doesn't |

Every key answered with its usual echo and nothing more, on every screen tried, so no
calibration values come out over the UART this way. The icons suggest the firmware is
shared with a model that has a relay and a breaker function.

## Using it

Copy the firmware to the Pico (`pyserial` is the only host dependency):

```bash
pip3 install pyserial
python3 tools/repl.py put pico/kaw.py kaw.py
python3 tools/repl.py put pico/main.py main.py
```

Then log:

```bash
python3 kaw_log.py               # prints readings, appends to kaw_log.csv
python3 kaw_log.py -o run1.csv   # another file
python3 kaw_log.py -s <usb-serial>   # pick one Pico when several are plugged in
```

```
07:52:21  120.4 V  0.11 A  6.1 W  13.2 VA  PF 0.46  60.0 Hz  0.00 kWh  0:39
```

CSV columns: `time, volts, amps, watts, va, pf, hz, kwh, elapsed_min, q15, raw`. Past
99:59 `elapsed_min` moves in whole hours, as the meter does.
`raw` keeps the undecoded replies, so if a value turns up in a format the decoder
doesn't know yet, it's blank in its column but preserved there.

On the Pico itself:

```python
import kaw
kaw.open()
kaw.value(kaw.WATTS)    # 6.3
kaw.value(kaw.CLOCK)    # minutes since power-up
kaw.press(kaw.AMP)      # beep, amps screen
```

## Files

| path | what |
| --- | --- |
| `kaw_log.py` | host logger: finds the Pico, starts `main.py`, decodes, writes CSV |
| `pico/main.py` | Pico firmware: polls all readings once a second, prints `K <ms> 31:1204 …` |
| `pico/kaw.py` | PIO UART driver (TX + RX at 20174 baud), `query`, `value`, `press` |
| `pico/la.py` | PIO + DMA two-channel logic analyzer on GP17/GP18 |
| `pico/ptx.py` | PIO UART TX only (used for the early sweeps) |
| `tools/repl.py` | small MicroPython raw-REPL client: `run`, `exec`, `put`, `ls` |
| `tools/decode.py`, `tools/show.py` | UART decoding of logic-analyzer captures |
| `probe/` | the experiments and their raw captures |
| `NOTES.md` | how the protocol was worked out |

## Open questions

- What the `0.2` Watt setting (`0x15`) does.
- What `0x04` and `0x05` do on a real menu screen, and which is enter. Trying that needs
  the load off and a meter you can power-cycle.
- Header codes for three decimals, if any reading needs them.
- Whether there are multi-byte commands (higher resolution, VA/PF directly). Only single
  bytes have been tried.

### Bigger numbers wanted

So far it's been tested up to ~190 W and 5 kWh, so watts ≥ 1000 and kWh ≥ 100 have never
been seen. If you log one of those and a column comes out blank or
wrong, please open an issue with a few lines of the CSV (the `raw` column is the useful
part) and what the display showed, and the decoder can be fixed.

## Thanks

To Marty at SoundCertified for
[How to Modify a Kill A Watt Meter for Low Voltage](https://soundcertified.com/how-to-modify-kill-a-watt-meter-low-voltage/),
which gave me the idea and has photos of the board. His mod — running the meter from a
DC supply so it can measure low-voltage signals like amplifier output — is another fun
project for this meter, and pairs well with this one: with no mains on the board, J1 is
safe to wire up.

And to Claude (Anthropic's Claude Code), which did the probing, the protocol decoding
and most of the code here while I wired things up and watched the display.

## License

Public domain — [The Unlicense](https://unlicense.org). See `LICENSE`.
