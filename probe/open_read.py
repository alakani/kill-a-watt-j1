# Read-only look at the meter in the "OPEN" state: queries + listen for unsolicited bytes.
import kaw, time
kaw.open()
for r in range(3):
    print(" ".join("%02x:%r" % (c, kaw.query(c, 60)) for c in range(0x11, 0x18)))
    time.sleep_ms(700)
kaw.flush()
t0 = time.ticks_ms()
got = []
while time.ticks_diff(time.ticks_ms(), t0) < 5000:
    l = kaw.read_line(200)
    if l is not None:
        got.append(l)
print("unsolicited in 5 s:", got)
kaw.close()
