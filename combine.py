import sys

frequency = 48000
baud_rate = 10

upper_data = open(sys.argv[1], "rb").read()
lower_data = open(sys.argv[2], "rb").read()
sample_coutdown = 0
await_start = True
byte = 0
was = -1
half_bit = (frequency // baud_rate) // 2
gap_counter = 0

for (upper, lower) in zip(upper_data, lower_data):
    upper &= 1
    lower &= 1
    if upper and not lower:
        bit = 1
    elif lower and not upper:
        bit = 0
    else:
        bit = -1

    if await_start:
        if (was != bit) and (bit == 1):
            await_start = False
            sample_countdown = half_bit * 3
            byte = 1
        else:
            gap_counter += 1
    else:
        sample_countdown -= 1
        if sample_countdown <= 0:
            if byte >= 0x100:
                # stop bit
                if gap_counter >= (half_bit * 2):
                    print(f"<gap {gap_counter // (half_bit * 2 * 10)}>")
                print(chr(byte & 0xff), end="")
                assert bit == 0
                byte = 0
                await_start = True
                gap_counter = 0
            else:
                # data bit
                sample_countdown = half_bit * 2
                byte = byte << 1
                if bit == 1:
                    byte |= 1
                assert bit == 0 or bit == 1
    was = bit

