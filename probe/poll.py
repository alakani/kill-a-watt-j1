import kaw, time
kaw.open()
while True:
    row = []
    for c in range(0x11, 0x18):
        rep = kaw.query(c, 60)
        if rep is None:
            row.append("--")
        else:
            row.append("%02x:%s" % (rep[0], "".join("%x" % (b - 0x20) if 0x20 <= b < 0x30 else "<%02x>" % b for b in rep[1:])))
    print(" ".join(row))
    time.sleep_ms(1000)
