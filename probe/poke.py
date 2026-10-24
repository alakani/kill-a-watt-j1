import la, ptx, time
BAUD = 19200
ptx.open(BAUD)
for b in (0x00, 0x55, 0xff, 0x01, 0xaa):
    la.start(freq=1_000_000, words=12500)  # 200 ms
    time.sleep_ms(2)
    ptx.write(bytes([b]))
    la.wait()
    print("SENT %02x" % b)
    la.dump()
    time.sleep_ms(300)
ptx.close()
