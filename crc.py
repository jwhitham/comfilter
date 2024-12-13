
import zlib

#polynomial = 0x04C11DB7
#bit_width = 32

def crc(data, polynomial = 0x4c11db7, bit_width = 32, flip = True, lsb_first = True, reverse_out = True):
    value = 0
    if flip:
        value ^= (1 << bit_width) - 1


    # for each bit
    for byte in data:
        for j in range(8):
            bit_flag = (value >> (bit_width - 1)) ^ (byte >> (j if lsb_first else (7 - j)))
            value = value << 1
            if bit_flag & 1:
                value ^= polynomial
            value &= (1 << bit_width) - 1

    if flip:
        value ^= (1 << bit_width) - 1
    # bit reverse
    if reverse_out:
        value2 = 0
        for j in range(bit_width):
            value2 |= ((value >> j) & 1) << (bit_width - 1 - j)
        value = value2
    return value

def check(a):
    assert crc(a) == zlib.crc32(a)

for i in range(10):
    check(b"\x00" * i)
for i in range(1, 10):
    check(b"\x01" * i)
for i in range(1, 10):
    check(b"\x80" * i)

check(b"123456789")
check(b"hello world")
assert crc(b"123456789") == 0xCBF43926

for i in range(1, 4):
    check(b"\x55\xaa\x99" * i)


def crc16(data):
    polynomial = 0x8005
    bit_width = 16
    return crc(data, polynomial, bit_width, False)

def crc16_ccitt_kermit(data):
    polynomial = 0x1021
    bit_width = 16
    return crc(data, polynomial, bit_width, False)

def crc16_ccitt_xmodem(data):
    polynomial = 0x1021
    bit_width = 16
    return crc(data, polynomial, bit_width, False, False, False)

assert crc16(b"123456789") == 0xbb3d
assert crc16_ccitt_kermit(b"123456789") == 0x2189
assert crc16_ccitt_xmodem(b"123456789") == 0x31c3
assert crc(b"") == 0
print(hex(crc(b"\x80")))

