# Send one action command and show the reply plus a snapshot of all readings around it.
import kaw, time
CMD = 0x01
kaw.open()
def snap():
    return " ".join("%02x:%r" % (c, kaw.query(c, 60)) for c in range(0x11, 0x18))
print("before:", snap())
t0 = time.ticks_us()
rep = kaw.query(CMD, 200)
print("sent %02x -> %r (%d us)" % (CMD, rep, time.ticks_diff(time.ticks_us(), t0)))
time.sleep_ms(500)
print("after: ", snap())
# anything unsolicited in the next 2 s?
extra = kaw.read_line(2000)
print("extra:", extra)
kaw.close()
