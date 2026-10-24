# Send each command in CMDS once, record GP18 edge times (us) after it.
import la, ptx, time
CMDS = [0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17]
REPEAT = 3
ptx.open(19200)
for r in range(REPEAT):
    for b in CMDS:
        la.start(freq=500_000, words=2000)  # 64 ms
        time.sleep_ms(1)
        ptx.write(bytes([b]))
        la.wait()
        out, k = la.edges(400)
        ts = []
        prev = 1
        for j in range(1, k):
            e = int.from_bytes(out[4*j:4*j+4], "little")
            v = (e & 3) >> 1
            if v != prev:
                ts.append((e >> 2) * 2)
                prev = v
        print("B %02x %s" % (b, ",".join(str(x) for x in ts)))
        time.sleep_ms(30)
ptx.close()
