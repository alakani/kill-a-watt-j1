import la, time
from machine import Pin, SoftI2C
la.start(freq=1_000_000, words=20000)   # 320 ms
time.sleep_ms(5)
i2c = SoftI2C(sda=Pin(18), scl=Pin(17), freq=100000, timeout=2000)
found = i2c.scan()
Pin(17, Pin.IN); Pin(18, Pin.IN)
la.wait()
print("found", [hex(a) for a in found])
la.dump()
