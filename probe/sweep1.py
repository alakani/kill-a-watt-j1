import la, ptx, time
BAUD = 19200
ptx.open(BAUD)
for b in range(256):
    la.start(freq=500_000, words=2000)  # 64 ms
    time.sleep_ms(1)
    ptx.write(bytes([b]))
    la.wait()
    out, k = la.edges(400)
    # only GP18 (bit1) edges matter; print compactly
    ts = []
    prev = 1
    for j in range(1, k):
        e = int.from_bytes(out[4*j:4*j+4], "little")
        v = (e & 3) >> 1
        if v != prev:
            ts.append((e >> 2) * 2)
            prev = v
    print("B %02x %s" % (b, ",".join(str(x) for x in ts)))
    time.sleep_ms(40)
ptx.close()
