from machine import Pin, SoftI2C
for sda, scl in ((17, 18), (18, 17)):
    for f in (100000, 10000):
        i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=f, timeout=2000)
        try:
            found = i2c.scan()
        except Exception as e:
            found = repr(e)
        print("SDA=GP%d SCL=GP%d %dHz ->" % (sda, scl, f), [hex(a) if isinstance(a, int) else a for a in found] if isinstance(found, list) else found)
Pin(17, Pin.IN); Pin(18, Pin.IN)
