# -------------------------------------------------
# ES8311 init sequence (BCLK‑derived MCLK + mic + speaker)
# -------------------------------------------------
import machine, time

i2c = machine.I2C(scl=machine.Pin(15), sda=machine.Pin(16))

# BCLK‑derived MCLK enable (Bruce sequence)
i2c.writeto(0x18, b'\x01\xbf')   # REG01 = 0xBF
i2c.writeto(0x18, b'\x02\x18')   # REG02 = 0x18

# Mic path
i2c.writeto(0x18, b'\x14\x1a')   # REG14 = 0x1A  (mic gain)
i2c.writeto(0x18, b'\x17\xc8')   # REG17 = 0xC8  (mic bias)

# Speaker path
i2c.writeto(0x18, b'\x03\x10')   # REG03 = 0x10
i2c.writeto(0x18, b'\x04\x10')   # REG04 = 0x10
i2c.writeto(0x18, b'\x05\x00')   # REG05 = 0x00
i2c.writeto(0x18, b'\x06\x03')   # REG06 = 0x03
i2c.writeto(0x18, b'\x07\x00')   # REG07 = 0x00
i2c.writeto(0x18, b'\x08\xff')   # REG08 = 0xFF
i2c.writeto(0x18, b'\x09\x0c')   # REG09 = 0x0C
i2c.writeto(0x18, b'\x0a\x0c')   # REG0A = 0x0C
i2c.writeto(0x18, b'\x0d\x01')   # REG0D = 0x01
i2c.writeto(0x18, b'\x0e\x02')   # REG0E = 0x02
i2c.writeto(0x18, b'\x12\x00')   # REG12 = 0x00
i2c.writeto(0x18, b'\x13\x10')   # REG13 = 0x10
i2c.writeto(0x18, b'\x1c\x6a')   # REG1C = 0x6A
i2c.writeto(0x18, b'\x37\x08')   # REG37 = 0x08
i2c.writeto(0x18, b'\x32\xd8')   # REG32 = 0xD8

print("ES8311 init sequence sent – no errors = OK")