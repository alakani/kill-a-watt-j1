import kaw, time
kaw.open()
for r in range(3):
    row = []
    for c in range(0x11, 0x18):
        t0 = time.ticks_us()
        rep = kaw.query(c)
        row.append("%02x:%r/%dms" % (c, rep, time.ticks_diff(time.ticks_us(), t0) // 1000))
    print(" ".join(row))
    time.sleep_ms(500)
kaw.close()
